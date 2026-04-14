"""GFS Open-Meteo Provider — Option B fallback.

Uses the Open-Meteo forecast API with ``&models=gfs_seamless`` to fetch
GFS-based forecast data. Acts as a fallback when NCAR RDA GRIB downloads
are unavailable.
"""

from __future__ import annotations

from datetime import date

import httpx

from app.services.open_meteo_provider import FORECAST_URL, parse_open_meteo_response
from app.services.weather_provider import FetchResult, HourlyRecord, WeatherProvider


class GfsOpenMeteoProvider(WeatherProvider):
    """Fetches GFS forecast data via Open-Meteo's forecast API."""

    @property
    def source_name(self) -> str:
        return "gfs_open_meteo"

    def fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "hourly": "wind_speed_10m,wind_direction_10m,temperature_2m,surface_pressure,cloud_cover",
            "wind_speed_unit": "ms",
            "timezone": timezone,
            "models": "gfs_seamless",
        }
        response = httpx.get(FORECAST_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        records = parse_open_meteo_response(data, timezone)

        # Tag each record with model metadata
        for r in records:
            r.model_name = "gfs_seamless"

        return FetchResult(records=records, raw_payload=data)
