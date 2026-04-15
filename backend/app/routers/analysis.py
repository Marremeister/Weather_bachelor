"""Endpoints for analog matching analysis."""

import csv
import io
import datetime as _dt
from datetime import time

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.analog_result import AnalogResult
from app.models.location import Location
from app.models.weather_record import WeatherRecord
from app.schemas.analog import (
    AnalogHourlyResponse,
    AnalogResultResponse,
    AnalysisRequest,
    AnalysisRunDetailResponse,
    AnalysisRunResponse,
    DayHourlyRecords,
    ForecastCompositeHour,
    ForecastCompositeResponse,
)
from app.schemas.weather import WeatherRecordResponse
from app.schemas.features import (
    AnalysisWindow,
    DayClassificationDetail,
    DistanceDistributionResponse,
    DistanceEntry,
    SeaBreezePanelResponse,
    SeaBreezeThresholds,
)
from app.services.analog_service import compute_all_distances, run_analog_analysis
from app.services.feature_service import compute_daily_features, compute_feature_config_hash
from app.services.classification_service import classify_sea_breeze
from app.services.library_service import get_precomputed_features

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("", response_model=list[AnalysisRunResponse])
def list_analysis_runs(
    location_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(AnalysisRun).order_by(AnalysisRun.created_at.desc())
    if location_id is not None:
        stmt = stmt.where(AnalysisRun.location_id == location_id)
    runs = db.execute(stmt).scalars().all()
    return [AnalysisRunResponse.model_validate(r) for r in runs]


@router.post("/run", response_model=AnalysisRunDetailResponse)
def trigger_analysis(
    request: AnalysisRequest,
    db: Session = Depends(get_db),
):
    location = db.get(Location, request.location_id)
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    if request.historical_end_date <= request.historical_start_date:
        raise HTTPException(
            status_code=400,
            detail="historical_end_date must be after historical_start_date",
        )

    if request.mode not in ("historical", "forecast"):
        raise HTTPException(
            status_code=400,
            detail="mode must be 'historical' or 'forecast'",
        )

    run = run_analog_analysis(
        db=db,
        location=location,
        target_date=request.target_date,
        hist_start=request.historical_start_date,
        hist_end=request.historical_end_date,
        top_n=request.top_n,
        mode=request.mode,
        forecast_source=request.forecast_source,
        historical_source=request.historical_source,
    )

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return AnalysisRunDetailResponse.model_validate(
        {**_run_dict(run), "analogs": [AnalogResultResponse.model_validate(a) for a in analogs]}
    )


@router.get("/{run_id}", response_model=AnalysisRunDetailResponse)
def get_analysis_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return AnalysisRunDetailResponse.model_validate(
        {**_run_dict(run), "analogs": [AnalogResultResponse.model_validate(a) for a in analogs]}
    )


@router.get("/{run_id}/analogs", response_model=list[AnalogResultResponse])
def get_analysis_analogs(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    return [AnalogResultResponse.model_validate(a) for a in analogs]


@router.get("/{run_id}/export/weather-csv")
def export_weather_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    start_dt = _dt.datetime.combine(run.target_date, time.min)
    end_dt = _dt.datetime.combine(run.target_date, time.max)
    export_source = run.forecast_source or run.historical_source

    stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
    )
    if export_source:
        stmt = stmt.where(WeatherRecord.source == export_source)
    records = db.execute(stmt.order_by(WeatherRecord.valid_time_local)).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "valid_time_utc", "valid_time_local", "wind_speed_ms",
        "wind_direction_deg", "temperature_c", "pressure_hpa", "cloud_cover_pct",
        "source",
    ])
    for r in records:
        writer.writerow([
            r.valid_time_utc.isoformat() if r.valid_time_utc else "",
            r.valid_time_local.isoformat() if r.valid_time_local else "",
            r.true_wind_speed, r.true_wind_direction,
            r.temperature, r.pressure, r.cloud_cover,
            r.source,
        ])

    filename = f"weather_{run.target_date.isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/export/analogs-csv")
def export_analogs_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["rank", "analog_date", "similarity_score", "distance", "summary"])
    for a in analogs:
        writer.writerow([
            a.rank, a.analog_date.isoformat() if a.analog_date else "",
            a.similarity_score, a.distance, a.summary,
        ])

    filename = f"analogs_{run.target_date.isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/export/json")
def export_analysis_json(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    start_dt = _dt.datetime.combine(run.target_date, time.min)
    end_dt = _dt.datetime.combine(run.target_date, time.max)
    export_source = run.forecast_source or run.historical_source

    stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
    )
    if export_source:
        stmt = stmt.where(WeatherRecord.source == export_source)
    records = db.execute(stmt.order_by(WeatherRecord.valid_time_local)).scalars().all()

    run_response = AnalysisRunResponse.model_validate(run)
    analog_responses = [AnalogResultResponse.model_validate(a) for a in analogs]

    payload = {
        "analysis_run": run_response.model_dump(mode="json"),
        "analogs": [a.model_dump(mode="json") for a in analog_responses],
        "forecast_composite": run.forecast_composite,
        "weather_records": [
            {
                "valid_time_utc": r.valid_time_utc.isoformat() if r.valid_time_utc else None,
                "valid_time_local": r.valid_time_local.isoformat() if r.valid_time_local else None,
                "wind_speed_ms": r.true_wind_speed,
                "wind_direction_deg": r.true_wind_direction,
                "temperature_c": r.temperature,
                "pressure_hpa": r.pressure,
                "cloud_cover_pct": r.cloud_cover,
                "source": r.source,
                "model_run_time": r.model_run_time.isoformat() if r.model_run_time else None,
                "forecast_hour": r.forecast_hour,
                "model_name": r.model_name,
            }
            for r in records
        ],
    }

    filename = f"analysis_{run.target_date.isoformat()}.json"
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/sea-breeze-panel", response_model=SeaBreezePanelResponse)
def get_sea_breeze_panel(
    run_id: int,
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )

    target_source = run.forecast_source or run.historical_source
    analog_source = run.historical_source

    thresholds = SeaBreezeThresholds()

    def _classify_day(
        loc_id: int, day: _dt.date, source: str | None,
    ) -> DayClassificationDetail | None:
        start_dt = _dt.datetime.combine(day, time.min)
        end_dt = _dt.datetime.combine(day, time.max)
        stmt = select(WeatherRecord).where(
            WeatherRecord.location_id == loc_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
        if source:
            stmt = stmt.where(WeatherRecord.source == source)
        records = (
            db.execute(stmt.order_by(WeatherRecord.valid_time_local))
            .scalars()
            .all()
        )
        if not records:
            return None
        features = compute_daily_features(records, loc_id, day)
        if features.wind_speed_increase is None and features.onshore_fraction is None:
            return None
        classification = classify_sea_breeze(features, thresholds)
        return DayClassificationDetail(
            date=day,
            features=features,
            classification=classification,
        )

    target_detail = _classify_day(run.location_id, run.target_date, target_source)

    analog_details: list[DayClassificationDetail] = []
    for analog in analogs:
        detail = _classify_day(run.location_id, analog.analog_date, analog_source)
        if detail is not None:
            analog_details.append(detail)

    high = sum(1 for a in analog_details if a.classification.classification == "high")
    medium = sum(1 for a in analog_details if a.classification.classification == "medium")
    low = sum(1 for a in analog_details if a.classification.classification == "low")

    return SeaBreezePanelResponse(
        run_id=run.id,
        target=target_detail,
        analogs=analog_details,
        thresholds=thresholds,
        analog_high_count=high,
        analog_medium_count=medium,
        analog_low_count=low,
        analog_total=len(analog_details),
    )


@router.get("/{run_id}/analog-hourly", response_model=AnalogHourlyResponse)
def get_analog_hourly(
    run_id: int,
    top_n: int = Query(default=3, ge=1, le=10),
    db: Session = Depends(get_db),
):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
            .limit(top_n)
        )
        .scalars()
        .all()
    )

    target_source = run.forecast_source or run.historical_source
    analog_source = run.historical_source

    # Collect all dates we need
    all_dates = [run.target_date] + [a.analog_date for a in analogs]

    # Build per-date filter conditions
    date_conditions = []
    for day in all_dates:
        start_dt = _dt.datetime.combine(day, time.min)
        end_dt = _dt.datetime.combine(day, time.max)
        source = target_source if day == run.target_date else analog_source
        cond = and_(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= start_dt,
            WeatherRecord.valid_time_local <= end_dt,
        )
        if source:
            cond = and_(cond, WeatherRecord.source == source)
        date_conditions.append(cond)

    if not date_conditions:
        return AnalogHourlyResponse(
            run_id=run.id,
            target=DayHourlyRecords(date=run.target_date),
            analogs=[],
        )

    records = (
        db.execute(
            select(WeatherRecord)
            .where(or_(*date_conditions))
            .order_by(WeatherRecord.valid_time_local)
        )
        .scalars()
        .all()
    )

    # Group records by date
    by_date: dict[_dt.date, list[WeatherRecord]] = defaultdict(list)
    for rec in records:
        day = rec.valid_time_local.date()
        by_date[day].append(rec)

    def _to_responses(recs: list[WeatherRecord]) -> list[WeatherRecordResponse]:
        return [WeatherRecordResponse.model_validate(r) for r in recs]

    target = DayHourlyRecords(
        date=run.target_date,
        rank=None,
        similarity_score=None,
        records=_to_responses(by_date.get(run.target_date, [])),
    )

    analog_items: list[DayHourlyRecords] = []
    for analog in analogs:
        analog_items.append(
            DayHourlyRecords(
                date=analog.analog_date,
                rank=analog.rank,
                similarity_score=analog.similarity_score,
                records=_to_responses(by_date.get(analog.analog_date, [])),
            )
        )

    return AnalogHourlyResponse(
        run_id=run.id,
        target=target,
        analogs=analog_items,
    )


@router.get("/{run_id}/distance-distribution", response_model=DistanceDistributionResponse)
def get_distance_distribution(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Return distances from the target day to ALL library days."""
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    # Load stored top-N analog results for marking
    stored_analogs = (
        db.execute(
            select(AnalogResult)
            .where(AnalogResult.analysis_run_id == run.id)
            .order_by(AnalogResult.rank)
        )
        .scalars()
        .all()
    )
    top_n_map: dict[_dt.date, int] = {a.analog_date: a.rank for a in stored_analogs}
    top_n_dates = [a.analog_date for a in stored_analogs]

    # Load target-day weather and compute features
    target_source = run.forecast_source or run.historical_source
    target_start_dt = _dt.datetime.combine(run.target_date, time.min)
    target_end_dt = _dt.datetime.combine(run.target_date, time(23, 59, 59))
    target_stmt = (
        select(WeatherRecord)
        .where(
            WeatherRecord.location_id == run.location_id,
            WeatherRecord.valid_time_local >= target_start_dt,
            WeatherRecord.valid_time_local <= target_end_dt,
        )
    )
    if target_source:
        target_stmt = target_stmt.where(WeatherRecord.source == target_source)
    target_records = (
        db.execute(target_stmt.order_by(WeatherRecord.valid_time_local))
        .scalars()
        .all()
    )
    if not target_records:
        raise HTTPException(status_code=404, detail="No target-day weather data found")

    window = AnalysisWindow()

    target_features = compute_daily_features(
        target_records, run.location_id, run.target_date, window,
    )

    # Load full library
    hist_source = run.historical_source or "era5"
    config_hash = compute_feature_config_hash(window)
    historical_features = get_precomputed_features(
        db, run.location_id, hist_source, config_hash,
        start_date=run.historical_start_date,
        end_date=run.historical_end_date,
    )

    if not historical_features:
        return DistanceDistributionResponse(
            run_id=run.id,
            target_date=run.target_date,
            entries=[],
            top_n_dates=top_n_dates,
        )

    all_distances = compute_all_distances(target_features, historical_features, window=window)

    entries: list[DistanceEntry] = []
    for feat, dist in all_distances:
        rank = top_n_map.get(feat.date)
        entries.append(
            DistanceEntry(
                date=feat.date,
                distance=dist,
                similarity_score=1.0 / (1.0 + dist),
                is_top_n=rank is not None,
                rank=rank,
            )
        )

    return DistanceDistributionResponse(
        run_id=run.id,
        target_date=run.target_date,
        entries=entries,
        top_n_dates=top_n_dates,
    )


@router.get("/{run_id}/forecast", response_model=ForecastCompositeResponse)
def get_forecast_composite(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Return the forecast composite for a run (if available)."""
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    composite = run.forecast_composite
    if composite is None:
        raise HTTPException(status_code=404, detail="No forecast composite available for this run")

    gate_result = composite.get("gate_result", "low")
    raw_hours = composite.get("hours")
    hours: list[ForecastCompositeHour] | None = None
    if raw_hours:
        hours = [ForecastCompositeHour(**h) for h in raw_hours]

    return ForecastCompositeResponse(
        run_id=run.id,
        gate_result=gate_result,
        hours=hours,
        summary=run.summary,
    )


@router.get("/{run_id}/export/forecast-csv")
def export_forecast_csv(
    run_id: int,
    db: Session = Depends(get_db),
):
    """Export forecast composite hours as CSV."""
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    composite = run.forecast_composite
    if composite is None or not composite.get("hours"):
        raise HTTPException(status_code=404, detail="No forecast composite hours available")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "hour_local", "median_tws", "p25_tws", "p75_tws", "p10_tws", "p90_tws",
        "circular_mean_twd", "twd_circular_std", "twd_arc_radius_75", "analog_count",
    ])
    for h in composite["hours"]:
        writer.writerow([
            h.get("hour_local", ""),
            h.get("median_tws", ""),
            h.get("p25_tws", ""),
            h.get("p75_tws", ""),
            h.get("p10_tws", ""),
            h.get("p90_tws", ""),
            h.get("circular_mean_twd", ""),
            h.get("twd_circular_std", ""),
            h.get("twd_arc_radius_75", ""),
            h.get("analog_count", ""),
        ])

    filename = f"forecast_{run.target_date.isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _run_dict(run: AnalysisRun) -> dict:
    """Convert an AnalysisRun ORM object to a dict for Pydantic validation."""
    return {
        "id": run.id,
        "location_id": run.location_id,
        "target_date": run.target_date,
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "summary": run.summary,
        "historical_start_date": run.historical_start_date,
        "historical_end_date": run.historical_end_date,
        "top_n": run.top_n,
        "mode": run.mode,
        "forecast_source": run.forecast_source,
        "historical_source": run.historical_source,
        "forecast_composite": run.forecast_composite,
        "created_at": run.created_at,
    }
