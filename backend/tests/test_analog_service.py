"""Tests for analog_service — pure computation, no database required."""

import math
from datetime import date

import numpy as np
import pytest

from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.analog_service import (
    build_weight_vector,
    compute_distances,
    features_to_vector,
    is_valid_for_analog,
    rank_analogs,
    standardize,
    yearly_chunks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _features(**kwargs) -> DailyFeatures:
    """Build a DailyFeatures with sensible defaults for all 9 analog fields."""
    defaults = dict(
        location_id=1,
        date=date(2024, 7, 15),
        morning_mean_wind_speed=3.0,
        morning_mean_wind_direction=90.0,
        reference_wind_speed=4.0,
        reference_wind_direction=85.0,
        afternoon_max_wind_speed=10.0,
        afternoon_mean_wind_direction=220.0,
        wind_speed_increase=7.0,
        wind_direction_shift=130.0,
        onshore_fraction=1.0,
    )
    defaults.update(kwargs)
    return DailyFeatures(**defaults)


_ALL_WEIGHTS_WINDOW = AnalysisWindow(
    morning_weight=1.0,
    reference_weight=1.0,
    afternoon_weight=1.0,
    derived_weight=1.0,
)


# ---------------------------------------------------------------------------
# build_weight_vector
# ---------------------------------------------------------------------------

class TestBuildWeightVector:
    def test_default_weights(self):
        w = build_weight_vector(AnalysisWindow())
        expected = np.array([1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=np.float64)
        np.testing.assert_array_equal(w, expected)

    def test_all_ones(self):
        w = build_weight_vector(_ALL_WEIGHTS_WINDOW)
        np.testing.assert_array_equal(w, np.ones(12))

    def test_custom_weights(self):
        window = AnalysisWindow(
            morning_weight=2.0,
            reference_weight=0.5,
            afternoon_weight=0.0,
            derived_weight=3.0,
        )
        w = build_weight_vector(window)
        expected = np.array([2, 2, 2, 0.5, 0.5, 0.5, 0, 0, 0, 3, 3, 3], dtype=np.float64)
        np.testing.assert_array_equal(w, expected)


# ---------------------------------------------------------------------------
# features_to_vector
# ---------------------------------------------------------------------------

class TestFeaturesToVector:
    def test_correct_length(self):
        vec = features_to_vector(_features())
        assert len(vec) == 12

    def test_scalar_positions(self):
        feat = _features(
            morning_mean_wind_speed=3.0,
            reference_wind_speed=4.0,
            afternoon_max_wind_speed=10.0,
            wind_speed_increase=7.0,
            wind_direction_shift=130.0,
            onshore_fraction=1.0,
        )
        vec = features_to_vector(feat)
        assert vec[0] == 3.0    # morning_mean_wind_speed
        assert vec[3] == 4.0    # reference_wind_speed
        assert vec[6] == 10.0   # afternoon_max_wind_speed
        assert vec[9] == 7.0    # wind_speed_increase
        assert vec[10] == 130.0  # wind_direction_shift
        assert vec[11] == 1.0   # onshore_fraction

    def test_sincos_at_0_degrees(self):
        feat = _features(morning_mean_wind_direction=0.0)
        vec = features_to_vector(feat)
        # sin(0)=0, cos(0)=1
        assert abs(vec[1] - 0.0) < 1e-10
        assert abs(vec[2] - 1.0) < 1e-10

    def test_sincos_at_90_degrees(self):
        feat = _features(reference_wind_direction=90.0)
        vec = features_to_vector(feat)
        # sin(90)=1, cos(90)=0
        assert abs(vec[4] - 1.0) < 1e-10
        assert abs(vec[5] - 0.0) < 1e-10

    def test_sincos_at_270_degrees(self):
        feat = _features(afternoon_mean_wind_direction=270.0)
        vec = features_to_vector(feat)
        # sin(270)=-1, cos(270)=0
        assert abs(vec[7] - (-1.0)) < 1e-10
        assert abs(vec[8] - 0.0) < 1e-10


# ---------------------------------------------------------------------------
# is_valid_for_analog
# ---------------------------------------------------------------------------

class TestIsValidForAnalog:
    def test_valid(self):
        assert is_valid_for_analog(_features()) is True

    def test_missing_field(self):
        feat = _features(morning_mean_wind_speed=None)
        assert is_valid_for_analog(feat) is False

    def test_nan_field(self):
        """wind_direction_shift is a derived field; need derived_weight > 0 to check it."""
        feat = _features(wind_direction_shift=float("nan"))
        window = AnalysisWindow(derived_weight=1.0)
        assert is_valid_for_analog(feat, window) is False

    def test_all_none(self):
        feat = DailyFeatures(location_id=1, date=date(2024, 7, 15))
        assert is_valid_for_analog(feat) is False

    def test_missing_afternoon_ok_with_zero_weight(self):
        """Days missing afternoon data are valid when afternoon_weight=0."""
        feat = _features(afternoon_max_wind_speed=None, afternoon_mean_wind_direction=None)
        assert is_valid_for_analog(feat) is True  # default afternoon_weight=0

    def test_missing_derived_ok_with_zero_weight(self):
        """Days missing derived data are valid when derived_weight=0."""
        feat = _features(wind_speed_increase=None, wind_direction_shift=None, onshore_fraction=None)
        assert is_valid_for_analog(feat) is True  # default derived_weight=0

    def test_missing_afternoon_fails_with_nonzero_weight(self):
        feat = _features(afternoon_max_wind_speed=None)
        window = AnalysisWindow(afternoon_weight=1.0)
        assert is_valid_for_analog(feat, window) is False


# ---------------------------------------------------------------------------
# standardize
# ---------------------------------------------------------------------------

class TestStandardize:
    def test_known_matrix(self):
        # Two rows, two features: [1,2] and [3,4]
        m = np.array([[1.0, 2.0], [3.0, 4.0]])
        scaled, means, stds = standardize(m)

        np.testing.assert_allclose(means, [2.0, 3.0])
        np.testing.assert_allclose(stds, [1.0, 1.0])
        np.testing.assert_allclose(scaled, [[-1.0, -1.0], [1.0, 1.0]])

    def test_zero_variance_column(self):
        m = np.array([[5.0, 1.0], [5.0, 3.0]])
        scaled, means, stds = standardize(m)

        # First column has zero variance → std=0, scaled should be 0
        assert stds[0] == 0.0
        np.testing.assert_allclose(scaled[:, 0], [0.0, 0.0])

    def test_single_row(self):
        m = np.array([[2.0, 4.0]])
        scaled, means, stds = standardize(m)
        # Single row → std=0 for all columns → scaled = 0
        np.testing.assert_allclose(scaled, [[0.0, 0.0]])


# ---------------------------------------------------------------------------
# compute_distances
# ---------------------------------------------------------------------------

class TestComputeDistances:
    def test_identical_vector(self):
        target = np.array([1.0, 2.0, 3.0])
        historical = np.array([[1.0, 2.0, 3.0]])
        means = np.array([1.0, 2.0, 3.0])
        stds = np.array([1.0, 1.0, 1.0])

        dists = compute_distances(target, historical, means, stds)
        assert abs(dists[0]) < 1e-10

    def test_known_distance(self):
        target = np.array([0.0, 0.0])
        historical = np.array([[3.0, 4.0]])
        means = np.array([0.0, 0.0])
        stds = np.array([1.0, 1.0])

        dists = compute_distances(target, historical, means, stds)
        assert abs(dists[0] - 5.0) < 1e-10

    def test_multiple_candidates(self):
        target = np.array([0.0, 0.0])
        historical = np.array([[1.0, 0.0], [0.0, 2.0], [3.0, 4.0]])
        means = np.array([0.0, 0.0])
        stds = np.array([1.0, 1.0])

        dists = compute_distances(target, historical, means, stds)
        assert len(dists) == 3
        assert abs(dists[0] - 1.0) < 1e-10
        assert abs(dists[1] - 2.0) < 1e-10
        assert abs(dists[2] - 5.0) < 1e-10

    def test_weighted_distance(self):
        """Zeroing a weight should eliminate that dimension's contribution."""
        target = np.array([0.0, 0.0])
        historical = np.array([[3.0, 4.0]])
        means = np.array([0.0, 0.0])
        stds = np.array([1.0, 1.0])

        # Without weights: distance = 5
        d_unweighted = compute_distances(target, historical, means, stds)
        assert abs(d_unweighted[0] - 5.0) < 1e-10

        # Zero out first dimension: only second dimension matters → distance = 4
        weights = np.array([0.0, 1.0])
        d_weighted = compute_distances(target, historical, means, stds, weights=weights)
        assert abs(d_weighted[0] - 4.0) < 1e-10


# ---------------------------------------------------------------------------
# rank_analogs
# ---------------------------------------------------------------------------

class TestRankAnalogs:
    def test_basic_ranking(self):
        target = _features()
        # Near-identical day → should be rank 1
        close = _features(date=date(2024, 6, 1), morning_mean_wind_speed=3.1)
        # More different → should be rank 2
        far = _features(date=date(2024, 5, 1), morning_mean_wind_speed=8.0)

        candidates = rank_analogs(target, [far, close], top_n=10)
        assert len(candidates) == 2
        assert candidates[0].date == date(2024, 6, 1)
        assert candidates[0].rank == 1
        assert candidates[1].date == date(2024, 5, 1)
        assert candidates[1].rank == 2

    def test_filters_invalid_days(self):
        target = _features()
        valid = _features(date=date(2024, 6, 1))
        invalid = _features(date=date(2024, 5, 1), morning_mean_wind_speed=None)

        candidates = rank_analogs(target, [valid, invalid], top_n=10)
        assert len(candidates) == 1
        assert candidates[0].date == date(2024, 6, 1)

    def test_similarity_score(self):
        target = _features()
        identical = _features(date=date(2024, 6, 1))

        candidates = rank_analogs(target, [identical], top_n=10)
        assert len(candidates) == 1
        # Identical feature values across all historical data → distance=0 → score=1
        assert abs(candidates[0].similarity_score - 1.0) < 1e-6
        assert abs(candidates[0].distance) < 1e-6

    def test_empty_historical(self):
        target = _features()
        assert rank_analogs(target, [], top_n=10) == []

    def test_invalid_target(self):
        target = _features(morning_mean_wind_speed=None)
        hist = [_features(date=date(2024, 6, 1))]
        assert rank_analogs(target, hist, top_n=10) == []

    def test_top_n_limit(self):
        target = _features()
        historical = [
            _features(date=date(2024, 1, i + 1), morning_mean_wind_speed=3.0 + i * 0.1)
            for i in range(20)
        ]
        candidates = rank_analogs(target, historical, top_n=5)
        assert len(candidates) == 5
        # Ranks should be 1-5
        assert [c.rank for c in candidates] == [1, 2, 3, 4, 5]

    def test_similarity_score_range(self):
        """Similarity score should be in (0, 1]."""
        target = _features()
        far = _features(date=date(2024, 6, 1), morning_mean_wind_speed=100.0)

        candidates = rank_analogs(target, [far], top_n=10)
        assert len(candidates) == 1
        assert 0 < candidates[0].similarity_score <= 1.0

    def test_opposite_direction_shift_not_equal(self):
        """Days with opposite wind_direction_shift must have nonzero distance."""
        target = _features(wind_direction_shift=130.0)
        same_shift = _features(date=date(2024, 6, 1), wind_direction_shift=130.0)
        opposite_shift = _features(date=date(2024, 5, 1), wind_direction_shift=-130.0)

        # Need derived_weight > 0 to make direction_shift matter
        window = _ALL_WEIGHTS_WINDOW
        candidates = rank_analogs(target, [same_shift, opposite_shift], top_n=10, window=window)
        assert len(candidates) == 2
        # same_shift should be closer (rank 1)
        assert candidates[0].date == date(2024, 6, 1)
        assert candidates[0].distance < candidates[1].distance
        # opposite_shift must have nonzero distance
        assert candidates[1].distance > 0.0

    def test_afternoon_differences_ignored_with_default_weights(self):
        """With default weights (afternoon=0, derived=0), afternoon differences don't affect distance."""
        target = _features()
        # Same morning/reference but very different afternoon
        same_morning = _features(
            date=date(2024, 6, 1),
            afternoon_max_wind_speed=100.0,
            afternoon_mean_wind_direction=0.0,
            wind_speed_increase=97.0,
            wind_direction_shift=-90.0,
            onshore_fraction=0.0,
        )
        # Identical day
        identical = _features(date=date(2024, 5, 1))

        candidates = rank_analogs(target, [same_morning, identical], top_n=10)
        assert len(candidates) == 2
        # Both should have distance 0 since only morning+reference matter
        assert abs(candidates[0].distance) < 1e-6
        assert abs(candidates[1].distance) < 1e-6


# ---------------------------------------------------------------------------
# yearly_chunks
# ---------------------------------------------------------------------------

class TestYearlyChunks:
    def test_single_year(self):
        chunks = yearly_chunks(date(2024, 3, 1), date(2024, 9, 30))
        assert chunks == [(date(2024, 3, 1), date(2024, 9, 30))]

    def test_multi_year(self):
        chunks = yearly_chunks(date(2022, 6, 1), date(2024, 6, 30))
        assert len(chunks) == 3
        assert chunks[0] == (date(2022, 6, 1), date(2022, 12, 31))
        assert chunks[1] == (date(2023, 1, 1), date(2023, 12, 31))
        assert chunks[2] == (date(2024, 1, 1), date(2024, 6, 30))

    def test_partial_year_boundaries(self):
        chunks = yearly_chunks(date(2023, 11, 15), date(2024, 2, 10))
        assert len(chunks) == 2
        assert chunks[0] == (date(2023, 11, 15), date(2023, 12, 31))
        assert chunks[1] == (date(2024, 1, 1), date(2024, 2, 10))

    def test_same_day(self):
        chunks = yearly_chunks(date(2024, 7, 15), date(2024, 7, 15))
        assert chunks == [(date(2024, 7, 15), date(2024, 7, 15))]

    def test_full_year(self):
        chunks = yearly_chunks(date(2024, 1, 1), date(2024, 12, 31))
        assert chunks == [(date(2024, 1, 1), date(2024, 12, 31))]
