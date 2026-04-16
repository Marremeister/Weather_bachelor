"""GFS Forecast Provider — Option A: NCAR RDA THREDDS GRIB2 downloads.

Downloads GFS 0.25-degree GRIB2 files from NCAR RDA, parses them with
cfgrib/xarray, extracts nearest-point data, and returns HourlyRecords.

Key design: the provider picks the latest *already-published* GFS cycle,
then computes forecast-hour offsets so each valid time lands inside the
requested target day's local analysis window (default 08:00–16:00 local).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from app.config import settings
from app.services.gfs_common import forecast_hours_for_window
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

# GFS cycles run at 00, 06, 12, 18 UTC
_GFS_CYCLES = [0, 6, 12, 18]


class GfsDownloadError(Exception):
    """Raised when GFS GRIB download fails and fallback should be attempted."""


def _latest_available_cycle(now_utc: datetime) -> tuple[datetime, int]:
    """Return (model_run_time, cycle_hour) for the latest GFS cycle
    whose data is likely published, accounting for processing lag.

    GFS data becomes available ~5 hours after cycle init.
    """
    lag = settings.gfs_publish_lag_hours
    available_at = now_utc - timedelta(hours=lag)

    # Walk backwards through cycles to find the latest one
    for hours_back in range(0, 48, 6):
        candidate = available_at - timedelta(hours=hours_back)
        cycle_hour = (candidate.hour // 6) * 6
        run_time = candidate.replace(
            hour=cycle_hour, minute=0, second=0, microsecond=0
        )
        # The run must have been initialized *before* the available-at cutoff
        if run_time + timedelta(hours=lag) <= now_utc:
            return run_time, cycle_hour

    # Absolute fallback: yesterday's 00Z
    yesterday = (now_utc - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return yesterday, 0


# Backward-compatible alias for callers importing this symbol from the
# live-forecast module.  The implementation now lives in gfs_common.
_forecast_hours_for_window = forecast_hours_for_window


class GfsForecastProvider(WeatherProvider):
    """Fetches GFS forecast data from NCAR RDA GRIB2 files.

    Automatically selects the latest available GFS cycle and computes
    forecast hours covering the target day's analysis window.
    """

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

        Picks the latest available GFS cycle, computes forecast-hour
        offsets covering the analysis window (local 08:00–16:00) on each
        target day, and downloads the corresponding GRIB2 files.
        """
        utc = ZoneInfo("UTC")
        now_utc = datetime.now(tz=utc)

        model_run_time, cycle_hour = _latest_available_cycle(now_utc)
        cycle_str = f"{cycle_hour:02d}"
        run_yyyymmdd = model_run_time.strftime("%Y%m%d")

        logger.info(
            "Selected GFS cycle: %s %sZ (lag=%dh)",
            run_yyyymmdd, cycle_str, settings.gfs_publish_lag_hours,
        )

        local_start = settings.gfs_analysis_local_start
        local_end = settings.gfs_analysis_local_end

        all_records: list[HourlyRecord] = []
        errors: list[str] = []
        all_fhours: list[int] = []

        current = start_date
        while current <= end_date:
            fhours = _forecast_hours_for_window(
                model_run_time, current, timezone, local_start, local_end,
            )
            all_fhours.extend(fhours)

            logger.info(
                "Target %s: forecast hours %s from %s %sZ",
                current, fhours, run_yyyymmdd, cycle_str,
            )

            for fhour in fhours:
                fhour_str = f"{fhour:03d}"
                try:
                    grib_path = self._download_grib(
                        run_yyyymmdd, cycle_str, fhour_str,
                    )
                    records = self._parse_grib_to_records(
                        grib_path, latitude, longitude, timezone,
                        model_run_time, fhour,
                    )
                    all_records.extend(records)
                except GfsDownloadError as exc:
                    logger.error("GFS download failed: %s", exc)
                    errors.append(str(exc))
                except Exception as exc:
                    logger.error(
                        "GFS parse failed for %s %sZ f%03d: %s",
                        run_yyyymmdd, cycle_str, fhour, exc,
                    )
                    errors.append(str(exc))

            current += timedelta(days=1)

        total_expected = len(all_fhours)
        if not all_records and errors:
            raise GfsDownloadError(
                f"All GFS downloads failed: {'; '.join(errors[:3])}"
            )
        if total_expected > 0 and len(all_records) < total_expected * 0.9:
            raise GfsDownloadError(
                f"GFS partial failure: got {len(all_records)}/{total_expected} "
                f"hours; {'; '.join(errors[:3])}"
            )

        return FetchResult(
            records=all_records,
            raw_payload={
                "source": "gfs",
                "model_run": f"{run_yyyymmdd}_{cycle_str}Z",
                "forecast_hours": sorted(set(all_fhours)),
                "record_count": len(all_records),
            },
        )
