"""Tests for classification_service — pure computation, no database required."""

import math
from datetime import date

import pytest

from app.schemas.features import DailyFeatures, SeaBreezeThresholds
from app.services.classification_service import classify_sea_breeze


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _features(**kwargs) -> DailyFeatures:
    """Create DailyFeatures with sensible defaults, overriding with kwargs."""
    defaults = dict(location_id=1, date=date(2024, 7, 15))
    defaults.update(kwargs)
    return DailyFeatures(**defaults)


# ---------------------------------------------------------------------------
# TestClassifyHigh — all 3 indicators met
# ---------------------------------------------------------------------------

class TestClassifyHigh:
    def test_all_indicators_met(self):
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=40.0,
            onshore_fraction=0.8,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "high"
        assert result.score == pytest.approx(1.0)
        assert all(result.indicators.values())

    def test_exact_boundary_values(self):
        """Exactly at default thresholds: 1.5 mps, 25 deg, 0.5 fraction."""
        features = _features(
            wind_speed_increase=1.5,
            wind_direction_shift=25.0,
            onshore_fraction=0.5,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "high"
        assert result.score == pytest.approx(1.0)
        assert result.indicators["speed_increase"] is True
        assert result.indicators["direction_shift"] is True
        assert result.indicators["onshore_fraction"] is True


# ---------------------------------------------------------------------------
# TestClassifyMedium — exactly 2 indicators
# ---------------------------------------------------------------------------

class TestClassifyMedium:
    def test_speed_and_direction_only(self):
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=40.0,
            onshore_fraction=0.2,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "medium"
        assert result.score == pytest.approx(2 / 3)

    def test_speed_and_onshore_only(self):
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=10.0,
            onshore_fraction=0.8,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "medium"
        assert result.score == pytest.approx(2 / 3)

    def test_direction_and_onshore_only(self):
        features = _features(
            wind_speed_increase=0.5,
            wind_direction_shift=40.0,
            onshore_fraction=0.8,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "medium"
        assert result.score == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# TestClassifyLow — 0 or 1 indicator
# ---------------------------------------------------------------------------

class TestClassifyLow:
    def test_no_indicators(self):
        features = _features(
            wind_speed_increase=0.5,
            wind_direction_shift=10.0,
            onshore_fraction=0.2,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(0.0)

    def test_one_indicator_speed(self):
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=10.0,
            onshore_fraction=0.2,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(1 / 3)

    def test_one_indicator_direction(self):
        features = _features(
            wind_speed_increase=0.5,
            wind_direction_shift=40.0,
            onshore_fraction=0.2,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(1 / 3)

    def test_one_indicator_onshore(self):
        features = _features(
            wind_speed_increase=0.5,
            wind_direction_shift=10.0,
            onshore_fraction=0.8,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(1 / 3)


# ---------------------------------------------------------------------------
# TestNoneFeatures — None values treated as not met
# ---------------------------------------------------------------------------

class TestNoneFeatures:
    def test_all_none(self):
        features = _features()
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(0.0)
        assert not any(result.indicators.values())

    def test_some_none(self):
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=None,
            onshore_fraction=None,
        )
        result = classify_sea_breeze(features)
        assert result.classification == "low"
        assert result.score == pytest.approx(1 / 3)
        assert result.indicators["speed_increase"] is True
        assert result.indicators["direction_shift"] is False
        assert result.indicators["onshore_fraction"] is False


# ---------------------------------------------------------------------------
# TestNegativeDirectionShift — abs() is used
# ---------------------------------------------------------------------------

class TestNegativeDirectionShift:
    def test_negative_shift_meets_threshold(self):
        features = _features(wind_direction_shift=-30.0)
        result = classify_sea_breeze(features)
        assert result.indicators["direction_shift"] is True

    def test_negative_shift_below_threshold(self):
        features = _features(wind_direction_shift=-10.0)
        result = classify_sea_breeze(features)
        assert result.indicators["direction_shift"] is False


# ---------------------------------------------------------------------------
# TestCustomThresholds
# ---------------------------------------------------------------------------

class TestCustomThresholds:
    def test_stricter_thresholds(self):
        thresholds = SeaBreezeThresholds(
            minimum_speed_increase_mps=5.0,
            minimum_direction_shift_degrees=50.0,
            minimum_onshore_fraction=0.8,
        )
        features = _features(
            wind_speed_increase=3.0,
            wind_direction_shift=40.0,
            onshore_fraction=0.7,
        )
        result = classify_sea_breeze(features, thresholds)
        assert result.classification == "low"
        assert result.score == pytest.approx(0.0)

    def test_relaxed_thresholds(self):
        thresholds = SeaBreezeThresholds(
            minimum_speed_increase_mps=0.5,
            minimum_direction_shift_degrees=5.0,
            minimum_onshore_fraction=0.1,
        )
        features = _features(
            wind_speed_increase=1.0,
            wind_direction_shift=10.0,
            onshore_fraction=0.2,
        )
        result = classify_sea_breeze(features, thresholds)
        assert result.classification == "high"
        assert result.score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestNanDirectionShift — NaN treated as not met
# ---------------------------------------------------------------------------

class TestNanDirectionShift:
    def test_nan_shift(self):
        features = _features(wind_direction_shift=float("nan"))
        result = classify_sea_breeze(features)
        assert result.indicators["direction_shift"] is False
