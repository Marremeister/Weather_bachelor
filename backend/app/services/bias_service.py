"""Bias calibration between forecast and historical weather sources.

Computes per-feature bias statistics (mean, std) by comparing overlapping
date ranges from two different weather sources (e.g. GFS hindcast vs ERA5).
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.location import Location
from app.models.source_bias_correction import SourceBiasCorrection
from app.models.weather_record import WeatherRecord
from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.feature_service import _DEFAULT_FEATURE_NAMES, compute_daily_features
from app.services.weather_service import fetch_weather, get_provider

logger = logging.getLogger(__name__)


_LIVE_ONLY_SOURCES = frozenset({"gfs", "gfs_open_meteo", "open_meteo_forecast"})
"""Sources that use live/forecast-only endpoints and cannot serve historical dates.

``gfs_hindcast`` is intentionally *not* listed here: it can serve
historical dates (it's a forecast-hour archive) and in principle could be
calibrated against ERA5, but its ``(gfs_hindcast, era5)`` bias pair has
no consumers yet and is out of scope for the initial hindcast library.
Calibration for that pair is a separate follow-up."""


def calibrate_bias(
    location_id: int,
    overlap_days: int | None = None,
    forecast_source: str = "open_meteo",
    historical_source: str = "era5",
) -> None:
    """Compute per-feature bias corrections between two sources.

    Runs as a BackgroundTask with its own DB session.

    The default *forecast_source* is ``open_meteo`` (Open-Meteo archive API)
    because the calibration window is clamped to the ERA5 historical season.
    Live/forecast-only providers (``gfs``, ``gfs_open_meteo``,
    ``open_meteo_forecast``) cannot fetch those dates and are rejected.
    """
    if forecast_source in _LIVE_ONLY_SOURCES:
        logger.error(
            "Bias calibration: '%s' is a live/forecast-only provider and cannot "
            "fetch the historical dates needed for calibration.  Use a provider "
            "with archive/historical support (e.g. 'open_meteo').",
            forecast_source,
        )
        return

    if overlap_days is None:
        overlap_days = settings.bias_overlap_days

    db: Session = SessionLocal()
    try:
        location = db.get(Location, location_id)
        if location is None:
            logger.error("Bias calibration: location %d not found", location_id)
            return

        # Determine overlap date range: last N days within ERA5 season,
        # with a 2-day lag to allow for GFS data availability.
        now = datetime.now(tz=ZoneInfo("UTC"))
        end_date = (now - timedelta(days=2)).date()

        # Clamp to ERA5 season bounds
        era5_months = settings.era5_months_list
        latest_era5_year = settings.era5_end_year
        season_end = date(latest_era5_year, max(era5_months), 30)
        if end_date > season_end:
            end_date = season_end

        start_date = end_date - timedelta(days=overlap_days)
        season_start = date(latest_era5_year, min(era5_months), 1)
        if start_date < season_start:
            start_date = season_start

        logger.info(
            "Bias calibration: %s vs %s, overlap %s to %s",
            forecast_source, historical_source, start_date, end_date,
        )

        # Fetch data from both sources
        forecast_provider = get_provider(forecast_source)
        hist_provider = get_provider(historical_source)

        try:
            fetch_weather(db, forecast_provider, location, start_date, end_date)
        except Exception as exc:
            logger.warning("Forecast source fetch failed for bias: %s", exc)

        try:
            fetch_weather(db, hist_provider, location, start_date, end_date)
        except Exception as exc:
            logger.warning("Historical source fetch failed for bias: %s", exc)

        # Load records and compute features for both sources
        window = AnalysisWindow()

        def _load_features(source: str) -> dict[date, DailyFeatures]:
            start_dt = datetime.combine(start_date, time.min)
            end_dt = datetime.combine(end_date, time(23, 59, 59))
            records = (
                db.execute(
                    select(WeatherRecord)
                    .where(
                        WeatherRecord.location_id == location_id,
                        WeatherRecord.source == source,
                        WeatherRecord.valid_time_local >= start_dt,
                        WeatherRecord.valid_time_local <= end_dt,
                    )
                    .order_by(WeatherRecord.valid_time_local)
                )
                .scalars()
                .all()
            )
            by_date: dict[date, list] = defaultdict(list)
            for rec in records:
                by_date[rec.valid_time_local.date()].append(rec)

            features: dict[date, DailyFeatures] = {}
            for day, day_records in by_date.items():
                features[day] = compute_daily_features(
                    day_records, location_id, day, window
                )
            return features

        forecast_features = _load_features(forecast_source)
        hist_features = _load_features(historical_source)

        # Find overlapping dates
        common_dates = sorted(set(forecast_features) & set(hist_features))
        if not common_dates:
            logger.warning("No overlapping dates for bias calibration")
            return

        logger.info("Bias calibration: %d overlapping dates", len(common_dates))

        # Compute per-feature bias
        bias_data: dict[str, list[float]] = {name: [] for name in _DEFAULT_FEATURE_NAMES}

        for day in common_dates:
            fc = forecast_features[day]
            hc = hist_features[day]
            for name in _DEFAULT_FEATURE_NAMES:
                fc_val = getattr(fc, name, None)
                hc_val = getattr(hc, name, None)
                if (
                    fc_val is not None
                    and hc_val is not None
                    and not (isinstance(fc_val, float) and math.isnan(fc_val))
                    and not (isinstance(hc_val, float) and math.isnan(hc_val))
                ):
                    bias_data[name].append(fc_val - hc_val)

        # Delete old corrections for this pair
        db.execute(
            delete(SourceBiasCorrection).where(
                SourceBiasCorrection.location_id == location_id,
                SourceBiasCorrection.forecast_source == forecast_source,
                SourceBiasCorrection.historical_source == historical_source,
            )
        )
        db.commit()

        # Insert new corrections
        for name in _DEFAULT_FEATURE_NAMES:
            diffs = bias_data[name]
            if not diffs:
                continue
            arr = np.array(diffs)
            db.add(
                SourceBiasCorrection(
                    location_id=location_id,
                    forecast_source=forecast_source,
                    historical_source=historical_source,
                    feature_name=name,
                    bias_mean=float(np.mean(arr)),
                    bias_std=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
                    calibration_start=start_date,
                    calibration_end=end_date,
                    sample_count=len(diffs),
                )
            )

        db.commit()
        logger.info(
            "Bias calibration complete: %d features updated", len(_DEFAULT_FEATURE_NAMES)
        )

    except Exception:
        logger.exception("Bias calibration failed for location %d", location_id)
    finally:
        db.close()


def get_bias_report(db: Session, location_id: int) -> list[dict]:
    """Return stored bias corrections grouped by source pair."""
    rows = (
        db.execute(
            select(SourceBiasCorrection)
            .where(SourceBiasCorrection.location_id == location_id)
            .order_by(
                SourceBiasCorrection.forecast_source,
                SourceBiasCorrection.historical_source,
                SourceBiasCorrection.feature_name,
            )
        )
        .scalars()
        .all()
    )

    return [
        {
            "forecast_source": r.forecast_source,
            "historical_source": r.historical_source,
            "feature_name": r.feature_name,
            "bias_mean": r.bias_mean,
            "bias_std": r.bias_std,
            "calibration_start": r.calibration_start.isoformat(),
            "calibration_end": r.calibration_end.isoformat(),
            "sample_count": r.sample_count,
        }
        for r in rows
    ]
