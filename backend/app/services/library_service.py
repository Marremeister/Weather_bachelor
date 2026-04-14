"""Feature library service: build and query precomputed daily feature vectors."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.daily_feature import DailyFeatureRow
from app.models.library_build_job import LibraryBuildJob
from app.models.location import Location
from app.schemas.features import AnalysisWindow, DailyFeatures
from app.services.feature_service import (
    _DEFAULT_FEATURE_NAMES,
    compute_daily_features,
    compute_feature_config_hash,
)
from app.services.weather_service import fetch_weather, get_provider

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _season_date_chunks(
    start_year: int, end_year: int, months: list[int]
) -> list[tuple[date, date]]:
    """Return per-year (start, end) pairs covering the given months."""
    chunks: list[tuple[date, date]] = []
    for year in range(start_year, end_year + 1):
        first_month = min(months)
        last_month = max(months)
        chunk_start = date(year, first_month, 1)
        # Last day of last_month
        if last_month == 12:
            chunk_end = date(year, 12, 31)
        else:
            chunk_end = date(year, last_month + 1, 1) - __import__("datetime").timedelta(days=1)
        chunks.append((chunk_start, chunk_end))
    return chunks


# ------------------------------------------------------------------
# Background build
# ------------------------------------------------------------------


def build_feature_library(
    location_id: int,
    source: str,
    window: AnalysisWindow | None = None,
) -> None:
    """Build the precomputed feature library.  Runs as a BackgroundTask.

    Creates its own DB session so it can be called from a background thread.
    """
    if window is None:
        window = AnalysisWindow()

    config_hash = compute_feature_config_hash(window)
    months = settings.era5_months_list
    chunks = _season_date_chunks(settings.era5_start_year, settings.era5_end_year, months)

    db: Session = SessionLocal()
    try:
        location = db.get(Location, location_id)
        if location is None:
            logger.error("Library build: location %d not found", location_id)
            return

        job = LibraryBuildJob(
            location_id=location_id,
            source=source,
            total_chunks=len(chunks),
            completed_chunks=0,
            status="running",
            started_at=datetime.now(tz=ZoneInfo("UTC")),
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        provider = get_provider(source)
        errors: list[str] = []

        for idx, (chunk_start, chunk_end) in enumerate(chunks):
            try:
                # 1. Fetch weather data into Postgres
                fetch_weather(db, provider, location, chunk_start, chunk_end)

                # 2. Load weather records for this chunk
                start_dt = datetime.combine(chunk_start, time.min)
                end_dt = datetime.combine(chunk_end, time(23, 59, 59))
                from app.models.weather_record import WeatherRecord

                records = (
                    db.execute(
                        select(WeatherRecord)
                        .where(
                            WeatherRecord.location_id == location_id,
                            WeatherRecord.source == source,
                            WeatherRecord.valid_time_local >= start_dt,
                            WeatherRecord.valid_time_local <= end_dt,
                        )
                        .order_by(WeatherRecord.valid_time_local)
                    )
                    .scalars()
                    .all()
                )

                # 3. Group by date
                by_date: dict[date, list] = defaultdict(list)
                for rec in records:
                    by_date[rec.valid_time_local.date()].append(rec)

                # 4. Compute features and upsert
                rows = []
                for day, day_records in by_date.items():
                    feat = compute_daily_features(day_records, location_id, day, window)
                    feat_dict = {
                        name: getattr(feat, name, None)
                        for name in _DEFAULT_FEATURE_NAMES
                    }
                    # Also store metadata fields
                    feat_dict["hours_available"] = feat.hours_available
                    feat_dict["morning_hours_used"] = feat.morning_hours_used
                    feat_dict["afternoon_hours_used"] = feat.afternoon_hours_used

                    rows.append(
                        {
                            "location_id": location_id,
                            "source": source,
                            "date": day,
                            "features_json": feat_dict,
                            "feature_config_hash": config_hash,
                        }
                    )

                if rows:
                    batch_size = 1000
                    for i in range(0, len(rows), batch_size):
                        batch = rows[i : i + batch_size]
                        stmt = insert(DailyFeatureRow).values(batch)
                        stmt = stmt.on_conflict_do_nothing(
                            constraint="uq_daily_features_loc_src_date_hash"
                        )
                        db.execute(stmt)
                    db.commit()

                # 5. Update progress
                job.completed_chunks = idx + 1
                db.commit()
                logger.info(
                    "Library build chunk %d/%d done (%s to %s)",
                    idx + 1, len(chunks), chunk_start, chunk_end,
                )

            except Exception as exc:
                logger.exception(
                    "Library build error on chunk %d (%s to %s)",
                    idx, chunk_start, chunk_end,
                )
                errors.append(f"{chunk_start}-{chunk_end}: {exc}")
                job.error_message = "; ".join(errors[-3:])
                job.completed_chunks = idx + 1
                db.commit()

        job.status = "completed" if not errors else "partial"
        job.finished_at = datetime.now(tz=ZoneInfo("UTC"))
        db.commit()
    except Exception:
        logger.exception("Library build failed entirely for location %d", location_id)
        try:
            job.status = "failed"
            job.finished_at = datetime.now(tz=ZoneInfo("UTC"))
            db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ------------------------------------------------------------------
# Query helpers
# ------------------------------------------------------------------


def get_library_status(db: Session, location_id: int) -> dict | None:
    """Return the most recent library build job info for a location."""
    job = db.execute(
        select(LibraryBuildJob)
        .where(LibraryBuildJob.location_id == location_id)
        .order_by(LibraryBuildJob.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if job is None:
        return None

    return {
        "id": job.id,
        "location_id": job.location_id,
        "source": job.source,
        "total_chunks": job.total_chunks,
        "completed_chunks": job.completed_chunks,
        "status": job.status,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


def get_precomputed_features(
    db: Session,
    location_id: int,
    source: str,
    config_hash: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[DailyFeatures]:
    """Load precomputed DailyFeatures from the daily_features table.

    When *start_date* and *end_date* are supplied the query is filtered to
    that range so callers only receive candidates from the requested
    historical window.
    """
    stmt = (
        select(DailyFeatureRow)
        .where(
            DailyFeatureRow.location_id == location_id,
            DailyFeatureRow.source == source,
            DailyFeatureRow.feature_config_hash == config_hash,
        )
    )
    if start_date is not None:
        stmt = stmt.where(DailyFeatureRow.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(DailyFeatureRow.date <= end_date)
    stmt = stmt.order_by(DailyFeatureRow.date)

    rows = db.execute(stmt).scalars().all()

    features: list[DailyFeatures] = []
    for row in rows:
        fj = row.features_json
        features.append(
            DailyFeatures(
                location_id=row.location_id,
                date=row.date,
                morning_mean_wind_speed=fj.get("morning_mean_wind_speed"),
                morning_mean_wind_direction=fj.get("morning_mean_wind_direction"),
                reference_wind_speed=fj.get("reference_wind_speed"),
                reference_wind_direction=fj.get("reference_wind_direction"),
                afternoon_max_wind_speed=fj.get("afternoon_max_wind_speed"),
                afternoon_mean_wind_direction=fj.get("afternoon_mean_wind_direction"),
                wind_speed_increase=fj.get("wind_speed_increase"),
                wind_direction_shift=fj.get("wind_direction_shift"),
                onshore_fraction=fj.get("onshore_fraction"),
                hours_available=fj.get("hours_available", 0),
                morning_hours_used=fj.get("morning_hours_used", 0),
                afternoon_hours_used=fj.get("afternoon_hours_used", 0),
            )
        )

    return features
