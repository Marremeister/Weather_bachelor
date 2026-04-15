from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class HourlyObservation:
    observation_time_utc: datetime
    observation_time_local: datetime
    wind_speed: float | None
    wind_direction: float | None
    gust_speed: float | None
    temperature: float | None
    pressure: float | None


@dataclass
class ObservationFetchResult:
    records: list[HourlyObservation]
    raw_payload: dict


class ObservationProvider(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def fetch(
        self,
        station_code: str,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> ObservationFetchResult: ...
