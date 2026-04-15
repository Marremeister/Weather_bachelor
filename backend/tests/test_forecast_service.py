"""Tests for forecast_service — pure composite functions + circular stats."""

import math

import pytest

from app.services.feature_service import circular_arc_radius, circular_std
from app.services.forecast_service import build_composite, composite_hour


# ---------------------------------------------------------------------------
# circular_std
# ---------------------------------------------------------------------------

class TestCircularStd:
    def test_identical_directions(self):
        """All same direction → std should be ~0."""
        result = circular_std([180.0, 180.0, 180.0])
        assert result == 0.0

    def test_spread_directions(self):
        """Spread-out directions → positive std."""
        result = circular_std([0.0, 90.0, 180.0, 270.0])
        assert result > 0
        # Uniformly spread → maximal std (near 180)
        assert result <= 180.0

    def test_empty(self):
        result = circular_std([])
        assert math.isnan(result)

    def test_wrap_around(self):
        """350 and 10 are close together → small std."""
        result = circular_std([350.0, 10.0])
        assert result < 30.0

    def test_capped_at_180(self):
        """Std should never exceed 180."""
        result = circular_std([0.0, 90.0, 180.0, 270.0])
        assert result <= 180.0


# ---------------------------------------------------------------------------
# circular_arc_radius
# ---------------------------------------------------------------------------

class TestCircularArcRadius:
    def test_tight_cluster(self):
        """Tight cluster → small arc radius."""
        result = circular_arc_radius([100.0, 102.0, 98.0, 101.0, 99.0])
        assert result < 10.0
        assert result >= 0.0

    def test_empty(self):
        result = circular_arc_radius([])
        assert math.isnan(result)

    def test_wider_spread(self):
        """Wider spread → larger arc radius."""
        tight = circular_arc_radius([100.0, 102.0, 98.0])
        wide = circular_arc_radius([100.0, 140.0, 60.0])
        assert wide > tight


# ---------------------------------------------------------------------------
# composite_hour
# ---------------------------------------------------------------------------

class TestCompositeHour:
    def test_basic_composite(self):
        """Basic composite with both TWS and TWD."""
        tws = [5.0, 6.0, 7.0, 8.0, 9.0]
        twd = [200.0, 210.0, 220.0, 215.0, 205.0]
        result = composite_hour(tws, twd)

        assert result is not None
        assert result["median_tws"] == 7.0
        assert result["p25_tws"] is not None
        assert result["p75_tws"] is not None
        assert result["p10_tws"] is not None
        assert result["p90_tws"] is not None
        assert result["analog_count"] == 5
        # TWD should be near 210
        assert result["circular_mean_twd"] is not None
        assert abs(result["circular_mean_twd"] - 210.0) < 5.0
        assert result["twd_circular_std"] is not None
        assert result["twd_arc_radius_75"] is not None

    def test_empty_tws(self):
        """No TWS data → None result."""
        result = composite_hour([], [200.0, 210.0])
        assert result is None

    def test_missing_twd(self):
        """TWS present but no TWD → TWD fields are None."""
        result = composite_hour([5.0, 6.0], [])
        assert result is not None
        assert result["median_tws"] is not None
        assert result["circular_mean_twd"] is None
        assert result["twd_circular_std"] is None
        assert result["twd_arc_radius_75"] is None

    def test_single_value(self):
        """Single value should still produce a valid composite."""
        result = composite_hour([10.0], [180.0])
        assert result is not None
        assert result["median_tws"] == 10.0
        assert result["analog_count"] == 1


# ---------------------------------------------------------------------------
# build_composite
# ---------------------------------------------------------------------------

class TestBuildComposite:
    def test_two_analog_days(self):
        """Two analog days with data for forecast hours."""
        day1 = {
            11: {"tws": 5.0, "twd": 200.0},
            12: {"tws": 6.0, "twd": 210.0},
            13: {"tws": 7.0, "twd": 220.0},
            14: {"tws": 8.0, "twd": 225.0},
            15: {"tws": 7.5, "twd": 215.0},
            16: {"tws": 6.5, "twd": 205.0},
        }
        day2 = {
            11: {"tws": 4.0, "twd": 190.0},
            12: {"tws": 5.0, "twd": 200.0},
            13: {"tws": 6.0, "twd": 210.0},
            14: {"tws": 7.0, "twd": 220.0},
            15: {"tws": 6.5, "twd": 210.0},
            16: {"tws": 5.5, "twd": 200.0},
        }

        result = build_composite([day1, day2])

        assert len(result) == 6
        assert result[0]["hour_local"] == 11
        assert result[5]["hour_local"] == 16
        # Each hour should have analog_count == 2
        for h in result:
            assert h["analog_count"] == 2

    def test_filters_non_forecast_hours(self):
        """Hours outside 11-16 should not appear in output."""
        day = {
            8: {"tws": 3.0, "twd": 90.0},
            9: {"tws": 3.5, "twd": 95.0},
            11: {"tws": 5.0, "twd": 200.0},
            12: {"tws": 6.0, "twd": 210.0},
        }
        result = build_composite([day])

        hours_in_result = [h["hour_local"] for h in result]
        assert 8 not in hours_in_result
        assert 9 not in hours_in_result
        assert 11 in hours_in_result
        assert 12 in hours_in_result

    def test_empty_input(self):
        """No analog data → empty output."""
        result = build_composite([])
        assert result == []

    def test_partial_coverage(self):
        """Days with missing hours still contribute to available hours."""
        day1 = {11: {"tws": 5.0, "twd": 200.0}}
        day2 = {12: {"tws": 6.0, "twd": 210.0}}

        result = build_composite([day1, day2])
        hours_in_result = {h["hour_local"] for h in result}
        assert 11 in hours_in_result
        assert 12 in hours_in_result
        # Each only has 1 analog contributing
        for h in result:
            assert h["analog_count"] == 1
