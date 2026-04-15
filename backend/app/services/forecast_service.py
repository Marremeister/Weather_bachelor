"""Forecast composite: build probabilistic TWS/TWD forecast from analog day actuals."""

from __future__ import annotations

import logging
import math
from datetime import datetime, time

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.weather_record import WeatherRecord
from app.schemas.features import AnalysisWindow
from app.services.classification_service import classify_sea_breeze
from app.services.feature_service import (
    circular_arc_radius,
    circular_mean,
    circular_std,
    compute_daily_features,
)

logger = logging.getLogger(__name__)

FORECAST_HOURS = [11, 12, 13, 14, 15, 16]


def _safe_json(val: float | None) -> float | None:
    """Convert NaN/Inf to None for JSONB storage."""
    if val is None:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return round(val, 4)


def composite_hour(tws_values: list[float], twd_values: list[float]) -> dict | None:
    """Compute composite statistics for a single forecast hour.

    Returns a dict with TWS percentiles and TWD circular statistics,
    or None if no TWS data is available.
    """
    if not tws_values:
        return None

    tws_arr = np.array(tws_values)

    result: dict = {
        "median_tws": _safe_json(float(np.median(tws_arr))),
        "p25_tws": _safe_json(float(np.percentile(tws_arr, 25))),
        "p75_tws": _safe_json(float(np.percentile(tws_arr, 75))),
        "p10_tws": _safe_json(float(np.percentile(tws_arr, 10))),
        "p90_tws": _safe_json(float(np.percentile(tws_arr, 90))),
        "analog_count": len(tws_values),
    }

    if twd_values:
        result["circular_mean_twd"] = _safe_json(circular_mean(twd_values))
        result["twd_circular_std"] = _safe_json(circular_std(twd_values))
        result["twd_arc_radius_75"] = _safe_json(circular_arc_radius(twd_values, 75.0))
    else:
        result["circular_mean_twd"] = None
        result["twd_circular_std"] = None
        result["twd_arc_radius_75"] = None

    return result


def build_composite(analog_hourly_data: list[dict[int, dict]]) -> list[dict]:
    """Aggregate hourly data across all analog days.

    *analog_hourly_data* is a list (one per analog day) of dicts mapping
    hour (int) -> {"tws": float | None, "twd": float | None}.

    Returns a list of composite dicts, one per FORECAST_HOURS entry.
    """
    hours_out: list[dict] = []

    for hour in FORECAST_HOURS:
        tws_vals: list[float] = []
        twd_vals: list[float] = []

        for day_data in analog_hourly_data:
            rec = day_data.get(hour)
            if rec is None:
                continue
            if rec.get("tws") is not None:
                tws_vals.append(rec["tws"])
            if rec.get("twd") is not None:
                twd_vals.append(rec["twd"])

        comp = composite_hour(tws_vals, twd_vals)
        if comp is not None:
            comp["hour_local"] = hour
            hours_out.append(comp)

    return hours_out


def generate_forecast_composite(db: Session, run: AnalysisRun) -> dict | None:
    """Orchestrator: classify target day, gate-check, build composite.

    Stores the result as JSONB on ``run.forecast_composite`` and returns it.
    Returns None only on unexpected failure.
    """
    try:
        # --- 1. Load target-day records and classify ---
        target_source = run.forecast_source or run.historical_source
        t_start = datetime.combine(run.target_date, time.min)
        t_end = datetime.combine(run.target_date, time(23, 59, 59))

        target_stmt = (
            select(WeatherRecord)
            .where(
                WeatherRecord.location_id == run.location_id,
                WeatherRecord.valid_time_local >= t_start,
                WeatherRecord.valid_time_local <= t_end,
            )
        )
        if target_source:
            target_stmt = target_stmt.where(WeatherRecord.source == target_source)

        target_records = (
            db.execute(target_stmt.order_by(WeatherRecord.valid_time_local))
            .scalars()
            .all()
        )

        if not target_records:
            result = {"gate_result": "insufficient_data", "hours": None}
            run.forecast_composite = result
            db.commit()
            return result

        window = AnalysisWindow()
        features = compute_daily_features(
            target_records, run.location_id, run.target_date, window,
        )

        # --- 2. Sufficiency guard (same as sea-breeze panel) ---
        if features.wind_speed_increase is None and features.onshore_fraction is None:
            result = {"gate_result": "insufficient_data", "hours": None}
            run.forecast_composite = result
            db.commit()
            return result

        classification = classify_sea_breeze(features)

        if classification.classification == "low":
            result = {"gate_result": "low", "hours": None}
            run.forecast_composite = result
            db.commit()
            return result

        # --- 3. Load analog-day ERA5 records for 11:00-16:00 ---
        analogs = (
            db.execute(
                select(AnalogResult)
                .where(AnalogResult.analysis_run_id == run.id)
                .order_by(AnalogResult.rank)
            )
            .scalars()
            .all()
        )

        if not analogs:
            result = {"gate_result": classification.classification, "hours": None}
            run.forecast_composite = result
            db.commit()
            return result

        hist_source = run.historical_source or "era5"
        analog_hourly_data: list[dict[int, dict]] = []

        for analog in analogs:
            a_start = datetime.combine(analog.analog_date, time(11, 0))
            a_end = datetime.combine(analog.analog_date, time(16, 59, 59))

            recs = (
                db.execute(
                    select(WeatherRecord)
                    .where(
                        WeatherRecord.location_id == run.location_id,
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
                    day_data[h] = {
                        "tws": rec.true_wind_speed,
                        "twd": rec.true_wind_direction,
                    }

            if day_data:
                analog_hourly_data.append(day_data)

        # --- 4. Build composite ---
        hours = build_composite(analog_hourly_data)

        result = {
            "gate_result": classification.classification,
            "hours": hours if hours else None,
        }

        run.forecast_composite = result
        db.commit()

        logger.info(
            "Forecast composite for run %d: gate=%s, %d hours",
            run.id,
            classification.classification,
            len(hours),
        )
        return result

    except Exception:
        logger.exception("Forecast composite generation failed for run %d", run.id)
        return None
