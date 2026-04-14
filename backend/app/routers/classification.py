from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.location import Location
from app.models.weather_record import WeatherRecord
from app.schemas.features import SeaBreezeClassification, SeaBreezeThresholds
from app.services.classification_service import classify_sea_breeze
from app.services.feature_service import compute_daily_features

router = APIRouter(prefix="/api/classification", tags=["classification"])


@router.get("", response_model=SeaBreezeClassification)
def get_classification(
    location_id: int = Query(...),
    date_param: date = Query(..., alias="date"),
    minimum_speed_increase_mps: float | None = Query(None),
    minimum_direction_shift_degrees: float | None = Query(None),
    minimum_onshore_fraction: float | None = Query(None),
    db: Session = Depends(get_db),
):
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    start_dt = datetime.combine(date_param, time.min)
    end_dt = datetime.combine(date_param, time(23, 59, 59))

    records = (
        db.query(WeatherRecord)
        .filter(
            WeatherRecord.location_id == location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
        .order_by(WeatherRecord.valid_time_utc)
        .all()
    )

    features = compute_daily_features(records, location_id, date_param)

    thresholds = SeaBreezeThresholds()
    if minimum_speed_increase_mps is not None:
        thresholds.minimum_speed_increase_mps = minimum_speed_increase_mps
    if minimum_direction_shift_degrees is not None:
        thresholds.minimum_direction_shift_degrees = minimum_direction_shift_degrees
    if minimum_onshore_fraction is not None:
        thresholds.minimum_onshore_fraction = minimum_onshore_fraction

    return classify_sea_breeze(features, thresholds)
