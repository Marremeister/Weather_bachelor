"""GFS Forecast Provider — Option A: NCAR RDA THREDDS GRIB2 downloads.

Downloads GFS 0.25-degree GRIB2 files from NCAR RDA, parses them with
cfgrib/xarray, extracts nearest-point data, and returns HourlyRecords.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import requests

from app.config import settings
from app.services.gfs_grib_utils import (
    _open_target_da,
    select_point_dataarray,
    validate_grib_file,
    wind_dir_deg,
    wind_speed,
)
from app.services.weather_provider import FetchResult, HourlyRecord, WeatherProvider

logger = logging.getLogger(__name__)

NCAR_BASE = "https://thredds.rda.ucar.edu/thredds/fileServer/files/g/d084001"


class GfsDownloadError(Exception):
    """Raised when GFS GRIB download fails and fallback should be attempted."""


class GfsForecastProvider(WeatherProvider):
    """Fetches GFS forecast data from NCAR RDA GRIB2 files."""

    @property
    def source_name(self) -> str:
        return "gfs"

    def _grib_cache_path(self, yyyymmdd: str, cycle: str, fhour: str) -> Path:
        return (
            Path(settings.grib_cache_dir)
            / "gfs"
            / yyyymmdd
            / f"gfs.0p25.{yyyymmdd}{cycle}.f{fhour}.grib2"
        )

    def _download_grib(self, yyyymmdd: str, cycle: str, fhour: str) -> Path:
        """Download a GFS GRIB2 file from NCAR RDA, with local caching."""
        cache_path = self._grib_cache_path(yyyymmdd, cycle, fhour)

        if cache_path.exists() and validate_grib_file(cache_path):
            logger.info("GRIB cache hit: %s", cache_path)
            return cache_path

        year = yyyymmdd[:4]
        url = (
            f"{NCAR_BASE}/{year}/{yyyymmdd}/"
            f"gfs.0p25.{yyyymmdd}{cycle}.f{fhour}.grib2"
        )

        logger.info("Downloading GFS GRIB: %s", url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            resp = requests.get(
                url, stream=True, timeout=settings.gfs_download_timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise GfsDownloadError(
                f"Failed to download {url}: {exc}"
            ) from exc

        # Write to temp file then rename for atomicity
        tmp_path = cache_path.with_suffix(".tmp")
        try:
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)

            if not validate_grib_file(tmp_path):
                tmp_path.unlink(missing_ok=True)
                raise GfsDownloadError(
                    f"Downloaded file is not valid GRIB: {url}"
                )

            tmp_path.rename(cache_path)
        except GfsDownloadError:
            raise
        except Exception as exc:
            tmp_path.unlink(missing_ok=True)
            raise GfsDownloadError(
                f"Error saving GRIB file: {exc}"
            ) from exc

        logger.info("GRIB downloaded: %s (%.1f MB)", cache_path, cache_path.stat().st_size / 1e6)
        return cache_path

    def _parse_grib_to_records(
        self,
        path: Path,
        latitude: float,
        longitude: float,
        timezone: str,
        model_run_time: datetime,
        forecast_hour: int,
    ) -> list[HourlyRecord]:
        """Parse a GRIB2 file and extract nearest-point data as HourlyRecords."""
        tz = ZoneInfo(timezone)
        utc = ZoneInfo("UTC")

        # Extract target variables
        u10_da = _open_target_da(str(path), "u10")
        v10_da = _open_target_da(str(path), "v10")
        t2m_da = _open_target_da(str(path), "t2m")
        mslp_da = _open_target_da(str(path), "mslp")
        tcc_da = _open_target_da(str(path), "tcc")

        # Extract point values
        u10_val = None
        v10_val = None
        ws = None
        wd = None
        temp = None
        pressure = None
        cloud = None

        if u10_da is not None:
            try:
                pt = select_point_dataarray(u10_da, latitude, longitude)
                u10_val = float(pt.values)
            except Exception:
                logger.warning("Failed to extract u10 point data")

        if v10_da is not None:
            try:
                pt = select_point_dataarray(v10_da, latitude, longitude)
                v10_val = float(pt.values)
            except Exception:
                logger.warning("Failed to extract v10 point data")

        if u10_val is not None and v10_val is not None:
            ws = wind_speed(u10_val, v10_val)
            wd = wind_dir_deg(u10_val, v10_val)

        if t2m_da is not None:
            try:
                pt = select_point_dataarray(t2m_da, latitude, longitude)
                val = float(pt.values)
                # Convert Kelvin to Celsius if needed
                if val > 200:
                    val -= 273.15
                temp = val
            except Exception:
                logger.warning("Failed to extract t2m point data")

        if mslp_da is not None:
            try:
                pt = select_point_dataarray(mslp_da, latitude, longitude)
                val = float(pt.values)
                # Convert Pa to hPa if needed
                if val > 50000:
                    val /= 100.0
                pressure = val
            except Exception:
                logger.warning("Failed to extract mslp point data")

        if tcc_da is not None:
            try:
                pt = select_point_dataarray(tcc_da, latitude, longitude)
                val = float(pt.values)
                # Convert fraction (0-1) to percentage if needed
                if val <= 1.0:
                    val *= 100.0
                cloud = val
            except Exception:
                logger.warning("Failed to extract tcc point data")

        # Compute valid time from model run + forecast hour
        valid_time_utc = model_run_time + timedelta(hours=forecast_hour)
        valid_time_local = valid_time_utc.astimezone(tz)

        record = HourlyRecord(
            valid_time_utc=valid_time_utc,
            valid_time_local=valid_time_local.replace(tzinfo=None),
            true_wind_speed=ws,
            true_wind_direction=wd,
            temperature=temp,
            pressure=pressure,
            cloud_cover=cloud,
            model_run_time=model_run_time,
            forecast_hour=forecast_hour,
            model_name="gfs_0p25",
        )

        return [record]

    def fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult:
        """Fetch GFS forecast data for the given date range.

        Downloads GRIB2 files for each date × forecast hour combination,
        parses them, and returns a FetchResult.
        """
        cycle = settings.gfs_cycle
        forecast_hours = settings.gfs_forecast_hours_list
        utc = ZoneInfo("UTC")

        all_records: list[HourlyRecord] = []
        errors: list[str] = []

        current = start_date
        while current <= end_date:
            yyyymmdd = current.strftime("%Y%m%d")
            model_run_time = datetime(
                current.year, current.month, current.day,
                int(cycle), 0, 0, tzinfo=utc,
            )

            for fhour_str in forecast_hours:
                fhour = int(fhour_str)
                try:
                    grib_path = self._download_grib(yyyymmdd, cycle, fhour_str)
                    records = self._parse_grib_to_records(
                        grib_path, latitude, longitude, timezone,
                        model_run_time, fhour,
                    )
                    all_records.extend(records)
                except GfsDownloadError as exc:
                    logger.error("GFS download failed: %s", exc)
                    errors.append(str(exc))
                except Exception as exc:
                    logger.error("GFS parse failed for %s f%s: %s", yyyymmdd, fhour_str, exc)
                    errors.append(str(exc))

            current += timedelta(days=1)

        if not all_records and errors:
            raise GfsDownloadError(
                f"All GFS downloads failed: {'; '.join(errors[:3])}"
            )

        return FetchResult(
            records=all_records,
            raw_payload={
                "source": "gfs",
                "cycle": cycle,
                "forecast_hours": forecast_hours,
                "record_count": len(all_records),
            },
        )
