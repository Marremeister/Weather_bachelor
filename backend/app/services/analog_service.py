"""Analog matching: compare a target day against historical days by meteorological similarity."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.weather_record import WeatherRecord
from app.schemas.analog import AnalogCandidate
from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.feature_service import compute_daily_features, compute_feature_config_hash
from app.services.library_service import get_precomputed_features
from app.services.weather_provider import WeatherProvider
from app.services.weather_service import fetch_weather, get_provider

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

# Map each feature name to its group for weighting.
_FIELD_GROUP: dict[str, str] = {
    "morning_mean_wind_speed": "morning",
    "morning_mean_wind_direction": "morning",
    "reference_wind_speed": "reference",
    "reference_wind_direction": "reference",
    "afternoon_max_wind_speed": "afternoon",
    "afternoon_mean_wind_direction": "afternoon",
    "wind_speed_increase": "derived",
    "wind_direction_shift": "derived",
    "onshore_fraction": "derived",
}


def build_weight_vector(window: AnalysisWindow) -> np.ndarray:
    """Build a 12-element weight vector matching ``features_to_vector()`` order.

    Each feature group expands to 3 elements in the vector (directions are
    decomposed into sin/cos pairs), giving::

        [m, m, m, r, r, r, a, a, a, d, d, d]
    """
    group_weight = {
        "morning": window.morning_weight,
        "reference": window.reference_weight,
        "afternoon": window.afternoon_weight,
        "derived": window.derived_weight,
    }
    return np.array([
        group_weight["morning"],   # morning_mean_wind_speed
        group_weight["morning"],   # sin(morning_mean_wind_direction)
        group_weight["morning"],   # cos(morning_mean_wind_direction)
        group_weight["reference"], # reference_wind_speed
        group_weight["reference"], # sin(reference_wind_direction)
        group_weight["reference"], # cos(reference_wind_direction)
        group_weight["afternoon"], # afternoon_max_wind_speed
        group_weight["afternoon"], # sin(afternoon_mean_wind_direction)
        group_weight["afternoon"], # cos(afternoon_mean_wind_direction)
        group_weight["derived"],   # wind_speed_increase
        group_weight["derived"],   # wind_direction_shift
        group_weight["derived"],   # onshore_fraction
    ], dtype=np.float64)


# ---------------------------------------------------------------------------
# Pure functions
# ---------------------------------------------------------------------------


def features_to_vector(features: DailyFeatures) -> list[float]:
    """Convert a DailyFeatures instance to a 12-dimensional vector.

    Wind directions are decomposed into sin/cos pairs so Euclidean distance
    handles circular data correctly.  ``wind_direction_shift`` is included as
    a scalar because it captures the signed magnitude of the morning→afternoon
    rotation which the individual direction decompositions do not fully encode.

    The resulting order is:

        [morning_mean_wind_speed,
         sin(morning_mean_wind_direction), cos(morning_mean_wind_direction),
         reference_wind_speed,
         sin(reference_wind_direction), cos(reference_wind_direction),
         afternoon_max_wind_speed,
         sin(afternoon_mean_wind_direction), cos(afternoon_mean_wind_direction),
         wind_speed_increase,
         wind_direction_shift,
         onshore_fraction]
    """

    def _safe(val: float | None) -> float:
        return 0.0 if val is None else val

    def _sincos(deg: float | None) -> tuple[float, float]:
        if deg is None:
            return 0.0, 0.0
        rad = math.radians(deg)
        return math.sin(rad), math.cos(rad)

    morning_dir_sin, morning_dir_cos = _sincos(features.morning_mean_wind_direction)
    ref_dir_sin, ref_dir_cos = _sincos(features.reference_wind_direction)
    afternoon_dir_sin, afternoon_dir_cos = _sincos(features.afternoon_mean_wind_direction)

    return [
        _safe(features.morning_mean_wind_speed),
        morning_dir_sin,
        morning_dir_cos,
        _safe(features.reference_wind_speed),
        ref_dir_sin,
        ref_dir_cos,
        _safe(features.afternoon_max_wind_speed),
        afternoon_dir_sin,
        afternoon_dir_cos,
        _safe(features.wind_speed_increase),
        _safe(features.wind_direction_shift),
        _safe(features.onshore_fraction),
    ]


def is_valid_for_analog(
    features: DailyFeatures,
    window: AnalysisWindow | None = None,
) -> bool:
    """Return True if all required fields (for groups with non-zero weight) are present.

    Fields belonging to groups with weight 0 are not required, so days
    missing afternoon or derived data can still be valid candidates when
    those groups carry no weight.
    """
    if window is None:
        window = AnalysisWindow()

    group_weight = {
        "morning": window.morning_weight,
        "reference": window.reference_weight,
        "afternoon": window.afternoon_weight,
        "derived": window.derived_weight,
    }

    for field_name in _REQUIRED_FIELDS:
        if group_weight[_FIELD_GROUP[field_name]] == 0:
            continue
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
    weights: np.ndarray | None = None,
) -> np.ndarray:
    """Weighted Euclidean distance from *target* to each row in *historical*.

    Both are standardized using the provided *means* and *stds* (computed from
    the historical sample).  When *weights* is provided, each dimension of the
    difference vector is scaled by ``sqrt(weight)`` before computing the norm,
    implementing weighted Euclidean distance.
    """
    safe_stds = np.where(stds == 0, 1.0, stds)
    target_scaled = (target - means) / safe_stds
    hist_scaled = (historical - means) / safe_stds
    diff = hist_scaled - target_scaled
    if weights is not None:
        diff = diff * np.sqrt(weights)
    return np.linalg.norm(diff, axis=1)


def rank_analogs(
    target_features: DailyFeatures,
    historical_features: list[DailyFeatures],
    top_n: int = 10,
    window: AnalysisWindow | None = None,
) -> list[AnalogCandidate]:
    """Full pure ranking pipeline: filter, vectorize, standardize, rank.

    Returns up to *top_n* :class:`AnalogCandidate` instances sorted by
    ascending distance (most similar first).
    """
    if window is None:
        window = AnalysisWindow()

    weights = build_weight_vector(window)

    # Filter valid historical days
    valid: list[tuple[DailyFeatures, list[float]]] = []
    for feat in historical_features:
        if is_valid_for_analog(feat, window):
            valid.append((feat, features_to_vector(feat)))

    if not valid or not is_valid_for_analog(target_features, window):
        return []

    target_vec = np.array(features_to_vector(target_features), dtype=np.float64)
    hist_matrix = np.array([v for _, v in valid], dtype=np.float64)

    # Standardize using historical sample statistics
    _, means, stds = standardize(hist_matrix)
    distances = compute_distances(target_vec, hist_matrix, means, stds, weights=weights)

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


def compute_all_distances(
    target_features: DailyFeatures,
    historical_features: list[DailyFeatures],
    window: AnalysisWindow | None = None,
) -> list[tuple[DailyFeatures, float]]:
    """Return (features, distance) for ALL valid historical days.

    Same pipeline as ``rank_analogs`` but returns the full list instead of top-N,
    sorted by ascending distance.
    """
    if window is None:
        window = AnalysisWindow()

    weights = build_weight_vector(window)

    valid: list[tuple[DailyFeatures, list[float]]] = []
    for feat in historical_features:
        if is_valid_for_analog(feat, window):
            valid.append((feat, features_to_vector(feat)))

    if not valid or not is_valid_for_analog(target_features, window):
        return []

    target_vec = np.array(features_to_vector(target_features), dtype=np.float64)
    hist_matrix = np.array([v for _, v in valid], dtype=np.float64)

    _, means, stds = standardize(hist_matrix)
    distances = compute_distances(target_vec, hist_matrix, means, stds, weights=weights)

    ranked_indices = np.argsort(distances)
    result: list[tuple[DailyFeatures, float]] = []
    for idx in ranked_indices:
        feat, _ = valid[idx]
        result.append((feat, float(distances[idx])))
    return result


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
    mode: str = "historical",
    forecast_source: str | None = None,
    historical_source: str | None = None,
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
    hist_provider = get_provider(historical_source or "open_meteo")
    if mode == "forecast":
        target_provider: WeatherProvider = get_provider(forecast_source or "gfs")
    else:
        target_provider = hist_provider

    run = AnalysisRun(
        location_id=location.id,
        target_date=target_date,
        status="running",
        started_at=datetime.now(tz=ZoneInfo("UTC")),
        historical_start_date=hist_start,
        historical_end_date=hist_end,
        top_n=top_n,
        mode=mode,
        forecast_source=forecast_source or target_provider.source_name,
        historical_source=historical_source or hist_provider.source_name,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        # -- Check for precomputed feature library --
        if window is None:
            window = AnalysisWindow()
        config_hash = compute_feature_config_hash(window)
        hist_source_name = hist_provider.source_name
        precomputed = get_precomputed_features(
            db, location.id, hist_source_name, config_hash,
            start_date=hist_start, end_date=hist_end,
        )

        if precomputed:
            logger.info(
                "Using precomputed feature library (%d days) for source=%s",
                len(precomputed), hist_source_name,
            )
            historical_features = precomputed
        else:
            # -- Fetch historical weather in yearly chunks (on-the-fly) --
            for chunk_start, chunk_end in yearly_chunks(hist_start, hist_end):
                count, cached = fetch_weather(db, hist_provider, location, chunk_start, chunk_end)
                logger.info(
                    "Chunk %s\u2013%s: %d records (cached=%s)",
                    chunk_start, chunk_end, count, cached,
                )

        # -- Fetch target date weather (with GFS fallback) --
        try:
            t_count, t_cached = fetch_weather(db, target_provider, location, target_date, target_date)
        except Exception as exc:
            if (
                mode == "forecast"
                and target_provider.source_name == "gfs"
                and settings.gfs_fallback_to_open_meteo
            ):
                logger.warning(
                    "GFS fetch failed, falling back to gfs_open_meteo: %s", exc
                )
                target_provider = get_provider("gfs_open_meteo")
                run.forecast_source = target_provider.source_name
                t_count, t_cached = fetch_weather(
                    db, target_provider, location, target_date, target_date
                )
            else:
                raise
        logger.info("Target %s: %d records (cached=%s)", target_date, t_count, t_cached)

        # -- Compute target-day features --
        from collections import defaultdict

        if precomputed:
            # Only need to load target-day records
            target_start_dt = datetime.combine(target_date, time.min)
            target_end_dt = datetime.combine(target_date, time(23, 59, 59))
            target_records = (
                db.execute(
                    select(WeatherRecord)
                    .where(
                        WeatherRecord.location_id == location.id,
                        WeatherRecord.source == target_provider.source_name,
                        WeatherRecord.valid_time_local >= target_start_dt,
                        WeatherRecord.valid_time_local <= target_end_dt,
                    )
                    .order_by(WeatherRecord.valid_time_local)
                )
                .scalars()
                .all()
            )
            target_features: DailyFeatures | None = None
            if target_records:
                target_features = compute_daily_features(
                    target_records, location.id, target_date, window
                )
        else:
            # -- Load weather records from DB for the full date range --
            # When forecast mode uses a different provider, load target and
            # historical records separately to avoid mixing sources.
            by_date: dict[date, list] = defaultdict(list)

            use_separate_sources = (
                mode == "forecast"
                and target_provider.source_name != hist_provider.source_name
            )

            if use_separate_sources:
                # Historical records
                hist_start_dt = datetime.combine(hist_start, time.min)
                hist_end_dt = datetime.combine(hist_end, time(23, 59, 59))
                hist_records = (
                    db.execute(
                        select(WeatherRecord)
                        .where(
                            WeatherRecord.location_id == location.id,
                            WeatherRecord.source == hist_provider.source_name,
                            WeatherRecord.valid_time_local >= hist_start_dt,
                            WeatherRecord.valid_time_local <= hist_end_dt,
                        )
                        .order_by(WeatherRecord.valid_time_local)
                    )
                    .scalars()
                    .all()
                )
                for rec in hist_records:
                    by_date[rec.valid_time_local.date()].append(rec)

                # Target records
                target_start_dt = datetime.combine(target_date, time.min)
                target_end_dt = datetime.combine(target_date, time(23, 59, 59))
                target_records = (
                    db.execute(
                        select(WeatherRecord)
                        .where(
                            WeatherRecord.location_id == location.id,
                            WeatherRecord.source == target_provider.source_name,
                            WeatherRecord.valid_time_local >= target_start_dt,
                            WeatherRecord.valid_time_local <= target_end_dt,
                        )
                        .order_by(WeatherRecord.valid_time_local)
                    )
                    .scalars()
                    .all()
                )
                for rec in target_records:
                    by_date[rec.valid_time_local.date()].append(rec)
            else:
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
                for rec in records:
                    by_date[rec.valid_time_local.date()].append(rec)

            # -- Compute DailyFeatures per day --
            historical_features: list[DailyFeatures] = []
            target_features = None

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
        candidates = rank_analogs(target_features, historical_features, top_n, window=window)

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

        # Add model run metadata to summary for forecast mode
        if mode == "forecast":
            # When using precomputed features, by_date may not exist;
            # load target-day records directly for metadata.
            if precomputed:
                _t_start = datetime.combine(target_date, time.min)
                _t_end = datetime.combine(target_date, time(23, 59, 59))
                target_day_records = (
                    db.execute(
                        select(WeatherRecord)
                        .where(
                            WeatherRecord.location_id == location.id,
                            WeatherRecord.source == target_provider.source_name,
                            WeatherRecord.valid_time_local >= _t_start,
                            WeatherRecord.valid_time_local <= _t_end,
                        )
                    )
                    .scalars()
                    .all()
                )
            else:
                target_day_records = by_date.get(target_date, [])
            model_run_times = [
                r.model_run_time for r in target_day_records
                if hasattr(r, "model_run_time") and r.model_run_time is not None
            ]
            if model_run_times:
                mrt = model_run_times[0]
                mrt_str = mrt.isoformat() if hasattr(mrt, "isoformat") else str(mrt)
                model_names = {
                    r.model_name for r in target_day_records
                    if hasattr(r, "model_name") and r.model_name
                }
                model_str = ", ".join(sorted(model_names)) if model_names else "unknown"
                run.summary = f"GFS model run: {mrt_str} ({model_str})"

        db.commit()
        db.refresh(run)
        return run

    except Exception:
        logger.exception("Analog analysis failed for run %d", run.id)
        run.status = "failed"
        run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()
        return run
