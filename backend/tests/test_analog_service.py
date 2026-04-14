"""Tests for analog_service — pure computation, no database required."""

import math
from datetime import date

import numpy as np
import pytest

from app.schemas.features import DailyFeatures
from app.services.analog_service import (
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


# ---------------------------------------------------------------------------
# features_to_vector
# ---------------------------------------------------------------------------

class TestFeaturesToVector:
    def test_correct_length(self):
        vec = features_to_vector(_features())
        assert len(vec) == 11

    def test_scalar_positions(self):
        feat = _features(
            morning_mean_wind_speed=3.0,
            reference_wind_speed=4.0,
            afternoon_max_wind_speed=10.0,
            wind_speed_increase=7.0,
            onshore_fraction=1.0,
        )
        vec = features_to_vector(feat)
        assert vec[0] == 3.0   # morning_mean_wind_speed
        assert vec[3] == 4.0   # reference_wind_speed
        assert vec[6] == 10.0  # afternoon_max_wind_speed
        assert vec[9] == 7.0   # wind_speed_increase
        assert vec[10] == 1.0  # onshore_fraction

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
        feat = _features(wind_direction_shift=float("nan"))
        assert is_valid_for_analog(feat) is False

    def test_all_none(self):
        feat = DailyFeatures(location_id=1, date=date(2024, 7, 15))
        assert is_valid_for_analog(feat) is False


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
