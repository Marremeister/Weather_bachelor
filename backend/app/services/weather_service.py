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


def _cache_path(source: str, lat: float, lng: float, start: date, end: date) -> Path:
    lat_r = f"{lat:.3f}"
    lng_r = f"{lng:.3f}"
    return (
        Path(settings.weather_cache_dir)
        / source
        / f"{lat_r}_{lng_r}"
        / f"{start.isoformat()}__{end.isoformat()}.json"
    )


def _expected_hours(start: date, end: date) -> int:
    return (end - start).days * 24 + 24


def _upsert_records(
    db: Session, location_id: int, source: str, records: list[HourlyRecord]
) -> int:
    if not records:
        return 0
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
            "raw_payload": None,
        }
        for r in records
    ]
    stmt = (
        insert(WeatherRecord)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=["location_id", "source", "valid_time_utc"]
        )
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
    expected = _expected_hours(start_date, end_date)

    # Tier 1: Check Postgres
    existing = _count_existing(db, location.id, source, start_date, end_date)
    if existing >= expected * 0.9:
        logger.info("Postgres cache hit: %d records for %s", existing, location.name)
        return existing, True

    # Tier 2: Check filesystem cache
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

    # Write raw JSON to filesystem cache
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(result.raw_payload))

    # Upsert into Postgres
    _upsert_records(db, location.id, source, result.records)
    count = _count_existing(db, location.id, source, start_date, end_date)
    return count, False
