"""Library management endpoints: build, status, bias calibration, seasonal heatmap."""

from __future__ import annotations

from datetime import date
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.daily_feature import DailyFeatureRow
from app.schemas.features import (
    AnalysisWindow,
    DailyFeatures,
    LibraryDaySummary,
    SeasonalHeatmapResponse,
)
from app.services.bias_service import calibrate_bias, get_bias_report
from app.services.classification_service import classify_sea_breeze
from app.services.feature_service import compute_feature_config_hash
from app.services.library_service import build_feature_library, get_library_status

router = APIRouter(prefix="/api/library", tags=["library"])


@router.post("/build")
def trigger_library_build(
    background_tasks: BackgroundTasks,
    location_id: int = Query(...),
    source: str = Query("era5"),
    db: Session = Depends(get_db),
):
    """Trigger a background feature library build for a location."""
    background_tasks.add_task(build_feature_library, location_id, source)
    return {"status": "started", "location_id": location_id, "source": source}


@router.get("/status")
def library_status(
    location_id: int = Query(...),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Check build progress for a location.

    When *source* is provided, the response reflects the latest build job
    for that specific source (e.g. ``era5`` or ``gfs_hindcast``); otherwise
    the latest job across all sources is returned (legacy behaviour).
    """
    info = get_library_status(db, location_id, source=source)
    if info is None:
        payload: dict = {"status": "no_build", "location_id": location_id}
        if source is not None:
            payload["source"] = source
        return payload
    return info


@router.post("/calibrate")
def trigger_bias_calibration(
    background_tasks: BackgroundTasks,
    location_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Trigger background bias calibration for a location."""
    background_tasks.add_task(calibrate_bias, location_id)
    return {"status": "started", "location_id": location_id}


@router.get("/bias-report")
def bias_report(
    location_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Return per-feature bias statistics for a location."""
    report = get_bias_report(db, location_id)
    return {"location_id": location_id, "corrections": report}


@router.get("/seasonal-heatmap", response_model=SeasonalHeatmapResponse)
def seasonal_heatmap(
    location_id: int = Query(...),
    source: str = Query("era5"),
    target_date: date | None = Query(default=None),
    analog_dates: List[date] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Return per-day summaries for all library days (for calendar heatmap)."""
    config_hash = compute_feature_config_hash(AnalysisWindow())

    rows = (
        db.execute(
            select(DailyFeatureRow)
            .where(
                DailyFeatureRow.location_id == location_id,
                DailyFeatureRow.source == source,
                DailyFeatureRow.feature_config_hash == config_hash,
            )
            .order_by(DailyFeatureRow.date)
        )
        .scalars()
        .all()
    )

    days: list[LibraryDaySummary] = []
    for row in rows:
        fj = row.features_json
        feat = DailyFeatures(
            location_id=row.location_id,
            date=row.date,
            morning_mean_wind_speed=fj.get("morning_mean_wind_speed"),
            morning_mean_wind_direction=fj.get("morning_mean_wind_direction"),
            reference_wind_speed=fj.get("reference_wind_speed"),
            reference_wind_direction=fj.get("reference_wind_direction"),
            afternoon_max_wind_speed=fj.get("afternoon_max_wind_speed"),
            afternoon_mean_wind_direction=fj.get("afternoon_mean_wind_direction"),
            wind_speed_increase=fj.get("wind_speed_increase"),
            wind_direction_shift=fj.get("wind_direction_shift"),
            onshore_fraction=fj.get("onshore_fraction"),
            hours_available=fj.get("hours_available", 0),
            morning_hours_used=fj.get("morning_hours_used", 0),
            afternoon_hours_used=fj.get("afternoon_hours_used", 0),
        )
        # Skip days with insufficient data — classifying them would
        # incorrectly label missing-data days as "low" sea-breeze days.
        if (
            feat.wind_speed_increase is None
            and feat.wind_direction_shift is None
            and feat.onshore_fraction is None
        ):
            continue
        classification = classify_sea_breeze(feat)
        days.append(
            LibraryDaySummary(
                date=row.date,
                wind_speed_increase=feat.wind_speed_increase,
                classification=classification.classification,
            )
        )

    return SeasonalHeatmapResponse(
        location_id=location_id,
        days=days,
        target_date=target_date,
        analog_dates=analog_dates or [],
    )
