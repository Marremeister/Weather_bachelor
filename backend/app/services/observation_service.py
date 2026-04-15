from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.observation import Observation
from app.models.weather_station import WeatherStation
from app.services.observation_provider import HourlyObservation, ObservationProvider

logger = logging.getLogger(__name__)


def get_observation_provider(source_name: str) -> ObservationProvider:
    """Registry mapping source names to observation provider instances."""
    from app.services.iem_asos_provider import IemAsosProvider

    if source_name == "iem_asos":
        return IemAsosProvider()
    raise ValueError(f"Unknown observation source: {source_name!r}")


def upsert_observations(
    db: Session, station_id: int, records: list[HourlyObservation]
) -> int:
    """Batch insert observations, skipping duplicates on conflict."""
    if not records:
        return 0

    rows = [
        {
            "station_id": station_id,
            "observation_time_utc": r.observation_time_utc,
            "observation_time_local": r.observation_time_local,
            "wind_speed": r.wind_speed,
            "wind_direction": r.wind_direction,
            "gust_speed": r.gust_speed,
            "temperature": r.temperature,
            "pressure": r.pressure,
            "raw_payload": None,
        }
        for r in records
    ]

    batch_size = 4000
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        stmt = insert(Observation).values(batch)
        stmt = stmt.on_conflict_do_nothing(
            constraint="uq_observations_station_time"
        )
        db.execute(stmt)
    db.commit()
    return len(records)


def _count_existing(
    db: Session, station_id: int, start_date: date, end_date: date, timezone: str
) -> int:
    tz = ZoneInfo(timezone)
    start_dt = datetime.combine(start_date, time.min, tzinfo=tz)
    end_dt = datetime.combine(end_date, time(23, 59, 59), tzinfo=tz)
    start_utc = start_dt.astimezone(ZoneInfo("UTC"))
    end_utc = end_dt.astimezone(ZoneInfo("UTC"))

    count = db.execute(
        select(func.count())
        .select_from(Observation)
        .where(
            Observation.station_id == station_id,
            Observation.observation_time_utc >= start_utc,
            Observation.observation_time_utc <= end_utc,
        )
    ).scalar()
    return count or 0


def fetch_observations(
    db: Session,
    provider: ObservationProvider,
    station: WeatherStation,
    start_date: date,
    end_date: date,
) -> tuple[int, bool]:
    """Fetch observations with DB cache check, then API fallback.

    Returns (record_count, cached).
    """
    days = (end_date - start_date).days + 1
    expected = days * 24  # hourly METAR

    existing = _count_existing(db, station.id, start_date, end_date, station.timezone)
    if existing >= expected * 0.8:
        logger.info("Observation cache hit: %d records for %s", existing, station.station_code)
        return existing, True

    logger.info(
        "Observation API fetch: %s for %s (%s to %s)",
        provider.source_name, station.station_code, start_date, end_date,
    )
    result = provider.fetch(
        station_code=station.station_code,
        start_date=start_date,
        end_date=end_date,
        timezone=station.timezone,
    )

    upsert_observations(db, station.id, result.records)
    count = _count_existing(db, station.id, start_date, end_date, station.timezone)
    return count, False


def query_observations(
    db: Session, station_id: int, start_date: date, end_date: date
) -> list[Observation]:
    """Query stored observations by local time."""
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time(23, 59, 59))

    return (
        db.query(Observation)
        .filter(
            Observation.station_id == station_id,
            Observation.observation_time_local >= start_dt,
            Observation.observation_time_local <= end_dt,
        )
        .order_by(Observation.observation_time_utc)
        .all()
    )


# --- Validation metrics ---


@dataclass
class ValidationMetrics:
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


def _circular_diff(a: float, b: float) -> float:
    """Absolute circular difference between two angles in degrees."""
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def _detect_onset_hour(
    hourly: dict[int, tuple[float | None, float | None]],
    speed_threshold: float = 3.0,
    dir_min: float = 180.0,
    dir_max: float = 260.0,
) -> int | None:
    """Find first hour with onshore wind > threshold in direction sector."""
    for hour in sorted(hourly.keys()):
        spd, direction = hourly[hour]
        if spd is not None and direction is not None:
            if spd > speed_threshold and dir_min <= direction <= dir_max:
                return hour
    return None


def compute_validation_metrics(
    forecast_hours: list[dict],
    observations: list[Observation],
) -> ValidationMetrics:
    """Compare forecast composite hours against observed data.

    forecast_hours: list of dicts with keys hour_local, median_tws,
                    circular_mean_twd (from ForecastCompositeData.hours)
    observations: list of Observation model instances
    """
    # Build observation lookup by local hour
    obs_by_hour: dict[int, Observation] = {}
    for obs in observations:
        h = obs.observation_time_local.hour
        # Keep the first observation per hour (hourly METAR)
        if h not in obs_by_hour:
            obs_by_hour[h] = obs

    # Build forecast lookup by local hour
    fc_by_hour: dict[int, dict] = {}
    for fh in forecast_hours:
        fc_by_hour[fh["hour_local"]] = fh

    # Match on the 11-16 window (typical sea breeze hours)
    analysis_hours = range(11, 17)
    tws_errors: list[float] = []
    twd_errors: list[float] = []

    for h in analysis_hours:
        fc = fc_by_hour.get(h)
        obs = obs_by_hour.get(h)
        if fc is None or obs is None:
            continue

        fc_tws = fc.get("median_tws")
        obs_tws = obs.wind_speed
        if fc_tws is not None and obs_tws is not None:
            tws_errors.append(abs(fc_tws - obs_tws))

        fc_twd = fc.get("circular_mean_twd")
        obs_twd = obs.wind_direction
        if fc_twd is not None and obs_twd is not None:
            twd_errors.append(_circular_diff(fc_twd, obs_twd))

    tws_mae = sum(tws_errors) / len(tws_errors) if tws_errors else None
    tws_max_error = max(tws_errors) if tws_errors else None
    twd_circular_mae = sum(twd_errors) / len(twd_errors) if twd_errors else None
    twd_max_error = max(twd_errors) if twd_errors else None

    # Peak speed comparison
    fc_peak = max(
        (fh.get("median_tws") for fh in forecast_hours if fh.get("median_tws") is not None),
        default=None,
    )
    obs_peak = max(
        (o.wind_speed for o in observations if o.wind_speed is not None),
        default=None,
    )
    peak_error = abs(fc_peak - obs_peak) if fc_peak is not None and obs_peak is not None else None

    # Onset hour comparison
    fc_onset_data: dict[int, tuple[float | None, float | None]] = {}
    for fh in forecast_hours:
        fc_onset_data[fh["hour_local"]] = (fh.get("median_tws"), fh.get("circular_mean_twd"))

    obs_onset_data: dict[int, tuple[float | None, float | None]] = {}
    for h, obs in obs_by_hour.items():
        obs_onset_data[h] = (obs.wind_speed, obs.wind_direction)

    onset_fc = _detect_onset_hour(fc_onset_data)
    onset_obs = _detect_onset_hour(obs_onset_data)
    onset_error = abs(onset_fc - onset_obs) if onset_fc is not None and onset_obs is not None else None

    return ValidationMetrics(
        tws_mae=round(tws_mae, 3) if tws_mae is not None else None,
        tws_max_error=round(tws_max_error, 3) if tws_max_error is not None else None,
        twd_circular_mae=round(twd_circular_mae, 1) if twd_circular_mae is not None else None,
        twd_max_error=round(twd_max_error, 1) if twd_max_error is not None else None,
        peak_speed_forecast=round(fc_peak, 2) if fc_peak is not None else None,
        peak_speed_observed=round(obs_peak, 2) if obs_peak is not None else None,
        peak_speed_error=round(peak_error, 2) if peak_error is not None else None,
        onset_hour_forecast=onset_fc,
        onset_hour_observed=onset_obs,
        onset_error_hours=onset_error,
        matched_hours=len(tws_errors),
        total_forecast_hours=len(forecast_hours),
        total_observation_hours=len(obs_by_hour),
    )
