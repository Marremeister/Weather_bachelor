from datetime import date, datetime

from pydantic import BaseModel


class StationResponse(BaseModel):
    id: int
    name: str
    station_code: str
    source: str
    latitude: float
    longitude: float
    timezone: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ObservationFetchRequest(BaseModel):
    station_id: int
    start_date: date
    end_date: date


class ObservationFetchResponse(BaseModel):
    station_id: int
    station_code: str
    source: str
    start_date: date
    end_date: date
    count: int
    cached: bool


class ObservationResponse(BaseModel):
    id: int
    station_id: int
    observation_time_utc: datetime
    observation_time_local: datetime
    wind_speed: float | None
    wind_direction: float | None
    gust_speed: float | None
    temperature: float | None
    pressure: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ValidationMetricsResponse(BaseModel):
    tws_mae: float | None
    tws_max_error: float | None
    twd_circular_mae: float | None
    twd_max_error: float | None
    peak_speed_forecast: float | None
    peak_speed_observed: float | None
    peak_speed_error: float | None
    onset_hour_forecast: int | None
    onset_hour_observed: int | None
    onset_error_hours: int | None
    matched_hours: int
    total_forecast_hours: int
    total_observation_hours: int
