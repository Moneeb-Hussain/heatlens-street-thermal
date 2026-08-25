"""T_street(t) = T_city_forecast(t) + dT_vision."""

from __future__ import annotations

from typing import List

from heatlens.domain.types import ForecastPoint
from heatlens.errors import ValidationFailed


def fuse_absolute(city_temperature_c, delta_t):
    try:
        city = float(city_temperature_c)
        offset = float(delta_t)
    except (TypeError, ValueError):
        raise ValidationFailed("city temperature and delta_t must be numbers")
    return city + offset


def fuse_segments(segments, city_temperature_c):
    city = float(city_temperature_c)
    fused = []
    for segment in segments:
        fused.append(
            {
                "image_id": segment.image_id,
                "lat": segment.lat,
                "lon": segment.lon,
                "city": segment.city,
                "delta_t": segment.delta_t,
                "absolute_c": fuse_absolute(city, segment.delta_t),
                "validated": segment.validated,
                "source": segment.source,
            }
        )
    return fused


def nearest_forecast(series: List[ForecastPoint], timestamp: str) -> ForecastPoint:
    if not series:
        raise ValidationFailed("forecast series is empty")
    if not timestamp:
        return series[0]
    exact = [point for point in series if point.timestamp == timestamp]
    if exact:
        return exact[0]
    earlier = [point for point in series if point.timestamp <= timestamp]
    if earlier:
        return earlier[-1]
    return series[0]
