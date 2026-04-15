"""Batch validation endpoints: trigger, poll status, retrieve results."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.validation_run import ValidationRun
from app.schemas.validation import (
    ValidationRunRequest,
    ValidationRunResponse,
    ValidationRunStatusResponse,
    ValidationRunSummary,
)
from app.services.validation_service import run_batch_validation

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.post("/run")
def trigger_validation_run(
    req: ValidationRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a batch validation run (returns run_id, runs in background)."""
    run = ValidationRun(
        location_id=req.location_id,
        evaluation_method=req.evaluation_method,
        exclusion_buffer_days=req.exclusion_buffer_days,
        top_n=req.top_n,
        library_start_date=req.library_start_date,
        library_end_date=req.library_end_date,
        test_start_date=req.test_start_date,
        test_end_date=req.test_end_date,
        historical_source=req.historical_source or "era5",
        forecast_source=req.forecast_source,
        status="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    hist_source = req.historical_source or "era5"

    background_tasks.add_task(
        run_batch_validation,
        run.id,
        req.location_id,
        req.evaluation_method,
        req.exclusion_buffer_days,
        req.top_n,
        req.library_start_date,
        req.library_end_date,
        req.test_start_date,
        req.test_end_date,
        hist_source,
    )

    return {"run_id": run.id, "status": "queued"}


@router.get("/runs", response_model=list[ValidationRunSummary])
def list_validation_runs(
    location_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """List all validation runs for a location."""
    runs = (
        db.execute(
            select(ValidationRun)
            .where(ValidationRun.location_id == location_id)
            .order_by(ValidationRun.id.desc())
        )
        .scalars()
        .all()
    )
    return runs


@router.get("/{run_id}", response_model=ValidationRunResponse)
def get_validation_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Get full validation run results (aggregate + gate + stratification + per-day)."""
    run = db.get(ValidationRun, run_id)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Validation run not found")
    return run


@router.get("/{run_id}/status", response_model=ValidationRunStatusResponse)
def get_validation_run_status(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Poll validation run progress."""
    run = db.get(ValidationRun, run_id)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Validation run not found")
    return run


@router.get("/{run_id}/export/csv")
def export_validation_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Export per-day validation results as CSV for thesis."""
    run = db.get(ValidationRun, run_id)
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Validation run not found")

    results = run.per_day_results or []

    output = io.StringIO()
    if results:
        fieldnames = list(results[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    else:
        output.write("No results available\n")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=validation_run_{run_id}.csv",
        },
    )
