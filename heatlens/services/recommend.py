"""Indicative canopy intervention: estimated_delta_t = beta_canopy * (target - current)."""

from __future__ import annotations

from typing import List, Optional

from heatlens.domain.types import Coefficients, InterventionEstimate, StreetSegment
from heatlens.errors import ValidationFailed


def estimated_delta_t(current_canopy_frac, target_canopy_frac, beta_canopy):
    current = float(current_canopy_frac)
    target = float(target_canopy_frac)
    if target < 0.0 or target > 1.0:
        raise ValidationFailed("target_canopy_frac must be in [0, 1]")
    gain = max(target - current, 0.0)
    return float(beta_canopy) * gain


def estimate_segment(
    segment: StreetSegment,
    coefficients: Coefficients,
    target_canopy_frac: Optional[float] = None,
) -> InterventionEstimate:
    target = (
        coefficients.target_canopy_frac if target_canopy_frac is None else float(target_canopy_frac)
    )
    delta = estimated_delta_t(segment.features.canopy_frac, target, coefficients.canopy)
    return InterventionEstimate(
        image_id=segment.image_id,
        city=segment.city,
        lat=segment.lat,
        lon=segment.lon,
        current_delta_t=segment.delta_t,
        current_canopy_frac=segment.features.canopy_frac,
        target_canopy_frac=target,
        estimated_delta_t=delta,
        estimated_cooling_c=-delta,
        indicative=True,
        validated=segment.validated,
    )


def rank_interventions(
    segments: List[StreetSegment],
    coefficients: Coefficients,
    target_canopy_frac: Optional[float] = None,
    limit=50,
):
    estimates = [estimate_segment(s, coefficients, target_canopy_frac) for s in segments]
    if coefficients.canopy >= 0:
        estimates.sort(key=lambda item: (item.current_delta_t, -item.current_canopy_frac), reverse=True)
    else:
        estimates.sort(key=lambda item: item.estimated_cooling_c, reverse=True)
    if limit is None:
        return estimates
    return estimates[: max(int(limit), 0)]
