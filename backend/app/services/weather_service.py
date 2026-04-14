from __future__ import annotations

import json
import logging
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.location import Location
from app.models.weather_record import WeatherRecord
from app.services.open_meteo_provider import parse_open_meteo_response
from app.services.weather_provider import HourlyRecord, WeatherProvider

logger = logging.getLogger(__name__)

# Sources whose filesystem cache uses Open-Meteo JSON format
_OPEN_METEO_JSON_SOURCES = {"open_meteo", "open_meteo_forecast", "gfs_open_meteo"}


def get_provider(source_name: str) -> WeatherProvider:
    """Registry mapping source names to provider instances."""
    from app.services.open_meteo_provider import OpenMeteoForecastProvider, OpenMeteoProvider

    if source_name == "open_meteo":
        return OpenMeteoProvider()
    if source_name == "open_meteo_forecast":
        return OpenMeteoForecastProvider()
    if source_name == "gfs":
        from app.services.gfs_forecast_provider import GfsForecastProvider
        return GfsForecastProvider()
    if source_name == "gfs_open_meteo":
        from app.services.gfs_open_meteo_provider import GfsOpenMeteoProvider
        return GfsOpenMeteoProvider()
    raise ValueError(f"Unknown weather source: {source_name!r}")


def _cache_path(source: str, lat: float, lng: float, start: date, end: date) -> Path:
    lat_r = f"{lat:.3f}"
    lng_r = f"{lng:.3f}"
    return (
        Path(settings.weather_cache_dir)
        / source
        / f"{lat_r}_{lng_r}"
        / f"{start.isoformat()}__{end.isoformat()}.json"
    )


def _expected_hours(start: date, end: date, source: str = "") -> int:
    """Expected record count for a date range.

    Open-Meteo sources provide 24 hourly records per day.
    GFS provides one record per analysis-window hour (default 9/day).
    """
    days = (end - start).days + 1
    if source == "gfs":
        hours_per_day = (
            settings.gfs_analysis_local_end
            - settings.gfs_analysis_local_start
            + 1
        )
        return days * hours_per_day
    return days * 24


def _upsert_records(
    db: Session, location_id: int, source: str, records: list[HourlyRecord]
) -> int:
    if not records:
        return 0

    # Check if any records carry model_run_time (i.e. GFS forecast data).
    # If so, use on_conflict_do_update so newer model runs replace stale rows.
    has_model_run = any(r.model_run_time is not None for r in records)

    rows = [
        {
            "location_id": location_id,
            "source": source,
            "valid_time_utc": r.valid_time_utc,
            "valid_time_local": r.valid_time_local,
            "true_wind_speed": r.true_wind_speed,
            "true_wind_direction": r.true_wind_direction,
            "temperature": r.temperature,
            "pressure": r.pressure,
            "cloud_cover": r.cloud_cover,
            "model_run_time": r.model_run_time,
            "forecast_hour": r.forecast_hour,
            "model_name": r.model_name,
            "raw_payload": None,
        }
        for r in records
    ]
    # PostgreSQL limits bind parameters to 65,535 per query.
    # Each row has 14 columns, so batch at 4,000 rows to stay well under.
    batch_size = 4000
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        stmt = insert(WeatherRecord).values(batch)
        if has_model_run:
            # Replace weather values when a newer model run arrives for the
            # same valid time, so forecasts stay current.
            stmt = stmt.on_conflict_do_update(
                index_elements=["location_id", "source", "valid_time_utc"],
                set_={
                    "true_wind_speed": stmt.excluded.true_wind_speed,
                    "true_wind_direction": stmt.excluded.true_wind_direction,
                    "temperature": stmt.excluded.temperature,
                    "pressure": stmt.excluded.pressure,
                    "cloud_cover": stmt.excluded.cloud_cover,
                    "model_run_time": stmt.excluded.model_run_time,
                    "forecast_hour": stmt.excluded.forecast_hour,
                    "model_name": stmt.excluded.model_name,
                },
            )
        else:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["location_id", "source", "valid_time_utc"]
            )
        db.execute(stmt)
    db.commit()
    return len(records)


def _count_existing(
    db: Session, location_id: int, source: str, start: date, end: date
) -> int:
    location = db.get(Location, location_id)
    if location is None:
        return 0
    tz = ZoneInfo(location.timezone)
    start_dt = datetime.combine(start, time.min, tzinfo=tz)
    end_dt = datetime.combine(end, time(23, 59, 59), tzinfo=tz)
    start_utc = start_dt.astimezone(ZoneInfo("UTC"))
    end_utc = end_dt.astimezone(ZoneInfo("UTC"))

    count = db.execute(
        select(func.count())
        .select_from(WeatherRecord)
        .where(
            WeatherRecord.location_id == location_id,
            WeatherRecord.source == source,
            WeatherRecord.valid_time_utc >= start_utc,
            WeatherRecord.valid_time_utc <= end_utc,
        )
    ).scalar()
    return count or 0


def _gfs_cache_is_fresh(
    db: Session, location: Location, start: date, end: date
) -> bool:
    """Check whether cached GFS records use the latest available model run.

    Queries the most recent model_run_time stored for source='gfs' in the
    date range and compares it to the current latest available GFS cycle.
    Returns False (stale) if a newer cycle is available.
    """
    from app.services.gfs_forecast_provider import _latest_available_cycle

    tz = ZoneInfo(location.timezone)
    start_dt = datetime.combine(start, time.min, tzinfo=tz)
    end_dt = datetime.combine(end, time(23, 59, 59), tzinfo=tz)
    start_utc = start_dt.astimezone(ZoneInfo("UTC"))
    end_utc = end_dt.astimezone(ZoneInfo("UTC"))

    stored_mrt = db.execute(
        select(func.max(WeatherRecord.model_run_time))
        .where(
            WeatherRecord.location_id == location.id,
            WeatherRecord.source == "gfs",
            WeatherRecord.valid_time_utc >= start_utc,
            WeatherRecord.valid_time_utc <= end_utc,
        )
    ).scalar()

    if stored_mrt is None:
        return False  # no records at all

    now_utc = datetime.now(tz=ZoneInfo("UTC"))
    latest_run, _ = _latest_available_cycle(now_utc)

    # Fresh if the stored model run is the same as (or newer than) the latest
    return stored_mrt >= latest_run


def fetch_weather(
    db: Session,
    provider: WeatherProvider,
    location: Location,
    start_date: date,
    end_date: date,
) -> tuple[int, bool]:
    """Fetch weather data with 3-tier cache: Postgres -> filesystem -> API.

    Returns (record_count, cached).
    """
    source = provider.source_name
    expected = _expected_hours(start_date, end_date, source)

    # Tier 1: Check Postgres
    existing = _count_existing(db, location.id, source, start_date, end_date)
    if existing >= expected * 0.9:
        # For GFS, also verify the cached data is from the latest model run.
        if source == "gfs":
            if not _gfs_cache_is_fresh(db, location, start_date, end_date):
                logger.info(
                    "Postgres GFS records stale for %s, re-fetching", location.name
                )
            else:
                logger.info("Postgres cache hit: %d records for %s", existing, location.name)
                return existing, True
        else:
            logger.info("Postgres cache hit: %d records for %s", existing, location.name)
            return existing, True

    # Tier 2: Check filesystem cache (only for Open-Meteo JSON sources)
    if source in _OPEN_METEO_JSON_SOURCES:
        cache_file = _cache_path(
            source, location.latitude, location.longitude, start_date, end_date
        )
        if cache_file.exists():
            logger.info("Filesystem cache hit: %s", cache_file)
            raw = json.loads(cache_file.read_text())
            records = parse_open_meteo_response(raw, location.timezone)
            _upsert_records(db, location.id, source, records)
            count = _count_existing(db, location.id, source, start_date, end_date)
            return count, True

    # Tier 3: Fetch from API
    logger.info(
        "API fetch: %s for %s (%s to %s)",
        source,
        location.name,
        start_date,
        end_date,
    )
    result = provider.fetch(
        latitude=location.latitude,
        longitude=location.longitude,
        start_date=start_date,
        end_date=end_date,
        timezone=location.timezone,
    )

    # Write raw JSON to filesystem cache (only for Open-Meteo JSON sources)
    if source in _OPEN_METEO_JSON_SOURCES:
        cache_file = _cache_path(
            source, location.latitude, location.longitude, start_date, end_date
        )
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result.raw_payload))

    # Upsert into Postgres
    _upsert_records(db, location.id, source, result.records)
    count = _count_existing(db, location.id, source, start_date, end_date)
    return count, False
