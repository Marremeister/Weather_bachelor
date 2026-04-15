"""Tests for feature_service — pure computation, no database required."""

import math
from datetime import date, datetime
from types import SimpleNamespace

import pytest

from app.schemas.features import AnalysisWindow
from app.services.feature_service import (
    circular_mean,
    compute_daily_features,
    direction_difference,
    is_in_sector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rec(hour: int, speed: float | None, direction: float | None):
    """Create a mock weather record with the given hour, speed, direction."""
    return SimpleNamespace(
        valid_time_local=datetime(2024, 7, 15, hour, 0),
        true_wind_speed=speed,
        true_wind_direction=direction,
    )


# Window with original 8-10 morning defaults, used by tests whose synthetic
# data was written for the old default window.
_OLD_WINDOW = AnalysisWindow(morning_start=8, morning_end=10, reference_hour=9)


# ---------------------------------------------------------------------------
# circular_mean
# ---------------------------------------------------------------------------

class TestCircularMean:
    def test_simple_average(self):
        result = circular_mean([10.0, 20.0, 30.0])
        assert abs(result - 20.0) < 0.1

    def test_wrap_around(self):
        # 350 and 10 should average to 0
        result = circular_mean([350.0, 10.0])
        assert abs(result - 0.0) < 0.1 or abs(result - 360.0) < 0.1

    def test_all_nan(self):
        result = circular_mean([float("nan"), float("nan")])
        assert math.isnan(result)

    def test_empty_list(self):
        result = circular_mean([])
        assert math.isnan(result)

    def test_filters_nan(self):
        result = circular_mean([90.0, float("nan"), 90.0])
        assert abs(result - 90.0) < 0.1


# ---------------------------------------------------------------------------
# direction_difference
# ---------------------------------------------------------------------------

class TestDirectionDifference:
    def test_positive(self):
        assert abs(direction_difference(90.0, 45.0) - 45.0) < 0.01

    def test_negative(self):
        assert abs(direction_difference(45.0, 90.0) - (-45.0)) < 0.01

    def test_wrap_clockwise(self):
        # 10 - 350 should be +20
        result = direction_difference(10.0, 350.0)
        assert abs(result - 20.0) < 0.01

    def test_wrap_counterclockwise(self):
        # 350 - 10 should be -20
        result = direction_difference(350.0, 10.0)
        assert abs(result - (-20.0)) < 0.01

    def test_nan_input(self):
        assert math.isnan(direction_difference(float("nan"), 10.0))
        assert math.isnan(direction_difference(10.0, float("nan")))


# ---------------------------------------------------------------------------
# is_in_sector
# ---------------------------------------------------------------------------

class TestIsInSector:
    def test_normal_range(self):
        assert is_in_sector(200.0, 180.0, 260.0) is True
        assert is_in_sector(100.0, 180.0, 260.0) is False

    def test_wrap_around(self):
        # Sector 350 -> 10
        assert is_in_sector(355.0, 350.0, 10.0) is True
        assert is_in_sector(5.0, 350.0, 10.0) is True
        assert is_in_sector(180.0, 350.0, 10.0) is False

    def test_boundary(self):
        assert is_in_sector(180.0, 180.0, 260.0) is True
        assert is_in_sector(260.0, 180.0, 260.0) is True

    def test_nan(self):
        assert is_in_sector(float("nan"), 180.0, 260.0) is False


# ---------------------------------------------------------------------------
# compute_daily_features
# ---------------------------------------------------------------------------

class TestComputeDailyFeatures:
    def test_full_sea_breeze_day(self):
        """Synthetic sea-breeze day with morning light/NW and afternoon strong/SW."""
        records = [
            # Morning: hours 8, 9, 10 — light wind from ~90 (east)
            _rec(8, 3.0, 90.0),
            _rec(9, 4.0, 85.0),
            _rec(10, 3.5, 95.0),
            # Afternoon: hours 11-16 — stronger wind from ~220 (SW, onshore)
            _rec(11, 7.0, 210.0),
            _rec(12, 8.0, 220.0),
            _rec(13, 9.0, 225.0),
            _rec(14, 10.0, 230.0),
            _rec(15, 9.5, 220.0),
            _rec(16, 8.5, 215.0),
        ]
        features = compute_daily_features(
            records, location_id=1, target_date=date(2024, 7, 15), window=_OLD_WINDOW,
        )

        assert features.location_id == 1
        assert features.date == date(2024, 7, 15)

        # Morning: mean speed ~ 3.5
        assert features.morning_mean_wind_speed is not None
        assert abs(features.morning_mean_wind_speed - 3.5) < 0.1

        # Morning direction ~ 90
        assert features.morning_mean_wind_direction is not None
        assert abs(features.morning_mean_wind_direction - 90.0) < 1.0

        # Reference hour 9: speed=4.0, dir=85.0
        assert features.reference_wind_speed == 4.0
        assert features.reference_wind_direction == 85.0

        # Afternoon max speed = 10.0
        assert features.afternoon_max_wind_speed == 10.0

        # Afternoon direction ~ 220
        assert features.afternoon_mean_wind_direction is not None
        assert abs(features.afternoon_mean_wind_direction - 220.0) < 2.0

        # Wind speed increase = 10.0 - 3.5 = 6.5
        assert features.wind_speed_increase is not None
        assert abs(features.wind_speed_increase - 6.5) < 0.1

        # Direction shift: ~220 - ~90 = ~130
        assert features.wind_direction_shift is not None
        assert abs(features.wind_direction_shift - 130.0) < 2.0

        # All afternoon directions are in [180, 260] -> onshore_fraction = 1.0
        assert features.onshore_fraction == 1.0

        assert features.hours_available == 9
        assert features.morning_hours_used == 3
        assert features.afternoon_hours_used == 6

    def test_missing_data_none_values(self):
        """Records with None speed/direction should be skipped."""
        records = [
            _rec(8, None, 90.0),
            _rec(9, 4.0, None),
            _rec(10, 3.0, 80.0),
            _rec(11, 7.0, 210.0),
            _rec(12, None, 220.0),
            _rec(13, 8.0, None),
            _rec(14, 9.0, 230.0),
            _rec(15, 6.0, 200.0),
            _rec(16, 7.0, 220.0),
        ]
        features = compute_daily_features(
            records, location_id=1, target_date=date(2024, 7, 15), window=_OLD_WINDOW,
        )

        # Morning: 2 speeds (4.0, 3.0), 2 dirs (90.0, 80.0) — meets min of 2
        assert features.morning_hours_used == 2
        assert features.morning_mean_wind_speed is not None
        assert abs(features.morning_mean_wind_speed - 3.5) < 0.01

        # Afternoon: 5 speeds (7,8,9,6,7 — hour 12 has None speed), 4 dirs — meets min of 3
        assert features.afternoon_hours_used == 5
        assert features.afternoon_max_wind_speed == 9.0

    def test_insufficient_data(self):
        """Not enough morning hours → morning features are None."""
        records = [
            _rec(8, 3.0, 90.0),  # Only 1 morning hour
            _rec(11, 7.0, 210.0),
            _rec(12, 8.0, 220.0),
            _rec(13, 9.0, 225.0),
        ]
        features = compute_daily_features(
            records, location_id=1, target_date=date(2024, 7, 15), window=_OLD_WINDOW,
        )

        assert features.morning_hours_used == 1
        assert features.morning_mean_wind_speed is None
        assert features.morning_mean_wind_direction is None

        # Afternoon has exactly 3 → meets min_afternoon_hours
        assert features.afternoon_hours_used == 3
        assert features.afternoon_max_wind_speed == 9.0

        # No morning → no derived speed increase / direction shift
        assert features.wind_speed_increase is None
        assert features.wind_direction_shift is None

    def test_empty_records(self):
        """Empty input → all None features, zero counts."""
        features = compute_daily_features([], location_id=1, target_date=date(2024, 7, 15))

        assert features.hours_available == 0
        assert features.morning_hours_used == 0
        assert features.afternoon_hours_used == 0
        assert features.morning_mean_wind_speed is None
        assert features.afternoon_max_wind_speed is None
        assert features.wind_speed_increase is None
        assert features.onshore_fraction is None

    def test_custom_window(self):
        """Custom AnalysisWindow changes which hours are included."""
        window = AnalysisWindow(
            morning_start=6,
            morning_end=8,
            afternoon_start=12,
            afternoon_end=14,
            reference_hour=7,
            min_morning_hours=2,
            min_afternoon_hours=2,
        )
        records = [
            _rec(6, 2.0, 90.0),
            _rec(7, 3.0, 100.0),
            _rec(8, 2.5, 95.0),
            _rec(12, 8.0, 220.0),
            _rec(13, 9.0, 230.0),
            _rec(14, 7.5, 210.0),
        ]
        features = compute_daily_features(
            records, location_id=2, target_date=date(2024, 7, 15), window=window
        )

        assert features.morning_hours_used == 3
        assert features.afternoon_hours_used == 3
        assert features.reference_wind_speed == 3.0
        assert features.reference_wind_direction == 100.0

    def test_partial_onshore_fraction(self):
        """Some afternoon directions inside sector, some outside."""
        records = [
            _rec(8, 3.0, 90.0),
            _rec(9, 3.0, 90.0),
            _rec(10, 3.0, 90.0),
            # Afternoon: 3 onshore (200, 220, 240) + 1 offshore (100)
            _rec(11, 7.0, 200.0),
            _rec(12, 7.0, 220.0),
            _rec(13, 7.0, 240.0),
            _rec(14, 7.0, 100.0),
        ]
        features = compute_daily_features(
            records, location_id=1, target_date=date(2024, 7, 15), window=_OLD_WINDOW,
        )

        # 3 out of 4 afternoon directions in [180, 260]
        assert features.onshore_fraction is not None
        assert abs(features.onshore_fraction - 0.75) < 0.01

    def test_speeds_without_directions(self):
        """Speed present but all directions None → direction fields stay None."""
        records = [
            _rec(8, 3.0, None),
            _rec(9, 4.0, None),
            _rec(10, 3.5, None),
            _rec(11, 7.0, None),
            _rec(12, 8.0, None),
            _rec(13, 9.0, None),
        ]
        features = compute_daily_features(
            records, location_id=1, target_date=date(2024, 7, 15), window=_OLD_WINDOW,
        )

        # Speed features should still be computed
        assert features.morning_hours_used == 3
        assert features.afternoon_hours_used == 3
        assert features.morning_mean_wind_speed is not None
        assert abs(features.morning_mean_wind_speed - 3.5) < 0.01
        assert features.afternoon_max_wind_speed == 9.0
        assert features.wind_speed_increase is not None

        # Direction features must be None, not NaN or 0.0
        assert features.morning_mean_wind_direction is None
        assert features.afternoon_mean_wind_direction is None
        assert features.wind_direction_shift is None
        assert features.onshore_fraction is None
