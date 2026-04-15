from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.weather_station import WeatherStation
from app.schemas.observation import (
    ObservationFetchRequest,
    ObservationFetchResponse,
    ObservationResponse,
    StationResponse,
    ValidationMetricsResponse,
)
from app.services.observation_service import (
    compute_validation_metrics,
    fetch_observations,
    get_observation_provider,
    query_observations,
)

router = APIRouter(prefix="/api/observations", tags=["observations"])


@router.get("/stations", response_model=list[StationResponse])
def list_stations(db: Session = Depends(get_db)):
    return db.query(WeatherStation).order_by(WeatherStation.id).all()


@router.post("/fetch", response_model=ObservationFetchResponse)
def trigger_fetch(req: ObservationFetchRequest, db: Session = Depends(get_db)):
    station = db.get(WeatherStation, req.station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    if req.start_date > req.end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    provider = get_observation_provider(station.source)
    count, cached = fetch_observations(db, provider, station, req.start_date, req.end_date)

    return ObservationFetchResponse(
        station_id=station.id,
        station_code=station.station_code,
        source=station.source,
        start_date=req.start_date,
        end_date=req.end_date,
        count=count,
        cached=cached,
    )


@router.get("", response_model=list[ObservationResponse])
def get_observations(
    station_id: int = Query(...),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
):
    station = db.get(WeatherStation, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")

    return query_observations(db, station_id, start_date, end_date)


@router.get("/validate/{run_id}", response_model=ValidationMetricsResponse)
def validate_forecast(
    run_id: int,
    station_id: int = Query(...),
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    station = db.get(WeatherStation, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")

    # Must have a forecast composite
    if not run.forecast_composite or not run.forecast_composite.get("hours"):
        raise HTTPException(
            status_code=400,
            detail="No forecast composite available for this run",
        )

    forecast_hours = run.forecast_composite["hours"]

    # Auto-fetch observations if not cached
    provider = get_observation_provider(station.source)
    fetch_observations(db, provider, station, run.target_date, run.target_date)

    observations = query_observations(db, station.id, run.target_date, run.target_date)

    if not observations:
        raise HTTPException(
            status_code=404,
            detail="No observations found for this date and station",
        )

    metrics = compute_validation_metrics(forecast_hours, observations)

    return ValidationMetricsResponse(
        tws_mae=metrics.tws_mae,
        tws_max_error=metrics.tws_max_error,
        twd_circular_mae=metrics.twd_circular_mae,
        twd_max_error=metrics.twd_max_error,
        peak_speed_forecast=metrics.peak_speed_forecast,
        peak_speed_observed=metrics.peak_speed_observed,
        peak_speed_error=metrics.peak_speed_error,
        onset_hour_forecast=metrics.onset_hour_forecast,
        onset_hour_observed=metrics.onset_hour_observed,
        onset_error_hours=metrics.onset_error_hours,
        matched_hours=metrics.matched_hours,
        total_forecast_hours=metrics.total_forecast_hours,
        total_observation_hours=metrics.total_observation_hours,
    )
