from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class HourlyRecord:
    valid_time_utc: datetime
    valid_time_local: datetime
    true_wind_speed: float | None
    true_wind_direction: float | None
    temperature: float | None
    pressure: float | None
    cloud_cover: float | None


@dataclass
class FetchResult:
    records: list[HourlyRecord]
    raw_payload: dict


class WeatherProvider(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult: ...
