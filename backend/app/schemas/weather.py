from datetime import date, datetime

from pydantic import BaseModel


class WeatherFetchRequest(BaseModel):
    location_id: int
    start_date: date
    end_date: date
    source: str = "open_meteo"


class WeatherFetchResponse(BaseModel):
    location_id: int
    source: str
    start_date: date
    end_date: date
    records_count: int
    cached: bool


class WeatherRecordResponse(BaseModel):
    id: int
    location_id: int
    source: str
    valid_time_utc: datetime
    valid_time_local: datetime
    true_wind_speed: float | None
    true_wind_direction: float | None
    temperature: float | None
    pressure: float | None
    cloud_cover: float | None
    model_run_time: datetime | None = None
    forecast_hour: int | None = None
    model_name: str | None = None

    model_config = {"from_attributes": True}
