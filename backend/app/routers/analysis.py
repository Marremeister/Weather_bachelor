"""Endpoints for analog matching analysis."""

import csv
import io
import datetime as _dt
from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.location import Location
from app.models.weather_record import WeatherRecord
from app.schemas.analog import (
    AnalogResultResponse,
    AnalysisRequest,
    AnalysisRunDetailResponse,
    AnalysisRunResponse,
)
from app.schemas.features import (
    DayClassificationDetail,
    SeaBreezePanelResponse,
    SeaBreezeThresholds,
)
from app.services.analog_service import run_analog_analysis
from app.services.feature_service import compute_daily_features
from app.services.classification_service import classify_sea_breeze

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("", response_model=list[AnalysisRunResponse])
def list_analysis_runs(
    location_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    if location_id is not None:
        stmt = stmt.where(AnalysisRun.location_id == location_id)
    runs = db.execute(stmt).scalars().all()
    return [AnalysisRunResponse.model_validate(r) for r in runs]


@router.post("/run", response_model=AnalysisRunDetailResponse)
def trigger_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
):
    location = db.get(Location, request.location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    if request.historical_end_date <= request.historical_start_date:
        raise HTTPException(
            status_code=400,
            detail="historical_end_date must be after historical_start_date",
        )

    if request.mode not in ("historical", "forecast"):
        raise HTTPException(
            status_code=400,
            detail="mode must be 'historical' or 'forecast'",
        )

    run = run_analog_analysis(
        db=db,
        location=location,
        target_date=request.target_date,
        hist_start=request.historical_start_date,
        hist_end=request.historical_end_date,
        top_n=request.top_n,
        mode=request.mode,
        forecast_source=request.forecast_source,
        historical_source=request.historical_source,
    )

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return AnalysisRunDetailResponse.model_validate(
        {**_run_dict(run), "analogs": [AnalogResultResponse.model_validate(a) for a in analogs]}
    )


@router.get("/{run_id}", response_model=AnalysisRunDetailResponse)
def get_analysis_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return AnalysisRunDetailResponse.model_validate(
        {**_run_dict(run), "analogs": [AnalogResultResponse.model_validate(a) for a in analogs]}
    )


@router.get("/{run_id}/analogs", response_model=list[AnalogResultResponse])
def get_analysis_analogs(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return [AnalogResultResponse.model_validate(a) for a in analogs]


@router.get("/{run_id}/export/weather-csv")
def export_weather_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    start_dt = _dt.datetime.combine(run.target_date, time.min)
    end_dt = _dt.datetime.combine(run.target_date, time.max)
    export_source = run.forecast_source or run.historical_source

    stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
    )
    if export_source:
        stmt = stmt.where(WeatherRecord.source == export_source)
    records = db.execute(stmt.order_by(WeatherRecord.valid_time_local)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "valid_time_utc", "valid_time_local", "wind_speed_ms",
        "wind_direction_deg", "temperature_c", "pressure_hpa", "cloud_cover_pct",
        "source",
    ])
    for r in records:
        writer.writerow([
            r.valid_time_utc.isoformat() if r.valid_time_utc else "",
            r.valid_time_local.isoformat() if r.valid_time_local else "",
            r.true_wind_speed, r.true_wind_direction,
            r.temperature, r.pressure, r.cloud_cover,
            r.source,
        ])

    filename = f"weather_{run.target_date.isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/export/analogs-csv")
def export_analogs_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "analog_date", "similarity_score", "distance", "summary"])
    for a in analogs:
        writer.writerow([
            a.rank, a.analog_date.isoformat() if a.analog_date else "",
            a.similarity_score, a.distance, a.summary,
        ])

    filename = f"analogs_{run.target_date.isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/export/json")
def export_analysis_json(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    start_dt = _dt.datetime.combine(run.target_date, time.min)
    end_dt = _dt.datetime.combine(run.target_date, time.max)
    export_source = run.forecast_source or run.historical_source

    stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
    )
    if export_source:
        stmt = stmt.where(WeatherRecord.source == export_source)
    records = db.execute(stmt.order_by(WeatherRecord.valid_time_local)).scalars().all()

    run_response = AnalysisRunResponse.model_validate(run)
    analog_responses = [AnalogResultResponse.model_validate(a) for a in analogs]

    payload = {
        "analysis_run": run_response.model_dump(mode="json"),
        "analogs": [a.model_dump(mode="json") for a in analog_responses],
        "weather_records": [
            {
                "valid_time_utc": r.valid_time_utc.isoformat() if r.valid_time_utc else None,
                "valid_time_local": r.valid_time_local.isoformat() if r.valid_time_local else None,
                "wind_speed_ms": r.true_wind_speed,
                "wind_direction_deg": r.true_wind_direction,
                "temperature_c": r.temperature,
                "pressure_hpa": r.pressure,
                "cloud_cover_pct": r.cloud_cover,
                "source": r.source,
                "model_run_time": r.model_run_time.isoformat() if r.model_run_time else None,
                "forecast_hour": r.forecast_hour,
                "model_name": r.model_name,
            }
            for r in records
        ],
    }

    filename = f"analysis_{run.target_date.isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/sea-breeze-panel", response_model=SeaBreezePanelResponse)
def get_sea_breeze_panel(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    target_source = run.forecast_source or run.historical_source
    analog_source = run.historical_source

    thresholds = SeaBreezeThresholds()

    def _classify_day(
        loc_id: int, day: _dt.date, source: str | None,
    ) -> DayClassificationDetail | None:
        start_dt = _dt.datetime.combine(day, time.min)
        end_dt = _dt.datetime.combine(day, time.max)
        stmt = select(WeatherRecord).where(
            WeatherRecord.location_id == loc_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
        if source:
            stmt = stmt.where(WeatherRecord.source == source)
        records = (
            db.execute(stmt.order_by(WeatherRecord.valid_time_local))
            .scalars()
            .all()
        )
        if not records:
            return None
        features = compute_daily_features(records, loc_id, day)
        if features.wind_speed_increase is None and features.onshore_fraction is None:
            return None
        classification = classify_sea_breeze(features, thresholds)
        return DayClassificationDetail(
            date=day,
            features=features,
            classification=classification,
        )

    target_detail = _classify_day(run.location_id, run.target_date, target_source)

    analog_details: list[DayClassificationDetail] = []
    for analog in analogs:
        detail = _classify_day(run.location_id, analog.analog_date, analog_source)
        if detail is not None:
            analog_details.append(detail)

    high = sum(1 for a in analog_details if a.classification.classification == "high")
    medium = sum(1 for a in analog_details if a.classification.classification == "medium")
    low = sum(1 for a in analog_details if a.classification.classification == "low")

    return SeaBreezePanelResponse(
        run_id=run.id,
        target=target_detail,
        analogs=analog_details,
        thresholds=thresholds,
        analog_high_count=high,
        analog_medium_count=medium,
        analog_low_count=low,
        analog_total=len(analog_details),
    )


def _run_dict(run: AnalysisRun) -> dict:
    """Convert an AnalysisRun ORM object to a dict for Pydantic validation."""
    return {
        "id": run.id,
        "location_id": run.location_id,
        "target_date": run.target_date,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary": run.summary,
        "historical_start_date": run.historical_start_date,
        "historical_end_date": run.historical_end_date,
        "top_n": run.top_n,
        "mode": run.mode,
        "forecast_source": run.forecast_source,
        "historical_source": run.historical_source,
        "created_at": run.created_at,
    }
