"""Endpoints for analog matching analysis."""

import csv
import io
import datetime as _dt
from datetime import date, time

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
from app.services.analog_service import run_analog_analysis

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

    run = run_analog_analysis(
        db=db,
        location=location,
        target_date=request.target_date,
        hist_start=request.historical_start_date,
        hist_end=request.historical_end_date,
        top_n=request.top_n,
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

    day_start = run.target_date
    day_end = date(day_start.year, day_start.month, day_start.day)

    start_dt = _dt.datetime.combine(day_start, time.min)
    end_dt = _dt.datetime.combine(day_end, time.max)

    records = (
        db.execute(
            select(WeatherRecord)
            .where(
                WeatherRecord.location_id == run.location_id,
                WeatherRecord.valid_time_utc >= start_dt,
                WeatherRecord.valid_time_utc <= end_dt,
            )
            .order_by(WeatherRecord.valid_time_utc)
        )
        .scalars()
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "valid_time_utc", "valid_time_local", "wind_speed_ms",
        "wind_direction_deg", "temperature_c", "pressure_hpa", "cloud_cover_pct",
    ])
    for r in records:
        writer.writerow([
            r.valid_time_utc.isoformat() if r.valid_time_utc else "",
            r.valid_time_local.isoformat() if r.valid_time_local else "",
            r.true_wind_speed, r.true_wind_direction,
            r.temperature, r.pressure, r.cloud_cover,
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

    records = (
        db.execute(
            select(WeatherRecord)
            .where(
                WeatherRecord.location_id == run.location_id,
                WeatherRecord.valid_time_utc >= start_dt,
                WeatherRecord.valid_time_utc <= end_dt,
            )
            .order_by(WeatherRecord.valid_time_utc)
        )
        .scalars()
        .all()
    )

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
            }
            for r in records
        ],
    }

    filename = f"analysis_{run.target_date.isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
        "created_at": run.created_at,
    }
