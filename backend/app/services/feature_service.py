"""Feature engineering: convert hourly WeatherRecord rows into daily feature vectors."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date

import numpy as np

from app.schemas.features import AnalysisWindow, DailyFeatures

# The 9 feature fields stored in the daily_features table.
_DEFAULT_FEATURE_NAMES = (
    "morning_mean_wind_speed",
    "morning_mean_wind_direction",
    "reference_wind_speed",
    "reference_wind_direction",
    "afternoon_max_wind_speed",
    "afternoon_mean_wind_direction",
    "wind_speed_increase",
    "wind_direction_shift",
    "onshore_fraction",
)


def compute_feature_config_hash(
    window: AnalysisWindow,
    feature_names: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Deterministic 16-hex-char hash of the feature extraction configuration.

    Changes whenever the analysis window parameters or the set of extracted
    features change, which signals that precomputed libraries need rebuilding.
    """
    names = sorted(feature_names) if feature_names else sorted(_DEFAULT_FEATURE_NAMES)
    payload = json.dumps(
        {"window": window.model_dump(), "features": names},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def circular_mean(degrees: list[float]) -> float:
    """Circular mean of angles in degrees, result in [0, 360). Returns NaN if empty."""
    clean = [d for d in degrees if d is not None and not math.isnan(d)]
    if not clean:
        return float("nan")
    rads = np.deg2rad(clean)
    mean_sin = np.mean(np.sin(rads))
    mean_cos = np.mean(np.cos(rads))
    result = np.rad2deg(np.arctan2(mean_sin, mean_cos)) % 360
    return float(result)


def circular_std(degrees: list[float]) -> float:
    """Circular standard deviation (Mardia-Jupp formula), result in degrees.

    Formula: sqrt(-2 * ln(R)) converted to degrees, where R is the mean
    resultant length.  Capped at 180 degrees.  Returns NaN if empty.
    """
    clean = [d for d in degrees if d is not None and not math.isnan(d)]
    if not clean:
        return float("nan")
    rads = np.deg2rad(clean)
    mean_sin = float(np.mean(np.sin(rads)))
    mean_cos = float(np.mean(np.cos(rads)))
    R = math.sqrt(mean_sin**2 + mean_cos**2)
    if R >= 1.0:
        return 0.0
    if R <= 0.0:
        return 180.0
    return min(float(np.rad2deg(math.sqrt(-2.0 * math.log(R)))), 180.0)


def circular_arc_radius(degrees: list[float], percentile: float = 75.0) -> float:
    """Return the *percentile*-rank circular distance from the circular mean.

    Useful for describing the angular spread: e.g. 75th-percentile arc
    radius tells you that 75 % of observations are within this many degrees
    of the mean direction.  Returns NaN if empty.
    """
    clean = [d for d in degrees if d is not None and not math.isnan(d)]
    if not clean:
        return float("nan")
    mean_deg = circular_mean(clean)
    if math.isnan(mean_deg):
        return float("nan")
    # Compute absolute circular distances from the mean
    dists = [abs(((d - mean_deg) + 180) % 360 - 180) for d in clean]
    dists.sort()
    return float(np.percentile(dists, percentile))


def direction_difference(a: float, b: float) -> float:
    """Signed angular difference in [-180, +180]."""
    if a is None or b is None or math.isnan(a) or math.isnan(b):
        return float("nan")
    return ((a - b) + 180) % 360 - 180


def is_in_sector(direction: float, sector_min: float, sector_max: float) -> bool:
    """Check if direction falls within [sector_min, sector_max], handling wrap-around."""
    if direction is None or math.isnan(direction):
        return False
    direction = direction % 360
    sector_min = sector_min % 360
    sector_max = sector_max % 360
    if sector_min <= sector_max:
        return sector_min <= direction <= sector_max
    # Wrap-around case (e.g. 350 -> 10)
    return direction >= sector_min or direction <= sector_max


def compute_daily_features(
    records,
    location_id: int,
    target_date: date,
    window: AnalysisWindow | None = None,
) -> DailyFeatures:
    """Compute daily feature vector from hourly weather records.

    ``records`` must be an iterable of objects with attributes:
    ``.valid_time_local``, ``.true_wind_speed``, ``.true_wind_direction``.
    """
    if window is None:
        window = AnalysisWindow()

    morning_speeds: list[float] = []
    morning_dirs: list[float] = []
    afternoon_speeds: list[float] = []
    afternoon_dirs: list[float] = []
    reference_speed: float | None = None
    reference_dir: float | None = None

    for rec in records:
        hour = rec.valid_time_local.hour
        speed = rec.true_wind_speed
        direction = rec.true_wind_direction

        # Reference hour
        if hour == window.reference_hour:
            if speed is not None:
                reference_speed = speed
            if direction is not None:
                reference_dir = direction

        # Morning window (inclusive)
        if window.morning_start <= hour <= window.morning_end:
            if speed is not None:
                morning_speeds.append(speed)
            if direction is not None:
                morning_dirs.append(direction)

        # Afternoon window (inclusive)
        if window.afternoon_start <= hour <= window.afternoon_end:
            if speed is not None:
                afternoon_speeds.append(speed)
            if direction is not None:
                afternoon_dirs.append(direction)

    hours_available = len(morning_speeds) + len(afternoon_speeds)
    morning_hours_used = len(morning_speeds)
    afternoon_hours_used = len(afternoon_speeds)

    features = DailyFeatures(
        location_id=location_id,
        date=target_date,
        hours_available=hours_available,
        morning_hours_used=morning_hours_used,
        afternoon_hours_used=afternoon_hours_used,
        reference_wind_speed=reference_speed,
        reference_wind_direction=reference_dir,
    )

    morning_dir_count = len(morning_dirs)
    afternoon_dir_count = len(afternoon_dirs)

    # Morning aggregates — speed and direction gated independently
    if morning_hours_used >= window.min_morning_hours:
        features.morning_mean_wind_speed = float(np.mean(morning_speeds))
    if morning_dir_count >= window.min_morning_hours:
        features.morning_mean_wind_direction = circular_mean(morning_dirs)

    # Afternoon aggregates — speed and direction gated independently
    if afternoon_hours_used >= window.min_afternoon_hours:
        features.afternoon_max_wind_speed = float(np.max(afternoon_speeds))
    if afternoon_dir_count >= window.min_afternoon_hours:
        features.afternoon_mean_wind_direction = circular_mean(afternoon_dirs)

    # Derived features (require both windows)
    if features.morning_mean_wind_speed is not None and features.afternoon_max_wind_speed is not None:
        features.wind_speed_increase = features.afternoon_max_wind_speed - features.morning_mean_wind_speed

    if features.morning_mean_wind_direction is not None and features.afternoon_mean_wind_direction is not None:
        morning_dir = features.morning_mean_wind_direction
        afternoon_dir = features.afternoon_mean_wind_direction
        if not math.isnan(morning_dir) and not math.isnan(afternoon_dir):
            features.wind_direction_shift = direction_difference(afternoon_dir, morning_dir)

    # Onshore fraction — only when enough direction samples exist
    if afternoon_dir_count >= window.min_afternoon_hours:
        onshore_count = sum(
            1 for d in afternoon_dirs
            if is_in_sector(d, window.onshore_sector_min, window.onshore_sector_max)
        )
        features.onshore_fraction = onshore_count / afternoon_dir_count

    return features
