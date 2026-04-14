"""Tests for parse_open_meteo_response — data ingestion boundary, no DB required."""

from datetime import datetime

from zoneinfo import ZoneInfo

from app.services.open_meteo_provider import parse_open_meteo_response


def _make_response(
    times: list[str],
    wind_speed: list[float | None] | None = None,
    wind_direction: list[float | None] | None = None,
    temperature: list[float | None] | None = None,
    pressure: list[float | None] | None = None,
    cloud_cover: list[float | None] | None = None,
) -> dict:
    """Build a minimal Open-Meteo-shaped dict."""
    hourly: dict = {"time": times}
    if wind_speed is not None:
        hourly["wind_speed_10m"] = wind_speed
    if wind_direction is not None:
        hourly["wind_direction_10m"] = wind_direction
    if temperature is not None:
        hourly["temperature_2m"] = temperature
    if pressure is not None:
        hourly["surface_pressure"] = pressure
    if cloud_cover is not None:
        hourly["cloud_cover"] = cloud_cover
    return {"hourly": hourly}


class TestParseOpenMeteoResponse:
    def test_basic_parsing(self):
        """3-hour response with all fields populated parses correctly."""
        data = _make_response(
            times=["2024-07-15T10:00", "2024-07-15T11:00", "2024-07-15T12:00"],
            wind_speed=[5.0, 6.0, 7.0],
            wind_direction=[180.0, 190.0, 200.0],
            temperature=[20.0, 21.0, 22.0],
            pressure=[1013.0, 1012.0, 1011.0],
            cloud_cover=[10.0, 20.0, 30.0],
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert len(records) == 3
        assert records[0].true_wind_speed == 5.0
        assert records[1].true_wind_direction == 190.0
        assert records[2].temperature == 22.0
        assert records[0].pressure == 1013.0
        assert records[1].cloud_cover == 20.0

    def test_timezone_conversion(self):
        """LA summer (PDT, UTC-7): local 10:00 → UTC 17:00."""
        data = _make_response(
            times=["2024-07-15T10:00"],
            wind_speed=[5.0],
            wind_direction=[180.0],
            temperature=[20.0],
            pressure=[1013.0],
            cloud_cover=[10.0],
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert len(records) == 1
        utc_dt = records[0].valid_time_utc
        assert utc_dt.tzinfo == ZoneInfo("UTC")
        assert utc_dt.hour == 17  # PDT = UTC-7

        local_dt = records[0].valid_time_local
        assert local_dt.tzinfo is None
        assert local_dt.hour == 10

    def test_timezone_winter(self):
        """LA winter (PST, UTC-8): local 10:00 → UTC 18:00."""
        data = _make_response(
            times=["2024-01-15T10:00"],
            wind_speed=[3.0],
            wind_direction=[90.0],
            temperature=[10.0],
            pressure=[1015.0],
            cloud_cover=[50.0],
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert records[0].valid_time_utc.hour == 18  # PST = UTC-8

    def test_european_timezone(self):
        """Non-US timezone (Europe/Stockholm, CEST UTC+2): local 14:00 → UTC 12:00."""
        data = _make_response(
            times=["2024-07-15T14:00"],
            wind_speed=[4.0],
            wind_direction=[270.0],
            temperature=[25.0],
            pressure=[1010.0],
            cloud_cover=[0.0],
        )
        records = parse_open_meteo_response(data, "Europe/Stockholm")

        assert records[0].valid_time_utc.hour == 12  # CEST = UTC+2

    def test_none_values_in_fields(self):
        """None in weather arrays propagates as None in records."""
        data = _make_response(
            times=["2024-07-15T10:00", "2024-07-15T11:00"],
            wind_speed=[5.0, None],
            wind_direction=[None, 200.0],
            temperature=[20.0, None],
            pressure=[None, 1012.0],
            cloud_cover=[10.0, None],
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert records[0].true_wind_speed == 5.0
        assert records[1].true_wind_speed is None
        assert records[0].true_wind_direction is None
        assert records[1].true_wind_direction == 200.0
        assert records[1].temperature is None
        assert records[0].pressure is None
        assert records[1].cloud_cover is None

    def test_missing_fields_default_to_none(self):
        """Absent JSON keys (e.g. no wind_direction_10m) produce None in records."""
        data = _make_response(
            times=["2024-07-15T10:00"],
            wind_speed=[5.0],
            # wind_direction, temperature, pressure, cloud_cover omitted
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert len(records) == 1
        assert records[0].true_wind_speed == 5.0
        assert records[0].true_wind_direction is None
        assert records[0].temperature is None
        assert records[0].pressure is None
        assert records[0].cloud_cover is None

    def test_empty_hourly_data(self):
        """Empty time array → empty list."""
        data = _make_response(times=[])
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert records == []

    def test_missing_hourly_key(self):
        """No 'hourly' key → empty list."""
        records = parse_open_meteo_response({}, "America/Los_Angeles")

        assert records == []

    def test_multi_day_response(self):
        """48-hour (2-day) response parses all records with correct dates."""
        times = [f"2024-07-15T{h:02d}:00" for h in range(24)] + [
            f"2024-07-16T{h:02d}:00" for h in range(24)
        ]
        data = _make_response(
            times=times,
            wind_speed=[5.0] * 48,
            wind_direction=[180.0] * 48,
            temperature=[20.0] * 48,
            pressure=[1013.0] * 48,
            cloud_cover=[10.0] * 48,
        )
        records = parse_open_meteo_response(data, "America/Los_Angeles")

        assert len(records) == 48
        # First record: July 15 00:00 local
        assert records[0].valid_time_local == datetime(2024, 7, 15, 0, 0)
        # Last record: July 16 23:00 local
        assert records[-1].valid_time_local == datetime(2024, 7, 16, 23, 0)
