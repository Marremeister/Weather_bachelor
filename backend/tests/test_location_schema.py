"""Tests for LocationResponse schema — pure Pydantic validation, no DB required."""

from datetime import datetime
from types import SimpleNamespace

from app.schemas.location import LocationResponse


class TestLocationResponse:
    def test_from_orm_like_object(self):
        """model_validate reads attributes from a SimpleNamespace (simulates ORM row)."""
        obj = SimpleNamespace(
            id=1,
            name="Gothenburg",
            latitude=57.707,
            longitude=11.967,
            timezone="Europe/Stockholm",
            created_at=datetime(2024, 1, 15, 12, 0, 0),
        )
        resp = LocationResponse.model_validate(obj)

        assert resp.id == 1
        assert resp.name == "Gothenburg"
        assert resp.latitude == 57.707
        assert resp.longitude == 11.967
        assert resp.timezone == "Europe/Stockholm"
        assert resp.created_at == datetime(2024, 1, 15, 12, 0, 0)

    def test_serialization_round_trip(self):
        """model_dump returns expected keys and types."""
        obj = SimpleNamespace(
            id=2,
            name="Los Angeles",
            latitude=34.052,
            longitude=-118.244,
            timezone="America/Los_Angeles",
            created_at=datetime(2024, 6, 1, 8, 30, 0),
        )
        resp = LocationResponse.model_validate(obj)
        data = resp.model_dump()

        assert set(data.keys()) == {
            "id", "name", "latitude", "longitude", "timezone", "created_at",
        }
        assert isinstance(data["id"], int)
        assert isinstance(data["name"], str)
        assert isinstance(data["latitude"], float)
        assert isinstance(data["longitude"], float)
        assert isinstance(data["timezone"], str)
        assert isinstance(data["created_at"], datetime)
