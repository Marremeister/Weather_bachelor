"""ERA5 Reanalysis Provider — fetches historical weather from CDS or Open-Meteo fallback.

Downloads ERA5 single-level reanalysis GRIB files from the Copernicus Climate
Data Store (CDS) via cdsapi, parses with cfgrib/xarray, and returns
HourlyRecords.  Falls back to Open-Meteo archive with ``&models=era5`` when
CDS credentials are missing or the download fails.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from app.config import settings
from app.services.gfs_grib_utils import (
    _open_target_da,
    select_point_dataarray,
    validate_grib_file,
    wind_dir_deg,
    wind_speed,
)
from app.services.open_meteo_provider import parse_open_meteo_response
from app.services.weather_provider import FetchResult, HourlyRecord, WeatherProvider

logger = logging.getLogger(__name__)

ERA5_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class Era5Provider(WeatherProvider):
    """Fetches ERA5 reanalysis data, year-by-year GRIB from CDS."""

    @property
    def source_name(self) -> str:
        return "era5"

    # ------------------------------------------------------------------
    # GRIB caching
    # ------------------------------------------------------------------

    def _grib_cache_path(self, year: int) -> Path:
        version = settings.era5_data_version
        return (
            Path(settings.grib_cache_dir)
            / "era5"
            / f"era5_point_{year}_{version}.grib"
        )

    # ------------------------------------------------------------------
    # CDS download
    # ------------------------------------------------------------------

    def _download_era5_year(self, year: int, lat: float, lon: float) -> Path:
        """Download ERA5 single-levels for one year from CDS.  Skips if cached."""
        cache_path = self._grib_cache_path(year)

        if cache_path.exists() and cache_path.stat().st_size > 0:
            logger.info("ERA5 GRIB cache hit: %s", cache_path)
            return cache_path

        import cdsapi

        client = cdsapi.Client(
            url=settings.cdsapi_url,
            key=settings.cdsapi_key,
        )

        buf = settings.point_buffer_deg
        area = [lat + buf, lon - buf, lat - buf, lon + buf]  # N, W, S, E

        months = [f"{m:02d}" for m in settings.era5_months_list]
        days = [f"{d:02d}" for d in range(1, 32)]
        hours = [f"{h:02d}:00" for h in range(24)]

        logger.info("Downloading ERA5 year=%d months=%s area=%s", year, months, area)

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_suffix(".tmp")

        client.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "reanalysis",
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "2m_temperature",
                    "2m_dewpoint_temperature",
                    "mean_sea_level_pressure",
                    "boundary_layer_height",
                    "total_cloud_cover",
                ],
                "year": str(year),
                "month": months,
                "day": days,
                "time": hours,
                "area": area,
                "data_format": "grib",
            },
            str(tmp_path),
        )

        # Atomic rename
        tmp_path.rename(cache_path)
        logger.info(
            "ERA5 GRIB downloaded: %s (%.1f MB)",
            cache_path,
            cache_path.stat().st_size / 1e6,
        )
        return cache_path

    # ------------------------------------------------------------------
    # GRIB parsing
    # ------------------------------------------------------------------

    def _parse_era5_grib(
        self, path: Path, lat: float, lon: float, timezone: str
    ) -> list[HourlyRecord]:
        """Parse a multi-timestep ERA5 GRIB into HourlyRecords."""
        import xarray as xr

        tz = ZoneInfo(timezone)
        records: list[HourlyRecord] = []

        # ERA5 GRIB may contain multiple variables; open all filter combos
        u10_da = _open_target_da(str(path), "u10")
        v10_da = _open_target_da(str(path), "v10")
        t2m_da = _open_target_da(str(path), "t2m")
        mslp_da = _open_target_da(str(path), "mslp")
        tcc_da = _open_target_da(str(path), "tcc")

        # Determine the time coordinate from whichever variable loaded
        time_da = None
        for da in (u10_da, v10_da, t2m_da, mslp_da, tcc_da):
            if da is not None and "time" in da.dims:
                time_da = da.coords["time"]
                break

        if time_da is None:
            logger.warning("No time dimension found in ERA5 GRIB %s", path)
            return records

        for t in time_da.values:
            ts = _numpy_dt_to_datetime(t)
            valid_utc = ts.replace(tzinfo=ZoneInfo("UTC"))
            valid_local = valid_utc.astimezone(tz).replace(tzinfo=None)

            u10_val = _extract_point_at_time(u10_da, lat, lon, t)
            v10_val = _extract_point_at_time(v10_da, lat, lon, t)

            ws = None
            wd = None
            if u10_val is not None and v10_val is not None:
                ws = wind_speed(u10_val, v10_val)
                wd = wind_dir_deg(u10_val, v10_val)

            temp = _extract_point_at_time(t2m_da, lat, lon, t)
            if temp is not None and temp > 200:
                temp -= 273.15  # K -> C

            pressure = _extract_point_at_time(mslp_da, lat, lon, t)
            if pressure is not None and pressure > 50000:
                pressure /= 100.0  # Pa -> hPa

            cloud = _extract_point_at_time(tcc_da, lat, lon, t)
            if cloud is not None and cloud <= 1.0:
                cloud *= 100.0  # fraction -> %

            records.append(
                HourlyRecord(
                    valid_time_utc=valid_utc,
                    valid_time_local=valid_local,
                    true_wind_speed=ws,
                    true_wind_direction=wd,
                    temperature=temp,
                    pressure=pressure,
                    cloud_cover=cloud,
                    model_name="era5",
                )
            )

        return records

    # ------------------------------------------------------------------
    # Open-Meteo fallback
    # ------------------------------------------------------------------

    def _fetch_open_meteo_fallback(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult:
        """Fetch ERA5 data via Open-Meteo archive API as fallback."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": "wind_speed_10m,wind_direction_10m,temperature_2m,surface_pressure,cloud_cover",
            "wind_speed_unit": "ms",
            "timezone": timezone,
            "models": "era5",
        }
        response = httpx.get(ERA5_ARCHIVE_URL, params=params, timeout=60.0)
        response.raise_for_status()
        data = response.json()
        records = parse_open_meteo_response(data, timezone)
        # Tag records with era5_open_meteo model name
        for r in records:
            r.model_name = "era5_open_meteo"
        return FetchResult(records=records, raw_payload=data)

    # ------------------------------------------------------------------
    # WeatherProvider.fetch()
    # ------------------------------------------------------------------

    def fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult:
        all_records: list[HourlyRecord] = []

        # If no CDS key configured, go straight to fallback
        if not settings.cdsapi_key:
            if settings.era5_fallback_to_open_meteo:
                logger.info("No CDSAPI_KEY set, using Open-Meteo ERA5 fallback")
                return self._fetch_open_meteo_fallback(
                    latitude, longitude, start_date, end_date, timezone
                )
            raise RuntimeError(
                "CDSAPI_KEY not configured and era5_fallback_to_open_meteo is False"
            )

        for year in range(start_date.year, end_date.year + 1):
            try:
                grib_path = self._download_era5_year(year, latitude, longitude)
                year_records = self._parse_era5_grib(
                    grib_path, latitude, longitude, timezone
                )
                # Filter to requested date range
                for r in year_records:
                    rd = r.valid_time_local.date() if hasattr(r.valid_time_local, "date") else r.valid_time_local
                    if isinstance(rd, datetime):
                        rd = rd.date()
                    if start_date <= rd <= end_date:
                        all_records.append(r)
            except Exception as exc:
                logger.error("ERA5 CDS fetch failed for year %d: %s", year, exc)
                if settings.era5_fallback_to_open_meteo:
                    logger.info("Falling back to Open-Meteo ERA5 for year %d", year)
                    # Compute year-bounded date range
                    y_start = max(start_date, date(year, 1, 1))
                    y_end = min(end_date, date(year, 12, 31))
                    fb = self._fetch_open_meteo_fallback(
                        latitude, longitude, y_start, y_end, timezone
                    )
                    all_records.extend(fb.records)
                else:
                    raise

        return FetchResult(
            records=all_records,
            raw_payload={
                "source": "era5",
                "years": list(range(start_date.year, end_date.year + 1)),
                "record_count": len(all_records),
            },
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _numpy_dt_to_datetime(np_dt) -> datetime:
    """Convert numpy datetime64 to Python datetime."""
    import numpy as np

    ts = (np_dt - np.datetime64("1970-01-01T00:00:00")) / np.timedelta64(1, "s")
    return datetime.utcfromtimestamp(float(ts))


def _extract_point_at_time(da, lat: float, lon: float, time_val) -> float | None:
    """Extract a single scalar value from a DataArray at (lat, lon, time)."""
    if da is None:
        return None
    try:
        sliced = da.sel(time=time_val)
        pt = select_point_dataarray(sliced, lat, lon)
        return float(pt.values)
    except Exception:
        return None
