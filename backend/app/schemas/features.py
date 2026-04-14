from datetime import date
from typing import Literal

from pydantic import BaseModel


class AnalysisWindow(BaseModel):
    """Configurable time windows for sea-breeze feature extraction."""

    morning_start: int = 8
    morning_end: int = 10
    afternoon_start: int = 11
    afternoon_end: int = 16
    reference_hour: int = 9
    onshore_sector_min: float = 180.0
    onshore_sector_max: float = 260.0
    min_morning_hours: int = 2
    min_afternoon_hours: int = 3


class DailyFeatures(BaseModel):
    """Output feature vector for one location-day."""

    location_id: int
    date: date

    morning_mean_wind_speed: float | None = None
    morning_mean_wind_direction: float | None = None

    reference_wind_speed: float | None = None
    reference_wind_direction: float | None = None

    afternoon_max_wind_speed: float | None = None
    afternoon_mean_wind_direction: float | None = None

    wind_speed_increase: float | None = None
    wind_direction_shift: float | None = None
    onshore_fraction: float | None = None

    hours_available: int = 0
    morning_hours_used: int = 0
    afternoon_hours_used: int = 0


class SeaBreezeThresholds(BaseModel):
    minimum_speed_increase_mps: float = 1.5
    minimum_direction_shift_degrees: float = 25.0
    minimum_onshore_fraction: float = 0.5


class SeaBreezeClassification(BaseModel):
    classification: Literal["low", "medium", "high"]
    score: float
    indicators: dict[str, bool]


class DayClassificationDetail(BaseModel):
    date: date
    features: DailyFeatures
    classification: SeaBreezeClassification


class SeaBreezePanelResponse(BaseModel):
    run_id: int
    target: DayClassificationDetail | None
    analogs: list[DayClassificationDetail]
    thresholds: SeaBreezeThresholds
    analog_high_count: int
    analog_medium_count: int
    analog_low_count: int
    analog_total: int
