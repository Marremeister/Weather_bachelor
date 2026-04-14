"""Tests for weather_service pure helpers — no DB required."""

from datetime import date
from pathlib import Path
from unittest.mock import patch

from app.services.weather_service import _cache_path, _expected_hours


# ---------------------------------------------------------------------------
# _expected_hours
# ---------------------------------------------------------------------------

class TestExpectedHours:
    def test_single_day(self):
        """start == end → 24 hours."""
        assert _expected_hours(date(2024, 7, 15), date(2024, 7, 15)) == 24

    def test_two_days(self):
        """2 consecutive days → 48 hours."""
        assert _expected_hours(date(2024, 7, 15), date(2024, 7, 16)) == 48

    def test_one_week(self):
        """7 days → 168 hours."""
        assert _expected_hours(date(2024, 7, 15), date(2024, 7, 21)) == 168

    def test_full_year(self):
        """366 days (2024 leap year) → 8784 hours."""
        assert _expected_hours(date(2024, 1, 1), date(2024, 12, 31)) == 8784

    def test_same_date(self):
        """Degenerate case: same date confirms 24."""
        assert _expected_hours(date(2024, 1, 1), date(2024, 1, 1)) == 24


# ---------------------------------------------------------------------------
# _cache_path
# ---------------------------------------------------------------------------

class TestCachePath:
    @patch("app.services.weather_service.settings")
    def test_basic_structure(self, mock_settings):
        """Path follows {cache_dir}/{source}/{lat}_{lng}/{start}__{end}.json."""
        mock_settings.weather_cache_dir = "/tmp/cache"
        result = _cache_path("open_meteo", 34.052, -118.244, date(2024, 7, 1), date(2024, 7, 7))

        assert result == Path("/tmp/cache/open_meteo/34.052_-118.244/2024-07-01__2024-07-07.json")

    @patch("app.services.weather_service.settings")
    def test_lat_lng_rounding(self, mock_settings):
        """Coordinates rounded to 3 decimal places."""
        mock_settings.weather_cache_dir = "/tmp/cache"
        result = _cache_path("open_meteo", 34.05234567, -118.24412345, date(2024, 7, 1), date(2024, 7, 7))

        assert "34.052" in str(result)
        assert "-118.244" in str(result)

    @patch("app.services.weather_service.settings")
    def test_different_source(self, mock_settings):
        """Different source names → different paths."""
        mock_settings.weather_cache_dir = "/tmp/cache"
        path_a = _cache_path("open_meteo", 34.0, -118.0, date(2024, 7, 1), date(2024, 7, 7))
        path_b = _cache_path("smhi", 34.0, -118.0, date(2024, 7, 1), date(2024, 7, 7))

        assert path_a != path_b
        assert "open_meteo" in str(path_a)
        assert "smhi" in str(path_b)

    @patch("app.services.weather_service.settings")
    def test_returns_path_object(self, mock_settings):
        """Return type is pathlib.Path."""
        mock_settings.weather_cache_dir = "/tmp/cache"
        result = _cache_path("open_meteo", 34.0, -118.0, date(2024, 7, 1), date(2024, 7, 7))

        assert isinstance(result, Path)

    @patch("app.services.weather_service.settings")
    def test_filename_format(self, mock_settings):
        """Filename uses double-underscore separator and .json extension."""
        mock_settings.weather_cache_dir = "/tmp/cache"
        result = _cache_path("open_meteo", 34.0, -118.0, date(2024, 7, 1), date(2024, 7, 7))

        assert result.name == "2024-07-01__2024-07-07.json"
        assert result.suffix == ".json"
