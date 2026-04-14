"""Endpoints for analog matching analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.location import Location
from app.schemas.analog import (
    AnalogResultResponse,
    AnalysisRequest,
    AnalysisRunDetailResponse,
)
from app.services.analog_service import run_analog_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


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
