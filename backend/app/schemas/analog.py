"""Schemas for analog matching analysis."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.weather import WeatherRecordResponse


class AnalysisRequest(BaseModel):
    location_id: int
    target_date: date
    historical_start_date: date
    historical_end_date: date
    top_n: int = Field(default=10, ge=1, le=50)
    mode: str = "historical"
    forecast_source: str | None = None
    historical_source: str | None = None


class AnalogCandidate(BaseModel):
    """Internal value object produced by the ranking pipeline."""

    date: date
    rank: int
    distance: float
    similarity_score: float
    features: dict[str, float | None]


class AnalogResultResponse(BaseModel):
    id: int
    analysis_run_id: int
    analog_date: date
    rank: int
    similarity_score: float | None
    distance: float | None
    summary: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunResponse(BaseModel):
    id: int
    location_id: int
    target_date: date
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    summary: str | None
    historical_start_date: date | None
    historical_end_date: date | None
    top_n: int | None
    mode: str | None = None
    forecast_source: str | None = None
    historical_source: str | None = None
    forecast_composite: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalysisRunDetailResponse(AnalysisRunResponse):
    analogs: list[AnalogResultResponse] = []


class DayHourlyRecords(BaseModel):
    date: date
    rank: int | None = None
    similarity_score: float | None = None
    records: list[WeatherRecordResponse] = []


class AnalogHourlyResponse(BaseModel):
    run_id: int
    target: DayHourlyRecords
    analogs: list[DayHourlyRecords]


class ForecastCompositeHour(BaseModel):
    hour_local: int
    median_tws: float | None = None
    p25_tws: float | None = None
    p75_tws: float | None = None
    p10_tws: float | None = None
    p90_tws: float | None = None
    circular_mean_twd: float | None = None
    twd_circular_std: float | None = None
    twd_arc_radius_75: float | None = None
    analog_count: int = 0


class ForecastCompositeResponse(BaseModel):
    run_id: int
    gate_result: str
    hours: list[ForecastCompositeHour] | None = None
    summary: str | None = None
