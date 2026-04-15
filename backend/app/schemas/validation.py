"""Schemas for batch validation and method evaluation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ValidationRunRequest(BaseModel):
    location_id: int
    evaluation_method: str = Field(
        default="temporal_split",
        pattern="^(temporal_split|leave_one_out)$",
    )
    exclusion_buffer_days: int = Field(default=7, ge=0, le=30)
    top_n: int = Field(default=10, ge=1, le=50)
    library_start_date: date | None = None
    library_end_date: date | None = None
    test_start_date: date | None = None
    test_end_date: date | None = None
    historical_source: str | None = None
    forecast_source: str | None = None


class AggregateMetrics(BaseModel):
    # Classification metrics
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None

    # Continuous metrics (sea breeze days only)
    tws_mae: float | None = None
    tws_rmse: float | None = None
    twd_circular_mae: float | None = None
    peak_speed_error_mean: float | None = None
    peak_speed_bias_mean: float | None = None
    onset_error_mean: float | None = None
    skill_score: float | None = None

    total_days: int = 0
    insufficient_days: int = 0
    sea_breeze_days: int = 0
    forecast_produced_days: int = 0


class GateSensitivityEntry(BaseModel):
    gate_level: int  # 1, 2, or 3
    gate_label: str  # ">=1", ">=2", ">=3"
    coverage: float | None = None
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    conditional_tws_mae: float | None = None
    conditional_tws_rmse: float | None = None


class SourceStratificationEntry(BaseModel):
    source: str
    day_count: int = 0
    tws_mae: float | None = None
    tws_rmse: float | None = None
    twd_circular_mae: float | None = None


class ValidationDayResult(BaseModel):
    date: date
    forecast_source_used: str | None = None
    gate_result: str | None = None
    classification_count_true: int | None = None
    actual_classification: str | None = None
    actual_count_true: int | None = None
    tws_mae: float | None = None
    tws_rmse: float | None = None
    twd_circular_mae: float | None = None
    peak_speed_forecast: float | None = None
    peak_speed_actual: float | None = None
    peak_speed_error: float | None = None
    peak_speed_bias: float | None = None
    onset_hour_forecast: int | None = None
    onset_hour_actual: int | None = None
    onset_error_hours: int | None = None
    analog_count: int | None = None


class ValidationRunStatusResponse(BaseModel):
    id: int
    status: str
    total_days: int
    completed_days: int
    error_message: str | None = None

    model_config = {"from_attributes": True}


class ValidationRunResponse(BaseModel):
    id: int
    location_id: int
    evaluation_method: str
    exclusion_buffer_days: int
    top_n: int
    library_start_date: date | None = None
    library_end_date: date | None = None
    test_start_date: date | None = None
    test_end_date: date | None = None
    historical_source: str | None = None
    forecast_source: str | None = None
    status: str
    total_days: int
    completed_days: int
    error_message: str | None = None
    aggregate_metrics: dict | None = None
    gate_sensitivity: list | None = None
    source_stratification: list | None = None
    per_day_results: list | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class ValidationRunSummary(BaseModel):
    id: int
    location_id: int
    evaluation_method: str
    status: str
    total_days: int
    completed_days: int
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
