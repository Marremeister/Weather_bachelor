"""Tests for weather request/response schemas — pure Pydantic validation, no DB required."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.weather import WeatherFetchRequest, WeatherRecordResponse


class TestWeatherFetchRequest:
    def test_valid_request(self):
        """Parses string dates into date objects."""
        req = WeatherFetchRequest(
            location_id=1,
            start_date="2024-07-01",
            end_date="2024-07-07",
        )
        assert req.location_id == 1
        assert req.start_date == date(2024, 7, 1)
        assert req.end_date == date(2024, 7, 7)

    def test_invalid_date_format(self):
        """Invalid date string raises ValidationError."""
        with pytest.raises(ValidationError):
            WeatherFetchRequest(
                location_id=1,
                start_date="not-a-date",
                end_date="2024-07-07",
            )

    def test_missing_required_field(self):
        """Missing end_date raises ValidationError."""
        with pytest.raises(ValidationError):
            WeatherFetchRequest(
                location_id=1,
                start_date="2024-07-01",
            )


class TestWeatherRecordResponse:
    def test_from_orm_like_object(self):
        """model_validate reads ORM-like attributes."""
        obj = SimpleNamespace(
            id=42,
            location_id=1,
            source="open_meteo",
            valid_time_utc=datetime(2024, 7, 15, 17, 0, 0),
            valid_time_local=datetime(2024, 7, 15, 10, 0, 0),
            true_wind_speed=5.5,
            true_wind_direction=180.0,
            temperature=22.3,
            pressure=1013.25,
            cloud_cover=15.0,
        )
        resp = WeatherRecordResponse.model_validate(obj)

        assert resp.id == 42
        assert resp.location_id == 1
        assert resp.source == "open_meteo"
        assert resp.valid_time_utc == datetime(2024, 7, 15, 17, 0, 0)
        assert resp.valid_time_local == datetime(2024, 7, 15, 10, 0, 0)
        assert resp.true_wind_speed == 5.5
        assert resp.true_wind_direction == 180.0
        assert resp.temperature == 22.3
        assert resp.pressure == 1013.25
        assert resp.cloud_cover == 15.0

    def test_nullable_fields(self):
        """None weather fields are accepted."""
        obj = SimpleNamespace(
            id=43,
            location_id=1,
            source="open_meteo",
            valid_time_utc=datetime(2024, 7, 15, 17, 0, 0),
            valid_time_local=datetime(2024, 7, 15, 10, 0, 0),
            true_wind_speed=None,
            true_wind_direction=None,
            temperature=None,
            pressure=None,
            cloud_cover=None,
        )
        resp = WeatherRecordResponse.model_validate(obj)

        assert resp.true_wind_speed is None
        assert resp.true_wind_direction is None
        assert resp.temperature is None
        assert resp.pressure is None
        assert resp.cloud_cover is None
