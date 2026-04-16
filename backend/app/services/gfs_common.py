"""Shared helpers for GFS providers (live forecast and hindcast).

Extracted so `gfs_forecast_provider` and `gfs_hindcast_provider` can share
the forecast-hour window computation without either importing the other.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


def forecast_hours_for_window(
    model_run_time: datetime,
    target_date: date,
    timezone: str,
    local_start: int,
    local_end: int,
) -> list[int]:
    """Compute the GFS forecast hours (offsets from *model_run_time*)
    whose valid times land in ``[local_start, local_end]`` on *target_date*.

    Returns a sorted list of non-negative integer forecast hours.
    """
    tz = ZoneInfo(timezone)
    utc = ZoneInfo("UTC")

    hours: list[int] = []
    for local_hour in range(local_start, local_end + 1):
        local_dt = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            local_hour,
            0,
            0,
            tzinfo=tz,
        )
        utc_dt = local_dt.astimezone(utc)
        fhour = int((utc_dt - model_run_time).total_seconds() / 3600)
        if fhour >= 0:
            hours.append(fhour)

    return sorted(hours)
