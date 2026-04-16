"""Feature library service: build and query precomputed daily feature vectors."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta
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


def _date_range_for_source(source: str) -> tuple[int, int, list[int], int]:
    """Return ``(start_year, end_year, months, chunk_months)`` for *source*.

    ``chunk_months`` controls how finely the season is sliced by
    :func:`_season_date_chunks`.  ERA5 builds are coarse (one chunk per
    season/year) because the CDS API prefers large requests; GFS
    hindcast builds are fine (one chunk per month) so partial failures
    are isolated and resume cost stays low.
    """
    if source == "era5":
        return (
            settings.era5_start_year,
            settings.era5_end_year,
            settings.era5_months_list,
            12,  # effectively one chunk per year (covers all configured months)
        )
    if source == "gfs_hindcast":
        return (
            settings.gfs_hindcast_start_year,
            settings.gfs_hindcast_end_year,
            settings.gfs_hindcast_months_list,
            settings.gfs_hindcast_chunk_months,
        )
    raise ValueError(f"No library date range configured for source {source!r}")


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _season_date_chunks(
    start_year: int,
    end_year: int,
    months: list[int],
    chunk_months: int = 12,
) -> list[tuple[date, date]]:
    """Return ``(start, end)`` pairs covering the configured season.

    When ``chunk_months`` is 12 (or any value ≥ ``len(months)``) the
    helper emits one chunk per year spanning the full configured
    season — historical behaviour.  Smaller values slice the season
    into consecutive ``chunk_months``-month groups so long builds can
    progress/fail incrementally.
    """
    if not months:
        return []

    ordered = sorted(months)
    chunks: list[tuple[date, date]] = []

    for year in range(start_year, end_year + 1):
        if chunk_months >= len(ordered):
            chunk_start, _ = _month_range(year, ordered[0])
            _, chunk_end = _month_range(year, ordered[-1])
            chunks.append((chunk_start, chunk_end))
            continue

        # Group consecutive months into buckets of size `chunk_months`.
        for i in range(0, len(ordered), chunk_months):
            bucket = ordered[i : i + chunk_months]
            chunk_start, _ = _month_range(year, bucket[0])
            _, chunk_end = _month_range(year, bucket[-1])
            chunks.append((chunk_start, chunk_end))

    return chunks


def _days_already_built(
    db: Session,
    location_id: int,
    source: str,
    config_hash: str,
    start: date,
    end: date,
) -> set[date]:
    """Return the set of dates already present in ``daily_features`` for
    the given source+hash.  Used by the resume guard so a restarted
    build skips work it has already persisted."""
    rows = db.execute(
        select(DailyFeatureRow.date)
        .where(
            DailyFeatureRow.location_id == location_id,
            DailyFeatureRow.source == source,
            DailyFeatureRow.feature_config_hash == config_hash,
            DailyFeatureRow.date >= start,
            DailyFeatureRow.date <= end,
        )
    ).scalars().all()
    return set(rows)


def _warn_on_hash_mismatch(
    db: Session,
    location_id: int,
    source: str,
    config_hash: str,
) -> None:
    """Log a warning if any *other* source has daily_features rows using a
    different feature_config_hash.  Non-fatal — divergent analysis
    windows between sources are legitimate — but worth surfacing."""
    other_hashes = (
        db.execute(
            select(DailyFeatureRow.source, DailyFeatureRow.feature_config_hash)
            .where(
                DailyFeatureRow.location_id == location_id,
                DailyFeatureRow.source != source,
            )
            .distinct()
        )
        .all()
    )
    mismatched = [
        (src, h) for (src, h) in other_hashes if h != config_hash
    ]
    if mismatched:
        logger.warning(
            "Library build (%s): other sources use a different "
            "feature_config_hash — rebuild may be needed if configs "
            "should stay aligned: %s (current hash=%s)",
            source,
            mismatched,
            config_hash,
        )


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
    try:
        start_year, end_year, months, chunk_months = _date_range_for_source(source)
    except ValueError:
        logger.error(
            "Library build: no date range configured for source %r", source
        )
        return

    chunks = _season_date_chunks(start_year, end_year, months, chunk_months)

    db: Session = SessionLocal()
    try:
        location = db.get(Location, location_id)
        if location is None:
            logger.error("Library build: location %d not found", location_id)
            return

        _warn_on_hash_mismatch(db, location_id, source, config_hash)

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
                # Resume guard: if every day in this chunk is already
                # persisted with the current feature_config_hash, skip
                # the network fetch + recomputation entirely.
                built = _days_already_built(
                    db, location_id, source, config_hash, chunk_start, chunk_end
                )
                total_days = (chunk_end - chunk_start).days + 1
                if len(built) >= total_days:
                    logger.info(
                        "Library build chunk %d/%d already complete (%s to %s),"
                        " skipping",
                        idx + 1, len(chunks), chunk_start, chunk_end,
                    )
                    job.completed_chunks = idx + 1
                    db.commit()
                    continue

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

                # 3. Group by date, skip days already built
                by_date: dict[date, list] = defaultdict(list)
                for rec in records:
                    day = rec.valid_time_local.date()
                    if day in built:
                        continue
                    by_date[day].append(rec)

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


def get_library_status(
    db: Session,
    location_id: int,
    source: str | None = None,
) -> dict | None:
    """Return the most recent library build job info for a location.

    When *source* is provided, only jobs for that source are considered;
    otherwise the latest job across all sources is returned (preserving
    the original behaviour for callers that don't care about source).
    """
    stmt = (
        select(LibraryBuildJob)
        .where(LibraryBuildJob.location_id == location_id)
        .order_by(LibraryBuildJob.id.desc())
        .limit(1)
    )
    if source is not None:
        stmt = (
            select(LibraryBuildJob)
            .where(
                LibraryBuildJob.location_id == location_id,
                LibraryBuildJob.source == source,
            )
            .order_by(LibraryBuildJob.id.desc())
            .limit(1)
        )
    job = db.execute(stmt).scalar_one_or_none()

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
