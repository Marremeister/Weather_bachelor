"""GFS Hindcast Provider — NCAR RDA THREDDS NCSS point subsetting.

Fetches historical GFS 0.25-degree forecast data by issuing NetCDF
Subsetting Service (NCSS) point-subset requests against the NCAR RDA
THREDDS server (dataset ``d084001``).  Each target date ``D`` is
reconstructed from the **D 00Z** GFS cycle; forecast hours are chosen
so that each valid time lands inside the local analysis window defined
by ``gfs_analysis_local_start`` .. ``gfs_analysis_local_end``.

Unlike the live ``GfsForecastProvider``, which downloads full GRIB2
files and runs them through cfgrib, this provider requests only a
single point per variable per forecast hour (~8 KB payload), making
multi-year hindcast builds tractable over a public network.

Variables are split across three NCSS requests because they live on
mixed vertical dimensions in the THREDDS catalog:

* ``wind``: ``u-component_of_wind_height_above_ground``,
  ``v-component_of_wind_height_above_ground``
* ``temp``: ``Temperature_height_above_ground``
* ``pres_cloud``: ``Pressure_reduced_to_MSL_msl``,
  ``Total_cloud_cover_entire_atmosphere``.  Cloud cover availability is
  best-effort: if THREDDS returns 400 for it we retry the group without
  cloud cover and accept pressure-only records.
"""

from __future__ import annotations

import io
import logging
import math
import time as time_mod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from threading import Lock
from typing import Iterable
from zoneinfo import ZoneInfo

import requests

try:
    import xarray as xr
except ImportError:  # pragma: no cover - xarray is a runtime dep
    xr = None  # type: ignore[assignment]

from app.config import settings
from app.services.gfs_common import forecast_hours_for_window
from app.services.weather_provider import FetchResult, HourlyRecord, WeatherProvider

logger = logging.getLogger(__name__)


# NCAR RDA THREDDS NCSS endpoint for GFS 0.25-degree historical archive.
NCSS_BASE = (
    "https://thredds.rda.ucar.edu/thredds/ncss/grid/files/g/d084001"
)


# Mixed vertical dims require three separate NCSS calls per fhour.
_VAR_GROUPS: dict[str, tuple[str, ...]] = {
    "wind": (
        "u-component_of_wind_height_above_ground",
        "v-component_of_wind_height_above_ground",
    ),
    "temp": ("Temperature_height_above_ground",),
    "pres_cloud": (
        "Pressure_reduced_to_MSL_msl",
        "Total_cloud_cover_entire_atmosphere",
    ),
}


class GfsHindcastError(Exception):
    """Raised when an NCSS request cannot be satisfied after retries."""


# ---------------------------------------------------------------------------
# NCSS URL / request helpers
# ---------------------------------------------------------------------------


def _ncss_url(model_run_time: datetime, cycle_hour: int, fhour: int) -> str:
    yyyymmdd = model_run_time.strftime("%Y%m%d")
    year = yyyymmdd[:4]
    fname = f"gfs.0p25.{yyyymmdd}{cycle_hour:02d}.f{fhour:03d}.grib2"
    return f"{NCSS_BASE}/{year}/{yyyymmdd}/{fname}"


def _ncss_params(
    variables: Iterable[str],
    latitude: float,
    longitude: float,
    valid_time_utc: datetime,
) -> list[tuple[str, str]]:
    """Build NCSS query string parameters for a point subset.

    THREDDS expects repeated ``var`` keys for multi-variable requests;
    using an ordered list-of-tuples keeps that representation without
    relying on dict ordering guarantees.
    """
    # NCSS wants an ISO-8601 timestamp; Z suffix required for UTC.
    time_str = valid_time_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    params: list[tuple[str, str]] = []
    for v in variables:
        params.append(("var", v))
    params.extend(
        [
            ("latitude", f"{latitude}"),
            ("longitude", f"{longitude}"),
            ("time", time_str),
            ("accept", "netcdf4"),
        ]
    )
    return params


def _request_group(
    session: requests.Session,
    url: str,
    variables: tuple[str, ...],
    latitude: float,
    longitude: float,
    valid_time_utc: datetime,
    timeout: int,
    max_retries: int,
) -> "xr.Dataset":
    """Issue one NCSS request with exponential-backoff retries.

    Returns an in-memory ``xarray.Dataset`` parsed from the NetCDF
    response body.  Raises ``GfsHindcastError`` on 4xx (other than the
    cloud-cover 400 handled upstream) or after ``max_retries`` failures.
    """
    if xr is None:
        raise GfsHindcastError(
            "xarray is required for GFS hindcast point extraction"
        )

    params = _ncss_params(variables, latitude, longitude, valid_time_utc)

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code == 400:
                # Don't retry 400s — caller may decide to drop variables.
                raise GfsHindcastError(
                    f"NCSS 400 for {variables} at {valid_time_utc}: "
                    f"{resp.text[:200]}"
                )
            if resp.status_code in (503, 504) or resp.status_code >= 500:
                raise requests.HTTPError(
                    f"NCSS {resp.status_code}", response=resp
                )
            resp.raise_for_status()
            # load_dataset materialises the file so the HTTP response
            # buffer can be released before the next request runs.
            ds = xr.load_dataset(io.BytesIO(resp.content), engine="h5netcdf")
            return ds
        except GfsHindcastError:
            raise
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                backoff = 2**attempt  # 1, 2, 4, 8, 16 s
                logger.debug(
                    "NCSS retry %d/%d for %s at %s after %s (sleep %ds)",
                    attempt + 1,
                    max_retries,
                    variables,
                    valid_time_utc,
                    exc,
                    backoff,
                )
                time_mod.sleep(backoff)
            else:
                break

    raise GfsHindcastError(
        f"NCSS request exhausted retries for {variables} at {valid_time_utc}: "
        f"{last_exc}"
    )


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


def _scalar(ds: "xr.Dataset", var: str) -> float | None:
    """Pull a scalar float from a point-subset dataset, or None if absent."""
    if var not in ds.data_vars:
        return None
    try:
        arr = ds[var].values
    except Exception:  # pragma: no cover - defensive
        return None
    # NCSS point subsets come back as 0-d or 1-element arrays; squeeze both.
    try:
        flat = arr.reshape(-1)
    except Exception:
        return None
    if flat.size == 0:
        return None
    val = flat[0]
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return None
    # NaNs from masked/missing NetCDF values should propagate as None.
    if fval != fval:
        return None
    return fval


def _wind_speed(u: float, v: float) -> float:
    return (u * u + v * v) ** 0.5


def _wind_dir_deg(u: float, v: float) -> float:
    """Meteorological "from" direction of the wind in degrees (0–360)."""
    deg = (math.degrees(math.atan2(-u, -v))) % 360.0
    return deg


def _merge_group_dsets(
    groups: dict[str, "xr.Dataset"],
) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    """Extract ``(ws, wd, temp_c, pressure_hpa, cloud_pct)`` from the
    three per-group datasets.  Missing groups yield ``None``s."""
    ws: float | None = None
    wd: float | None = None
    temp: float | None = None
    pres: float | None = None
    cloud: float | None = None

    wind_ds = groups.get("wind")
    if wind_ds is not None:
        u = _scalar(wind_ds, "u-component_of_wind_height_above_ground")
        v = _scalar(wind_ds, "v-component_of_wind_height_above_ground")
        if u is not None and v is not None:
            ws = _wind_speed(u, v)
            wd = _wind_dir_deg(u, v)

    temp_ds = groups.get("temp")
    if temp_ds is not None:
        t = _scalar(temp_ds, "Temperature_height_above_ground")
        if t is not None:
            # Kelvin → Celsius if needed.
            temp = t - 273.15 if t > 200 else t

    pres_ds = groups.get("pres_cloud")
    if pres_ds is not None:
        p = _scalar(pres_ds, "Pressure_reduced_to_MSL_msl")
        if p is not None:
            pres = p / 100.0 if p > 50000 else p
        c = _scalar(pres_ds, "Total_cloud_cover_entire_atmosphere")
        if c is not None:
            cloud = c * 100.0 if c <= 1.0 else c

    return ws, wd, temp, pres, cloud


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class GfsHindcastProvider(WeatherProvider):
    """Fetches historical GFS forecasts via NCAR RDA THREDDS NCSS.

    One ``(target_date, fhour, var_group)`` triplet = one HTTP request.
    Work is dispatched to a single ``ThreadPoolExecutor`` per ``fetch()``
    call; the default pool size of 8 is enough to keep the THREDDS tier
    saturated without tripping its per-client throttle.
    """

    @property
    def source_name(self) -> str:
        return "gfs_hindcast"

    # ---- planning ----------------------------------------------------------

    def _plan_tasks(
        self,
        start_date: date,
        end_date: date,
        timezone: str,
        local_start: int,
        local_end: int,
    ) -> list[tuple[date, datetime, int]]:
        """Build the flat list of ``(target_date, model_run_time, fhour)``
        units that will be fetched.  Variable groups fan out per-unit."""
        utc = ZoneInfo("UTC")
        tasks: list[tuple[date, datetime, int]] = []

        current = start_date
        while current <= end_date:
            # Option A: always use the target day's own 00Z cycle.
            model_run_time = datetime(
                current.year, current.month, current.day, 0, tzinfo=utc
            )
            fhours = forecast_hours_for_window(
                model_run_time, current, timezone, local_start, local_end
            )
            for fh in fhours:
                tasks.append((current, model_run_time, fh))
            current += timedelta(days=1)

        return tasks

    # ---- per-unit fetch ----------------------------------------------------

    def _fetch_unit(
        self,
        session: requests.Session,
        latitude: float,
        longitude: float,
        target_date: date,
        model_run_time: datetime,
        fhour: int,
        timeout: int,
        max_retries: int,
    ) -> dict[str, "xr.Dataset"]:
        """Fetch all three variable groups for a single ``(date, fhour)``
        unit.  Cloud-cover 400s trigger a pres-only retry for the
        ``pres_cloud`` group; all other 400s propagate."""
        url = _ncss_url(model_run_time, model_run_time.hour, fhour)
        valid_time_utc = model_run_time + timedelta(hours=fhour)

        groups: dict[str, "xr.Dataset"] = {}

        for group_name, variables in _VAR_GROUPS.items():
            try:
                ds = _request_group(
                    session,
                    url,
                    variables,
                    latitude,
                    longitude,
                    valid_time_utc,
                    timeout,
                    max_retries,
                )
                groups[group_name] = ds
            except GfsHindcastError as exc:
                if (
                    group_name == "pres_cloud"
                    and "Total_cloud_cover_entire_atmosphere" in variables
                    and "400" in str(exc)
                ):
                    # Cloud cover missing in this cycle → retry pres only.
                    fallback_vars = tuple(
                        v
                        for v in variables
                        if v != "Total_cloud_cover_entire_atmosphere"
                    )
                    logger.debug(
                        "Cloud cover unavailable at %s, retrying pres only",
                        valid_time_utc,
                    )
                    ds = _request_group(
                        session,
                        url,
                        fallback_vars,
                        latitude,
                        longitude,
                        valid_time_utc,
                        timeout,
                        max_retries,
                    )
                    groups[group_name] = ds
                else:
                    raise

        return groups

    # ---- entry point -------------------------------------------------------

    def fetch(
        self,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
        timezone: str,
    ) -> FetchResult:
        if xr is None:
            raise GfsHindcastError(
                "xarray is required for GFS hindcast point extraction"
            )

        tz = ZoneInfo(timezone)
        local_start = settings.gfs_analysis_local_start
        local_end = settings.gfs_analysis_local_end
        max_workers = settings.gfs_hindcast_ncss_max_workers
        max_retries = settings.gfs_hindcast_ncss_max_retries
        timeout = settings.gfs_hindcast_ncss_timeout

        tasks = self._plan_tasks(
            start_date, end_date, timezone, local_start, local_end
        )
        total_units = len(tasks)

        logger.info(
            "GFS hindcast fetch: %d days × %d fhours ≈ %d NCSS units "
            "(×3 groups/unit)",
            (end_date - start_date).days + 1,
            total_units // max(1, (end_date - start_date).days + 1),
            total_units,
        )

        # Collect results keyed by (target_date, fhour) → {group: ds}.
        results: dict[tuple[date, int], dict[str, "xr.Dataset"]] = defaultdict(
            dict
        )
        failures: list[str] = []
        day_progress_lock = Lock()
        day_done: dict[date, int] = defaultdict(int)
        day_total: dict[date, int] = defaultdict(int)
        for td, _mrt, _fh in tasks:
            day_total[td] += 1

        session = requests.Session()

        def _run(task: tuple[date, datetime, int]):
            target_date, model_run_time, fhour = task
            groups = self._fetch_unit(
                session,
                latitude,
                longitude,
                target_date,
                model_run_time,
                fhour,
                timeout,
                max_retries,
            )
            return (target_date, model_run_time, fhour, groups)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_run, t) for t in tasks]
            for fut in as_completed(futures):
                try:
                    target_date, _mrt, fhour, groups = fut.result()
                except GfsHindcastError as exc:
                    failures.append(str(exc))
                    logger.debug("NCSS unit failed: %s", exc)
                    continue
                except Exception as exc:  # pragma: no cover
                    failures.append(str(exc))
                    logger.debug("NCSS unit errored: %s", exc)
                    continue

                results[(target_date, fhour)] = groups
                with day_progress_lock:
                    day_done[target_date] += 1
                    if day_done[target_date] == day_total[target_date]:
                        logger.info(
                            "GFS hindcast day %s complete (%d fhours)",
                            target_date,
                            day_total[target_date],
                        )

        # Merge groups → HourlyRecords.
        records: list[HourlyRecord] = []
        for (target_date, fhour), groups in sorted(results.items()):
            model_run_time = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                0,
                tzinfo=ZoneInfo("UTC"),
            )
            valid_time_utc = model_run_time + timedelta(hours=fhour)
            valid_time_local = valid_time_utc.astimezone(tz).replace(tzinfo=None)

            ws, wd, temp, pres, cloud = _merge_group_dsets(groups)

            records.append(
                HourlyRecord(
                    valid_time_utc=valid_time_utc,
                    valid_time_local=valid_time_local,
                    true_wind_speed=ws,
                    true_wind_direction=wd,
                    temperature=temp,
                    pressure=pres,
                    cloud_cover=cloud,
                    model_run_time=model_run_time,
                    forecast_hour=fhour,
                    model_name="gfs_0p25_hindcast",
                )
            )

        logger.info(
            "GFS hindcast fetch done: %d records, %d failures",
            len(records),
            len(failures),
        )

        # If everything failed, surface as an error so the caller can retry.
        if total_units > 0 and not records:
            raise GfsHindcastError(
                f"All GFS hindcast NCSS requests failed: "
                f"{'; '.join(failures[:3])}"
            )

        return FetchResult(
            records=records,
            raw_payload={
                "source": self.source_name,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "units_requested": total_units,
                "records_returned": len(records),
                "failures": len(failures),
            },
        )
