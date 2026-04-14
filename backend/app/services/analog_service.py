"""Analog matching: compare a target day against historical days by meteorological similarity."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.weather_record import WeatherRecord
from app.schemas.analog import AnalogCandidate
from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.feature_service import compute_daily_features
from app.services.open_meteo_provider import OpenMeteoProvider
from app.services.weather_service import fetch_weather

logger = logging.getLogger(__name__)

# The 9 base feature fields required for a valid analog candidate.
_REQUIRED_FIELDS = (
    "morning_mean_wind_speed",
    "morning_mean_wind_direction",
    "reference_wind_speed",
    "reference_wind_direction",
    "afternoon_max_wind_speed",
    "afternoon_mean_wind_direction",
    "wind_speed_increase",
    "wind_direction_shift",
    "onshore_fraction",
)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def features_to_vector(features: DailyFeatures) -> list[float]:
    """Convert a DailyFeatures instance to an 11-dimensional vector.

    Wind directions are decomposed into sin/cos pairs so Euclidean distance
    handles circular data correctly.  The resulting order is:

        [morning_mean_wind_speed,
         sin(morning_mean_wind_direction), cos(morning_mean_wind_direction),
         reference_wind_speed,
         sin(reference_wind_direction), cos(reference_wind_direction),
         afternoon_max_wind_speed,
         sin(afternoon_mean_wind_direction), cos(afternoon_mean_wind_direction),
         wind_speed_increase,
         onshore_fraction]
    """

    def _sincos(deg: float) -> tuple[float, float]:
        rad = math.radians(deg)
        return math.sin(rad), math.cos(rad)

    morning_dir_sin, morning_dir_cos = _sincos(features.morning_mean_wind_direction)
    ref_dir_sin, ref_dir_cos = _sincos(features.reference_wind_direction)
    afternoon_dir_sin, afternoon_dir_cos = _sincos(features.afternoon_mean_wind_direction)

    return [
        features.morning_mean_wind_speed,
        morning_dir_sin,
        morning_dir_cos,
        features.reference_wind_speed,
        ref_dir_sin,
        ref_dir_cos,
        features.afternoon_max_wind_speed,
        afternoon_dir_sin,
        afternoon_dir_cos,
        features.wind_speed_increase,
        features.onshore_fraction,
    ]


def is_valid_for_analog(features: DailyFeatures) -> bool:
    """Return True if all 9 required fields are present and non-NaN."""
    for field_name in _REQUIRED_FIELDS:
        val = getattr(features, field_name, None)
        if val is None:
            return False
        if isinstance(val, float) and math.isnan(val):
            return False
    return True


def standardize(
    matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Z-score standardize columns of *matrix*.

    Returns (scaled, means, stds).  Zero-variance columns are left as zeros
    (std replaced by 1 to avoid division by zero).
    """
    means = np.mean(matrix, axis=0)
    stds = np.std(matrix, axis=0, ddof=0)
    # Replace zero std with 1 so those columns become all-zero after centering
    safe_stds = np.where(stds == 0, 1.0, stds)
    scaled = (matrix - means) / safe_stds
    return scaled, means, stds


def compute_distances(
    target: np.ndarray,
    historical: np.ndarray,
    means: np.ndarray,
    stds: np.ndarray,
) -> np.ndarray:
    """Euclidean distance from *target* to each row in *historical*.

    Both are standardized using the provided *means* and *stds* (computed from
    the historical sample).
    """
    safe_stds = np.where(stds == 0, 1.0, stds)
    target_scaled = (target - means) / safe_stds
    hist_scaled = (historical - means) / safe_stds
    return np.linalg.norm(hist_scaled - target_scaled, axis=1)


def rank_analogs(
    target_features: DailyFeatures,
    historical_features: list[DailyFeatures],
    top_n: int = 10,
) -> list[AnalogCandidate]:
    """Full pure ranking pipeline: filter, vectorize, standardize, rank.

    Returns up to *top_n* :class:`AnalogCandidate` instances sorted by
    ascending distance (most similar first).
    """
    # Filter valid historical days
    valid: list[tuple[DailyFeatures, list[float]]] = []
    for feat in historical_features:
        if is_valid_for_analog(feat):
            valid.append((feat, features_to_vector(feat)))

    if not valid or not is_valid_for_analog(target_features):
        return []

    target_vec = np.array(features_to_vector(target_features), dtype=np.float64)
    hist_matrix = np.array([v for _, v in valid], dtype=np.float64)

    # Standardize using historical sample statistics
    _, means, stds = standardize(hist_matrix)
    distances = compute_distances(target_vec, hist_matrix, means, stds)

    # Sort by distance, take top_n
    ranked_indices = np.argsort(distances)[:top_n]

    candidates: list[AnalogCandidate] = []
    for rank_idx, idx in enumerate(ranked_indices):
        feat, _ = valid[idx]
        dist = float(distances[idx])
        candidates.append(
            AnalogCandidate(
                date=feat.date,
                rank=rank_idx + 1,
                distance=dist,
                similarity_score=1.0 / (1.0 + dist),
                features={name: getattr(feat, name, None) for name in _REQUIRED_FIELDS},
            )
        )
    return candidates


def yearly_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split a date range into per-calendar-year chunks.

    Each chunk runs from the later of *start* / Jan-1 to the earlier of
    *end* / Dec-31 of that year.
    """
    chunks: list[tuple[date, date]] = []
    year = start.year
    while year <= end.year:
        chunk_start = max(start, date(year, 1, 1))
        chunk_end = min(end, date(year, 12, 31))
        chunks.append((chunk_start, chunk_end))
        year += 1
    return chunks


# ---------------------------------------------------------------------------
# Orchestrator (DB-dependent)
# ---------------------------------------------------------------------------


def run_analog_analysis(
    db: Session,
    location,
    target_date: date,
    hist_start: date,
    hist_end: date,
    top_n: int = 10,
    window: AnalysisWindow | None = None,
) -> AnalysisRun:
    """Execute the full analog matching lifecycle.

    1. Create an AnalysisRun with status='running'
    2. Fetch historical weather in yearly chunks
    3. Fetch target-date weather
    4. Load WeatherRecord rows, group by date, compute DailyFeatures
    5. Rank analogs
    6. Store AnalogResult rows
    7. Update run to 'completed' (or 'failed')

    Returns the AnalysisRun ORM object.
    """
    run = AnalysisRun(
        location_id=location.id,
        target_date=target_date,
        status="running",
        started_at=datetime.now(tz=ZoneInfo("UTC")),
        historical_start_date=hist_start,
        historical_end_date=hist_end,
        top_n=top_n,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        provider = OpenMeteoProvider()

        # -- Fetch historical weather in yearly chunks --
        for chunk_start, chunk_end in yearly_chunks(hist_start, hist_end):
            count, cached = fetch_weather(db, provider, location, chunk_start, chunk_end)
            logger.info(
                "Chunk %s–%s: %d records (cached=%s)",
                chunk_start, chunk_end, count, cached,
            )

        # -- Fetch target date weather --
        t_count, t_cached = fetch_weather(db, provider, location, target_date, target_date)
        logger.info("Target %s: %d records (cached=%s)", target_date, t_count, t_cached)

        # -- Load weather records from DB for the full date range --
        all_start = min(hist_start, target_date)
        all_end = max(hist_end, target_date)
        start_dt = datetime.combine(all_start, time.min)
        end_dt = datetime.combine(all_end, time(23, 59, 59))

        records = (
            db.execute(
                select(WeatherRecord)
                .where(
                    WeatherRecord.location_id == location.id,
                    WeatherRecord.valid_time_local >= start_dt,
                    WeatherRecord.valid_time_local <= end_dt,
                )
                .order_by(WeatherRecord.valid_time_local)
            )
            .scalars()
            .all()
        )

        # -- Group records by date --
        from collections import defaultdict

        by_date: dict[date, list] = defaultdict(list)
        for rec in records:
            by_date[rec.valid_time_local.date()].append(rec)

        # -- Compute DailyFeatures per day --
        historical_features: list[DailyFeatures] = []
        target_features: DailyFeatures | None = None

        for day, day_records in by_date.items():
            feat = compute_daily_features(day_records, location.id, day, window)
            if day == target_date:
                target_features = feat
            else:
                historical_features.append(feat)

        if target_features is None:
            run.status = "failed"
            run.summary = "No weather data available for the target date."
            run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
            db.commit()
            return run

        # -- Rank analogs --
        candidates = rank_analogs(target_features, historical_features, top_n)

        if not candidates:
            run.status = "completed"
            run.summary = "No valid analog candidates found in the historical range."
            run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
            db.commit()
            return run

        # -- Store AnalogResult rows --
        for cand in candidates:
            db.add(
                AnalogResult(
                    analysis_run_id=run.id,
                    analog_date=cand.date,
                    rank=cand.rank,
                    similarity_score=cand.similarity_score,
                    distance=cand.distance,
                )
            )

        run.status = "completed"
        run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()
        db.refresh(run)
        return run

    except Exception:
        logger.exception("Analog analysis failed for run %d", run.id)
        run.status = "failed"
        run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()
        return run
