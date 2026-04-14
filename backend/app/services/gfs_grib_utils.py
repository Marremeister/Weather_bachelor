"""GRIB parsing utilities for GFS forecast data.

Pure/stateless functions for opening GRIB2 files with cfgrib/xarray,
scoring variables against target specifications, extracting point data,
and converting wind vectors.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Target variable specifications
# ---------------------------------------------------------------------------

TARGET_SPECS: dict[str, dict[str, Any]] = {
    "u10": {
        "keywords": ["u-component", "u component", "10 metre"],
        "forbidden": ["gust", "planetary"],
        "expected_units": ["m s**-1", "m/s", "m s-1"],
        "plausibility": (-60.0, 60.0),
    },
    "v10": {
        "keywords": ["v-component", "v component", "10 metre"],
        "forbidden": ["gust", "planetary"],
        "expected_units": ["m s**-1", "m/s", "m s-1"],
        "plausibility": (-60.0, 60.0),
    },
    "t2m": {
        "keywords": ["temperature", "2 metre"],
        "forbidden": ["dew", "potential", "virtual"],
        "expected_units": ["K", "C"],
        "plausibility": (180.0, 340.0),  # Kelvin range
    },
    "d2m": {
        "keywords": ["dew", "2 metre"],
        "forbidden": ["temperature"],
        "expected_units": ["K", "C"],
        "plausibility": (180.0, 340.0),
    },
    "mslp": {
        "keywords": ["pressure", "mean sea level", "msl"],
        "forbidden": ["tendency", "change"],
        "expected_units": ["Pa", "hPa"],
        "plausibility": (80000.0, 110000.0),  # Pa range
    },
    "blh": {
        "keywords": ["boundary layer", "height"],
        "forbidden": [],
        "expected_units": ["m", "gpm"],
        "plausibility": (0.0, 10000.0),
    },
    "tcc": {
        "keywords": ["cloud", "total", "cover"],
        "forbidden": ["low", "medium", "high", "convective"],
        "expected_units": ["%", "(0 - 1)", "Fraction", "fraction"],
        "plausibility": (0.0, 110.0),
    },
}

# cfgrib filter sets to try when opening a target variable
_CFGRIB_FILTERS: list[dict[str, Any]] = [
    {"typeOfLevel": "heightAboveGround", "level": 10},   # u10, v10
    {"typeOfLevel": "heightAboveGround", "level": 2},    # t2m, d2m
    {"typeOfLevel": "meanSea"},                           # mslp
    {"typeOfLevel": "surface"},                           # blh, tcc
    {"typeOfLevel": "heightAboveGround"},                 # generic
    {"typeOfLevel": "isobaricInhPa"},                     # fallback
    {},                                                    # no filter
]


# ---------------------------------------------------------------------------
# GRIB file opening
# ---------------------------------------------------------------------------


def try_open_cfgrib(path: str | Path, filter_by_keys: dict[str, Any] | None = None):
    """Attempt to open a GRIB file with cfgrib, returning xr.Dataset or None."""
    import xarray as xr

    backend_kwargs: dict[str, Any] = {"indexpath": ""}
    if filter_by_keys:
        backend_kwargs["filter_by_keys"] = filter_by_keys

    try:
        ds = xr.open_dataset(
            str(path), engine="cfgrib", backend_kwargs=backend_kwargs
        )
        return ds
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Variable scoring
# ---------------------------------------------------------------------------


def _score_da_for_target(da, target: str, filt: dict[str, Any]) -> int:
    """Score how well a DataArray matches a target spec.

    Returns a composite score; higher is better. Negative means reject.
    """
    spec = TARGET_SPECS[target]
    score = 0

    da_name = (da.name or "").lower()
    long_name = str(da.attrs.get("long_name", "")).lower()
    units_str = str(da.attrs.get("units", "")).lower()

    # Exact name match
    canonical = {"u10": "u10", "v10": "v10", "t2m": "t2m", "d2m": "d2m",
                 "mslp": "msl", "blh": "blh", "tcc": "tcc"}
    if da_name == canonical.get(target, target):
        score += 300

    # Keyword matches in long_name
    for kw in spec["keywords"]:
        if kw.lower() in long_name:
            score += 40

    # Forbidden words
    for fw in spec["forbidden"]:
        if fw.lower() in long_name:
            score -= 200

    # Units match
    for eu in spec["expected_units"]:
        if eu.lower() in units_str:
            score += 80
            break

    # Plausibility check on sample values
    try:
        vals = da.values.ravel()
        finite = vals[np.isfinite(vals)]
        if len(finite) > 0:
            lo, hi = spec["plausibility"]
            median = float(np.median(finite))
            if not (lo <= median <= hi):
                score -= 1000
    except Exception:
        pass

    return score


def _open_target_da(path: str | Path, target: str):
    """Open the best-matching DataArray for a target variable from a GRIB file.

    Tries multiple cfgrib filter sets and returns the highest-scoring match,
    or None if nothing matches.
    """
    best_da = None
    best_score = -9999

    for filt in _CFGRIB_FILTERS:
        ds = try_open_cfgrib(path, filt if filt else None)
        if ds is None:
            continue

        for var_name in ds.data_vars:
            da = ds[var_name]
            sc = _score_da_for_target(da, target, filt)
            if sc > best_score:
                best_score = sc
                best_da = da

        ds.close()

    if best_da is not None and best_score > 0:
        return best_da
    return None


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------


def detect_lat_lon_names(ds) -> tuple[str, str]:
    """Detect latitude and longitude dimension/coordinate names in a dataset."""
    lat_candidates = ["latitude", "lat", "y"]
    lon_candidates = ["longitude", "lon", "x"]

    lat_name = None
    lon_name = None

    all_names = set(ds.dims) | set(ds.coords)
    for c in lat_candidates:
        if c in all_names:
            lat_name = c
            break
    for c in lon_candidates:
        if c in all_names:
            lon_name = c
            break

    if lat_name is None or lon_name is None:
        raise ValueError(
            f"Cannot detect lat/lon names. Available: {sorted(all_names)}"
        )

    return lat_name, lon_name


def convert_lon_360_to_180(ds, lon_name: str = "longitude"):
    """Convert longitudes from 0..360 to -180..180 convention."""
    import xarray as xr

    lon_vals = ds[lon_name].values
    if float(lon_vals.max()) > 180.0:
        new_lon = ((lon_vals + 180.0) % 360.0) - 180.0
        ds = ds.assign_coords({lon_name: new_lon})
        ds = ds.sortby(lon_name)
    return ds


def select_point_dataarray(da, lat: float, lon: float):
    """Select nearest grid point from a DataArray, handling lon convention."""
    # Detect coordinate names
    lat_name = None
    lon_name = None
    for name in da.dims:
        if name.lower() in ("latitude", "lat", "y"):
            lat_name = name
        elif name.lower() in ("longitude", "lon", "x"):
            lon_name = name

    if lat_name is None or lon_name is None:
        # Try coords
        for name in da.coords:
            nm = name.lower()
            if nm in ("latitude", "lat") and lat_name is None:
                lat_name = name
            elif nm in ("longitude", "lon") and lon_name is None:
                lon_name = name

    if lat_name is None or lon_name is None:
        raise ValueError("Cannot detect lat/lon in DataArray")

    # Check lon convention
    lon_vals = da[lon_name].values
    if float(lon_vals.max()) > 180.0 and lon < 0:
        # Convert query lon to 0..360
        query_lon = lon + 360.0
    else:
        query_lon = lon

    return da.sel({lat_name: lat, lon_name: query_lon}, method="nearest")


# ---------------------------------------------------------------------------
# Wind conversion
# ---------------------------------------------------------------------------


def wind_speed(u: float, v: float) -> float:
    """Compute wind speed from U and V components."""
    return math.sqrt(u * u + v * v)


def wind_dir_deg(u: float, v: float) -> float:
    """Compute meteorological wind direction (degrees, where wind comes FROM).

    Uses the standard convention: 0/360 = North, 90 = East, etc.
    """
    direction = (270.0 - math.degrees(math.atan2(v, u))) % 360.0
    return direction


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def validate_grib_file(path: str | Path) -> bool:
    """Check if a file begins with the GRIB magic number."""
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
        return magic == b"GRIB"
    except (OSError, IOError):
        return False


def remove_old_idx(grib_path: str | Path) -> None:
    """Remove stale cfgrib index files for a GRIB file."""
    grib_path = Path(grib_path)
    for suffix in (".idx", ".923a8.idx"):
        idx = grib_path.with_suffix(grib_path.suffix + suffix)
        if idx.exists():
            idx.unlink()
