"""Batch validation service: hindcast evaluation of the analog forecast method."""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.validation_run import ValidationRun
from app.models.weather_record import WeatherRecord
from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.analog_service import rank_analogs
from app.services.classification_service import classify_sea_breeze
from app.services.feature_service import compute_daily_features, compute_feature_config_hash
from app.services.forecast_service import FORECAST_HOURS, build_composite
from app.services.library_service import get_precomputed_features

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_exclusion_set(
    test_date: date,
    buffer_days: int,
    all_library_dates: list[date],
) -> set[date]:
    """Build the set of library dates to exclude for a given test date.

    Excludes any library day whose (month, day) falls within +/- buffer_days
    of the test date's (month, day), across ALL years.  Always excludes
    test_date itself.
    """
    excluded: set[date] = {test_date}

    # Build the set of (month, day) pairs that should be excluded
    excluded_md: set[tuple[int, int]] = set()
    for offset in range(-buffer_days, buffer_days + 1):
        d = test_date + timedelta(days=offset)
        excluded_md.add((d.month, d.day))

    for lib_date in all_library_dates:
        if (lib_date.month, lib_date.day) in excluded_md:
            excluded.add(lib_date)

    return excluded


def _classify_actual_day(
    features: DailyFeatures,
) -> tuple[str, int]:
    """Classify a day using its precomputed features.

    Returns (classification_string, count_true).
    """
    result = classify_sea_breeze(features)
    count_true = sum(result.indicators.values())
    return result.classification, count_true


def _detect_onset_hour(
    hourly_data: dict[int, dict],
    speed_threshold: float = 1.5,
) -> int | None:
    """Detect the onset hour as the first hour in FORECAST_HOURS where TWS exceeds threshold."""
    for hour in FORECAST_HOURS:
        rec = hourly_data.get(hour)
        if rec and rec.get("tws") is not None and rec["tws"] >= speed_threshold:
            return hour
    return None


def _compute_per_hour_errors(
    forecast_hours: list[dict],
    actual_hourly: dict[int, dict],
) -> tuple[list[float], list[float]]:
    """Compute per-hour TWS absolute errors and TWD circular differences.

    Returns (tws_errors, twd_errors) — lists of float.
    """
    tws_errors: list[float] = []
    twd_errors: list[float] = []

    for fh in forecast_hours:
        hour = fh.get("hour_local")
        if hour is None:
            continue
        actual = actual_hourly.get(hour)
        if actual is None:
            continue

        f_tws = fh.get("median_tws")
        a_tws = actual.get("tws")
        if f_tws is not None and a_tws is not None:
            tws_errors.append(abs(f_tws - a_tws))

        f_twd = fh.get("circular_mean_twd")
        a_twd = actual.get("twd")
        if f_twd is not None and a_twd is not None:
            diff = abs(f_twd - a_twd)
            if diff > 180:
                diff = 360 - diff
            twd_errors.append(diff)

    return tws_errors, twd_errors


def _safe(val: float | None) -> float | None:
    """Convert NaN/Inf to None."""
    if val is None:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return round(val, 4)


def _run_hindcast_for_day(
    db: Session,
    location_id: int,
    test_date: date,
    library_features: list[DailyFeatures],
    window: AnalysisWindow,
    top_n: int,
    hist_source: str,
) -> dict | None:
    """Run a single hindcast for one test day.

    Uses precomputed features from the library for the test day (acting as the
    'forecast' source — since ERA5 is the best available hindcast data).

    Returns a per-day result dict, or None if the test day has no features.
    """
    # Find test day's features in the library
    test_features: DailyFeatures | None = None
    for feat in library_features:
        if feat.date == test_date:
            test_features = feat
            break

    if test_features is None:
        # Try to load from weather_records directly
        t_start = datetime.combine(test_date, time.min)
        t_end = datetime.combine(test_date, time(23, 59, 59))
        records = (
            db.execute(
                select(WeatherRecord)
                .where(
                    WeatherRecord.location_id == location_id,
                    WeatherRecord.source == hist_source,
                    WeatherRecord.valid_time_local >= t_start,
                    WeatherRecord.valid_time_local <= t_end,
                )
                .order_by(WeatherRecord.valid_time_local)
            )
            .scalars()
            .all()
        )
        if not records:
            return None
        test_features = compute_daily_features(records, location_id, test_date, window)

    # Classify the test day (this IS the actual classification since we use ERA5)
    actual_classification, actual_count_true = _classify_actual_day(test_features)

    # Classify via gate (same logic as forecast mode)
    gate_classification = classify_sea_breeze(test_features)
    gate_count_true = sum(gate_classification.indicators.values())
    gate_result = gate_classification.classification

    # Check if we can produce a forecast
    if test_features.wind_speed_increase is None and test_features.onshore_fraction is None:
        return {
            "date": test_date.isoformat(),
            "forecast_source_used": hist_source,
            "gate_result": "insufficient_data",
            "classification_count_true": gate_count_true,
            "actual_classification": actual_classification,
            "actual_count_true": actual_count_true,
            "tws_mae": None,
            "tws_rmse": None,
            "twd_circular_mae": None,
            "peak_speed_forecast": None,
            "peak_speed_actual": None,
            "peak_speed_error": None,
            "onset_hour_forecast": None,
            "onset_hour_actual": None,
            "onset_error_hours": None,
            "analog_count": 0,
        }

    # Rank analogs (the library_features passed here are already filtered by exclusion)
    candidates = rank_analogs(test_features, library_features, top_n, window)

    if not candidates or gate_result == "low":
        return {
            "date": test_date.isoformat(),
            "forecast_source_used": hist_source,
            "gate_result": gate_result,
            "classification_count_true": gate_count_true,
            "actual_classification": actual_classification,
            "actual_count_true": actual_count_true,
            "tws_mae": None,
            "tws_rmse": None,
            "twd_circular_mae": None,
            "peak_speed_forecast": None,
            "peak_speed_actual": None,
            "peak_speed_error": None,
            "onset_hour_forecast": None,
            "onset_hour_actual": None,
            "onset_error_hours": None,
            "analog_count": len(candidates),
        }

    # Load analog days' ERA5 afternoon data (hours 11-16)
    analog_hourly_data: list[dict[int, dict]] = []
    for cand in candidates:
        a_start = datetime.combine(cand.date, time(11, 0))
        a_end = datetime.combine(cand.date, time(16, 59, 59))
        recs = (
            db.execute(
                select(WeatherRecord)
                .where(
                    WeatherRecord.location_id == location_id,
                    WeatherRecord.source == hist_source,
                    WeatherRecord.valid_time_local >= a_start,
                    WeatherRecord.valid_time_local <= a_end,
                )
                .order_by(WeatherRecord.valid_time_local)
            )
            .scalars()
            .all()
        )
        day_data: dict[int, dict] = {}
        for rec in recs:
            h = rec.valid_time_local.hour
            if h in FORECAST_HOURS:
                day_data[h] = {"tws": rec.true_wind_speed, "twd": rec.true_wind_direction}
        if day_data:
            analog_hourly_data.append(day_data)

    # Build composite
    composite_hours = build_composite(analog_hourly_data)

    # Load actual ERA5 afternoon data for test day
    a_start = datetime.combine(test_date, time(11, 0))
    a_end = datetime.combine(test_date, time(16, 59, 59))
    actual_recs = (
        db.execute(
            select(WeatherRecord)
            .where(
                WeatherRecord.location_id == location_id,
                WeatherRecord.source == hist_source,
                WeatherRecord.valid_time_local >= a_start,
                WeatherRecord.valid_time_local <= a_end,
            )
            .order_by(WeatherRecord.valid_time_local)
        )
        .scalars()
        .all()
    )
    actual_hourly: dict[int, dict] = {}
    for rec in actual_recs:
        h = rec.valid_time_local.hour
        if h in FORECAST_HOURS:
            actual_hourly[h] = {"tws": rec.true_wind_speed, "twd": rec.true_wind_direction}

    # Compute errors
    tws_errors, twd_errors = _compute_per_hour_errors(composite_hours, actual_hourly)

    tws_mae = _safe(float(np.mean(tws_errors))) if tws_errors else None
    tws_rmse = _safe(float(np.sqrt(np.mean(np.array(tws_errors) ** 2)))) if tws_errors else None
    twd_circular_mae = _safe(float(np.mean(twd_errors))) if twd_errors else None

    # Peak speed
    forecast_peak = max(
        (h.get("median_tws") for h in composite_hours if h.get("median_tws") is not None),
        default=None,
    )
    actual_peak = max(
        (v["tws"] for v in actual_hourly.values() if v.get("tws") is not None),
        default=None,
    )
    peak_error = None
    peak_bias = None
    if forecast_peak is not None and actual_peak is not None:
        peak_bias = _safe(forecast_peak - actual_peak)
        peak_error = _safe(abs(forecast_peak - actual_peak))

    # Onset hour
    forecast_onset = _detect_onset_hour(
        {h["hour_local"]: {"tws": h.get("median_tws")} for h in composite_hours if "hour_local" in h}
    )
    actual_onset = _detect_onset_hour(actual_hourly)
    onset_error = None
    if forecast_onset is not None and actual_onset is not None:
        onset_error = abs(forecast_onset - actual_onset)

    return {
        "date": test_date.isoformat(),
        "forecast_source_used": hist_source,
        "gate_result": gate_result,
        "classification_count_true": gate_count_true,
        "actual_classification": actual_classification,
        "actual_count_true": actual_count_true,
        "tws_mae": tws_mae,
        "tws_rmse": tws_rmse,
        "twd_circular_mae": twd_circular_mae,
        "peak_speed_forecast": _safe(forecast_peak),
        "peak_speed_actual": _safe(actual_peak),
        "peak_speed_error": peak_error,
        "peak_speed_bias": peak_bias,
        "onset_hour_forecast": forecast_onset,
        "onset_hour_actual": actual_onset,
        "onset_error_hours": onset_error,
        "analog_count": len(candidates),
    }


def _compute_climatology_baseline(
    all_library_features: list[DailyFeatures],
    per_day_results: list[dict],
    db: Session,
    location_id: int,
    hist_source: str,
    buffer_days: int,
) -> float | None:
    """Compute climatological MAE for skill score computation.

    For each test day, the climatology forecast is the hour-by-hour median TWS
    of all same-month library days (excluding the buffer zone).
    Returns the overall climatological MAE across all test days, or None.
    """
    all_lib_dates = [f.date for f in all_library_features]
    clim_errors: list[float] = []

    for result in per_day_results:
        if result.get("tws_mae") is None:
            continue  # Skip days without forecast errors

        test_date = date.fromisoformat(result["date"])
        exclusion = _build_exclusion_set(test_date, buffer_days, all_lib_dates)

        # Find same-month library days not in exclusion set
        same_month_features = [
            f for f in all_library_features
            if f.date.month == test_date.month and f.date not in exclusion
        ]

        if not same_month_features:
            continue

        # Load hourly data for same-month days and build climatological composite
        clim_hourly: dict[int, list[float]] = defaultdict(list)
        for feat in same_month_features:
            a_start = datetime.combine(feat.date, time(11, 0))
            a_end = datetime.combine(feat.date, time(16, 59, 59))
            recs = (
                db.execute(
                    select(WeatherRecord)
                    .where(
                        WeatherRecord.location_id == location_id,
                        WeatherRecord.source == hist_source,
                        WeatherRecord.valid_time_local >= a_start,
                        WeatherRecord.valid_time_local <= a_end,
                    )
                    .order_by(WeatherRecord.valid_time_local)
                )
                .scalars()
                .all()
            )
            for rec in recs:
                h = rec.valid_time_local.hour
                if h in FORECAST_HOURS and rec.true_wind_speed is not None:
                    clim_hourly[h].append(rec.true_wind_speed)

        # Compute climatological median per hour
        clim_median: dict[int, float] = {}
        for h, speeds in clim_hourly.items():
            if speeds:
                clim_median[h] = float(np.median(speeds))

        # Load actual test-day data
        a_start = datetime.combine(test_date, time(11, 0))
        a_end = datetime.combine(test_date, time(16, 59, 59))
        actual_recs = (
            db.execute(
                select(WeatherRecord)
                .where(
                    WeatherRecord.location_id == location_id,
                    WeatherRecord.source == hist_source,
                    WeatherRecord.valid_time_local >= a_start,
                    WeatherRecord.valid_time_local <= a_end,
                )
                .order_by(WeatherRecord.valid_time_local)
            )
            .scalars()
            .all()
        )
        actual_hourly: dict[int, float] = {}
        for rec in actual_recs:
            h = rec.valid_time_local.hour
            if h in FORECAST_HOURS and rec.true_wind_speed is not None:
                actual_hourly[h] = rec.true_wind_speed

        # Compute per-hour errors against climatology
        for h in FORECAST_HOURS:
            if h in clim_median and h in actual_hourly:
                clim_errors.append(abs(clim_median[h] - actual_hourly[h]))

    if not clim_errors:
        return None
    return float(np.mean(clim_errors))


def _compute_aggregate_metrics(
    per_day_results: list[dict],
    climatology_mae: float | None,
) -> dict:
    """Compute aggregate classification and continuous metrics from per-day results.

    Days with gate_result="insufficient_data" are excluded from the confusion
    matrix — they cannot be meaningfully classified and would inflate TN.
    """
    tp = fp = tn = fn = 0
    insufficient_days = 0
    tws_maes: list[float] = []
    tws_rmses: list[float] = []
    twd_maes: list[float] = []
    peak_errors: list[float] = []
    peak_biases: list[float] = []
    onset_errors: list[float] = []
    sea_breeze_days = 0
    forecast_produced_days = 0

    for r in per_day_results:
        # Skip insufficient-data days from classification metrics entirely
        if r.get("gate_result") == "insufficient_data":
            insufficient_days += 1
            continue

        # Classification: actual sea breeze = actual_count_true >= 2
        actual_sb = (r.get("actual_count_true") or 0) >= 2
        # Forecast: gate_result is medium or high
        forecast_sb = r.get("gate_result") in ("medium", "high")

        if actual_sb:
            sea_breeze_days += 1

        if actual_sb and forecast_sb:
            tp += 1
        elif not actual_sb and forecast_sb:
            fp += 1
        elif actual_sb and not forecast_sb:
            fn += 1
        else:
            tn += 1

        # Continuous metrics: only for days where forecast was produced
        if forecast_sb and r.get("tws_mae") is not None:
            forecast_produced_days += 1
            tws_maes.append(r["tws_mae"])
            if r.get("tws_rmse") is not None:
                tws_rmses.append(r["tws_rmse"])
            if r.get("twd_circular_mae") is not None:
                twd_maes.append(r["twd_circular_mae"])
            if r.get("peak_speed_error") is not None:
                peak_errors.append(r["peak_speed_error"])
            if r.get("peak_speed_bias") is not None:
                peak_biases.append(r["peak_speed_bias"])
            if r.get("onset_error_hours") is not None:
                onset_errors.append(r["onset_error_hours"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    analog_mae = float(np.mean(tws_maes)) if tws_maes else None
    skill_score = None
    if analog_mae is not None and climatology_mae is not None and climatology_mae > 0:
        skill_score = _safe(1.0 - (analog_mae / climatology_mae))

    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": _safe(precision),
        "recall": _safe(recall),
        "f1": _safe(f1),
        "tws_mae": _safe(float(np.mean(tws_maes))) if tws_maes else None,
        "tws_rmse": _safe(float(np.mean(tws_rmses))) if tws_rmses else None,
        "twd_circular_mae": _safe(float(np.mean(twd_maes))) if twd_maes else None,
        "peak_speed_error_mean": _safe(float(np.mean(peak_errors))) if peak_errors else None,
        "peak_speed_bias_mean": _safe(float(np.mean(peak_biases))) if peak_biases else None,
        "onset_error_mean": _safe(float(np.mean(onset_errors))) if onset_errors else None,
        "skill_score": skill_score,
        "total_days": len(per_day_results),
        "insufficient_days": insufficient_days,
        "sea_breeze_days": sea_breeze_days,
        "forecast_produced_days": forecast_produced_days,
    }


def _compute_gate_sensitivity(per_day_results: list[dict]) -> list[dict]:
    """Sweep count_true thresholds (>=1, >=2, >=3) to produce gate sensitivity analysis."""
    entries: list[dict] = []

    for threshold in [1, 2, 3]:
        tp = fp = tn = fn = 0
        tws_maes: list[float] = []
        tws_rmses: list[float] = []
        covered = 0

        total = 0
        for r in per_day_results:
            # Skip insufficient-data days — can't classify them
            if r.get("gate_result") == "insufficient_data":
                continue
            total += 1

            actual_sb = (r.get("actual_count_true") or 0) >= threshold
            forecast_sb = (r.get("classification_count_true") or 0) >= threshold

            if forecast_sb:
                covered += 1

            if actual_sb and forecast_sb:
                tp += 1
            elif not actual_sb and forecast_sb:
                fp += 1
            elif actual_sb and not forecast_sb:
                fn += 1
            else:
                tn += 1

            # Conditional continuous metrics for days where forecast passes gate
            if forecast_sb and r.get("tws_mae") is not None:
                tws_maes.append(r["tws_mae"])
                if r.get("tws_rmse") is not None:
                    tws_rmses.append(r["tws_rmse"])
        precision = tp / (tp + fp) if (tp + fp) > 0 else None
        recall = tp / (tp + fn) if (tp + fn) > 0 else None
        f1 = None
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)

        entries.append({
            "gate_level": threshold,
            "gate_label": f">={threshold}",
            "coverage": _safe(covered / total) if total > 0 else None,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": _safe(precision),
            "recall": _safe(recall),
            "f1": _safe(f1),
            "conditional_tws_mae": _safe(float(np.mean(tws_maes))) if tws_maes else None,
            "conditional_tws_rmse": _safe(float(np.mean(tws_rmses))) if tws_rmses else None,
        })

    return entries


def _compute_source_stratification(per_day_results: list[dict]) -> list[dict]:
    """Group results by forecast_source_used and compute separate metrics per group."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in per_day_results:
        src = r.get("forecast_source_used") or "unknown"
        groups[src].append(r)

    entries: list[dict] = []
    for source, results in sorted(groups.items()):
        tws_maes = [r["tws_mae"] for r in results if r.get("tws_mae") is not None]
        tws_rmses = [r["tws_rmse"] for r in results if r.get("tws_rmse") is not None]
        twd_maes = [r["twd_circular_mae"] for r in results if r.get("twd_circular_mae") is not None]

        entries.append({
            "source": source,
            "day_count": len(results),
            "tws_mae": _safe(float(np.mean(tws_maes))) if tws_maes else None,
            "tws_rmse": _safe(float(np.mean(tws_rmses))) if tws_rmses else None,
            "twd_circular_mae": _safe(float(np.mean(twd_maes))) if twd_maes else None,
        })

    return entries


# ------------------------------------------------------------------
# Main orchestrator
# ------------------------------------------------------------------


def _get_season_test_dates(
    start_year: int,
    end_year: int,
    months: list[int],
) -> list[date]:
    """Generate all dates within the given months across years."""
    dates: list[date] = []
    for year in range(start_year, end_year + 1):
        for month in months:
            day = 1
            while True:
                try:
                    d = date(year, month, day)
                    dates.append(d)
                    day += 1
                except ValueError:
                    break
    return dates


def run_batch_validation(
    run_id: int,
    location_id: int,
    evaluation_method: str,
    exclusion_buffer_days: int,
    top_n: int,
    library_start_date: date | None,
    library_end_date: date | None,
    test_start_date: date | None,
    test_end_date: date | None,
    hist_source: str,
) -> None:
    """BackgroundTask entry point for batch validation.

    Creates its own DB session so it can run in a background thread.
    """
    db: Session = SessionLocal()
    try:
        run = db.get(ValidationRun, run_id)
        if run is None:
            logger.error("Validation run %d not found", run_id)
            return

        run.status = "running"
        run.started_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()

        window = AnalysisWindow()
        config_hash = compute_feature_config_hash(window)
        months = settings.era5_months_list

        # Determine date ranges based on method
        if evaluation_method == "temporal_split":
            lib_start = library_start_date or date(settings.era5_start_year, min(months), 1)
            lib_end = library_end_date or date(2022, max(months), 30)
            tst_start = test_start_date or date(2023, min(months), 1)
            tst_end = test_end_date or date(settings.era5_end_year, max(months), 30)
        else:  # leave_one_out
            lib_start = library_start_date or date(settings.era5_start_year, min(months), 1)
            lib_end = library_end_date or date(settings.era5_end_year, max(months), 30)
            tst_start = test_start_date or lib_start
            tst_end = test_end_date or lib_end

        # Store resolved dates
        run.library_start_date = lib_start
        run.library_end_date = lib_end
        run.test_start_date = tst_start
        run.test_end_date = tst_end
        db.commit()

        # Load full library
        all_library_features = get_precomputed_features(
            db, location_id, hist_source, config_hash, lib_start, lib_end,
        )
        if not all_library_features:
            run.status = "failed"
            run.error_message = "No precomputed features found in library"
            run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
            db.commit()
            return

        all_lib_dates = [f.date for f in all_library_features]

        # Generate test dates (only season months)
        all_test_dates = [
            d for d in _get_season_test_dates(tst_start.year, tst_end.year, months)
            if tst_start <= d <= tst_end
        ]

        run.total_days = len(all_test_dates)
        db.commit()

        per_day_results: list[dict] = []

        for idx, test_date in enumerate(all_test_dates):
            try:
                # Build exclusion set
                excluded = _build_exclusion_set(test_date, exclusion_buffer_days, all_lib_dates)

                # Filter library features
                filtered_features = [f for f in all_library_features if f.date not in excluded]

                # For leave_one_out, we also need the test day features from the full library
                # (since test days overlap with library days)

                result = _run_hindcast_for_day(
                    db, location_id, test_date, filtered_features,
                    window, top_n, hist_source,
                )

                if result is not None:
                    per_day_results.append(result)

            except Exception:
                logger.exception("Validation error on day %s", test_date)

            run.completed_days = idx + 1
            if (idx + 1) % 10 == 0 or idx == len(all_test_dates) - 1:
                db.commit()

        # Compute aggregate metrics
        climatology_mae = _compute_climatology_baseline(
            all_library_features, per_day_results, db, location_id,
            hist_source, exclusion_buffer_days,
        )
        aggregate = _compute_aggregate_metrics(per_day_results, climatology_mae)
        gate_sens = _compute_gate_sensitivity(per_day_results)
        source_strat = _compute_source_stratification(per_day_results)

        run.aggregate_metrics = aggregate
        run.gate_sensitivity = gate_sens
        run.source_stratification = source_strat
        run.per_day_results = per_day_results
        run.status = "completed"
        run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()

        logger.info(
            "Validation run %d completed: %d days, %d results",
            run_id, len(all_test_dates), len(per_day_results),
        )

    except Exception:
        logger.exception("Validation run %d failed", run_id)
        try:
            run.status = "failed"
            run.error_message = "Unexpected error during validation"
            run.finished_at = datetime.now(tz=ZoneInfo("UTC"))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()
