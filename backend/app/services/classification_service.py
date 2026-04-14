"""Rules-based sea breeze classifier."""

from __future__ import annotations

import math

from app.schemas.features import DailyFeatures, SeaBreezeClassification, SeaBreezeThresholds


def classify_sea_breeze(
    features: DailyFeatures,
    thresholds: SeaBreezeThresholds | None = None,
) -> SeaBreezeClassification:
    """Evaluate three indicators and return a classification with score."""
    if thresholds is None:
        thresholds = SeaBreezeThresholds()

    speed_increase = (
        features.wind_speed_increase is not None
        and features.wind_speed_increase >= thresholds.minimum_speed_increase_mps
    )

    direction_shift = False
    if features.wind_direction_shift is not None and not math.isnan(features.wind_direction_shift):
        direction_shift = abs(features.wind_direction_shift) >= thresholds.minimum_direction_shift_degrees

    onshore_fraction = (
        features.onshore_fraction is not None
        and features.onshore_fraction >= thresholds.minimum_onshore_fraction
    )

    indicators = {
        "speed_increase": speed_increase,
        "direction_shift": direction_shift,
        "onshore_fraction": onshore_fraction,
    }

    count_true = sum(indicators.values())
    score = count_true / 3

    if count_true == 3:
        classification = "high"
    elif count_true == 2:
        classification = "medium"
    else:
        classification = "low"

    return SeaBreezeClassification(
        classification=classification,
        score=score,
        indicators=indicators,
    )
