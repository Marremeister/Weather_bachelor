from datetime import date, datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.location import Location
from app.models.weather_record import WeatherRecord
from app.schemas.weather import (
    WeatherFetchRequest,
    WeatherFetchResponse,
    WeatherRecordResponse,
)
from app.services.weather_service import fetch_weather, get_provider

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.post("/fetch", response_model=WeatherFetchResponse)
def trigger_fetch(req: WeatherFetchRequest, db: Session = Depends(get_db)):
    location = db.get(Location, req.location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")
    if req.start_date > req.end_date:
        raise HTTPException(
            status_code=400, detail="start_date must be <= end_date"
        )

    provider = get_provider(req.source)
    count, cached = fetch_weather(db, provider, location, req.start_date, req.end_date)

    return WeatherFetchResponse(
        location_id=location.id,
        source=provider.source_name,
        start_date=req.start_date,
        end_date=req.end_date,
        records_count=count,
        cached=cached,
    )


@router.get("", response_model=list[WeatherRecordResponse])
def get_weather_records(
    location_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    source: str | None = Query(None),
    db: Session = Depends(get_db),
):
    location = db.get(Location, location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time(23, 59, 59))

    query = db.query(WeatherRecord).filter(
        WeatherRecord.location_id == location_id,
        WeatherRecord.valid_time_local >= start_dt,
        WeatherRecord.valid_time_local <= end_dt,
    )
    if source is not None:
        query = query.filter(WeatherRecord.source == source)

    records = query.order_by(WeatherRecord.valid_time_utc).all()
    return records
