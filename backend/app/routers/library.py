"""Library management endpoints: build, status, bias calibration."""

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.bias_service import calibrate_bias, get_bias_report
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
    db: Session = Depends(get_db),
):
    """Check build progress for a location."""
    info = get_library_status(db, location_id)
    if info is None:
        return {"status": "no_build", "location_id": location_id}
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
