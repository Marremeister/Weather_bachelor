from datetime import date, datetime

import httpx
from zoneinfo import ZoneInfo

from app.services.weather_provider import FetchResult, HourlyRecord, WeatherProvider

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def parse_open_meteo_response(data: dict, timezone: str) -> list[HourlyRecord]:
    """Parse an Open-Meteo archive JSON response into HourlyRecords."""
    tz = ZoneInfo(timezone)
    utc = ZoneInfo("UTC")
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    records: list[HourlyRecord] = []

    for i, time_str in enumerate(times):
        local_dt = datetime.fromisoformat(time_str).replace(tzinfo=tz)
        utc_dt = local_dt.astimezone(utc)
        records.append(
            HourlyRecord(
                valid_time_utc=utc_dt,
                valid_time_local=local_dt.replace(tzinfo=None),
                true_wind_speed=hourly.get("wind_speed_10m", [None] * len(times))[i],
                true_wind_direction=hourly.get("wind_direction_10m", [None] * len(times))[i],
                temperature=hourly.get("temperature_2m", [None] * len(times))[i],
                pressure=hourly.get("surface_pressure", [None] * len(times))[i],
                cloud_cover=hourly.get("cloud_cover", [None] * len(times))[i],
            )
        )
    return records


class OpenMeteoProvider(WeatherProvider):
    @property
    def source_name(self) -> str:
        return "open_meteo"

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
        }
        response = httpx.get(ARCHIVE_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        records = parse_open_meteo_response(data, timezone)
        return FetchResult(records=records, raw_payload=data)


class OpenMeteoForecastProvider(WeatherProvider):
    """Fetches forecast data from the Open-Meteo forecast API.

    Covers up to ~16 days into the future. Response format is identical
    to the archive endpoint, so we reuse ``parse_open_meteo_response``.
    """

    @property
    def source_name(self) -> str:
        return "open_meteo_forecast"

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
        }
        response = httpx.get(FORECAST_URL, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        records = parse_open_meteo_response(data, timezone)
        return FetchResult(records=records, raw_payload=data)
