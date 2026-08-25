from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from heatlens.errors import ValidationFailed

ALLOWED_SPLITS = frozenset({"train", "val", "test", "holdout_city"})
FRACTION_FIELDS = ("canopy_frac", "asphalt_frac", "sky_frac", "building_frac")


def _require_fraction(name, value):
    if value is None:
        raise ValidationFailed("{0} is required".format(name))
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationFailed("{0} must be a number".format(name))
    if number < 0.0 or number > 1.0:
        raise ValidationFailed("{0} must be in [0, 1], got {1}".format(name, number))
    return number


def _require_lat(lat):
    try:
        number = float(lat)
    except (TypeError, ValueError):
        raise ValidationFailed("lat must be a number")
    if number < -90.0 or number > 90.0:
        raise ValidationFailed("lat must be in [-90, 90]")
    return number


def _require_lon(lon):
    try:
        number = float(lon)
    except (TypeError, ValueError):
        raise ValidationFailed("lon must be a number")
    if number < -180.0 or number > 180.0:
        raise ValidationFailed("lon must be in [-180, 180]")
    return number


@dataclass(frozen=True)
class UrbanFormFeatures:
    canopy_frac: float
    asphalt_frac: float
    sky_frac: float
    building_frac: float

    def __post_init__(self):
        object.__setattr__(self, "canopy_frac", _require_fraction("canopy_frac", self.canopy_frac))
        object.__setattr__(self, "asphalt_frac", _require_fraction("asphalt_frac", self.asphalt_frac))
        object.__setattr__(self, "sky_frac", _require_fraction("sky_frac", self.sky_frac))
        object.__setattr__(self, "building_frac", _require_fraction("building_frac", self.building_frac))

    def as_dict(self):
        return {
            "canopy_frac": self.canopy_frac,
            "asphalt_frac": self.asphalt_frac,
            "sky_frac": self.sky_frac,
            "building_frac": self.building_frac,
        }


@dataclass(frozen=True)
class StreetSegment:
    image_id: str
    lat: float
    lon: float
    city: str
    block_id: str
    delta_t: float
    features: UrbanFormFeatures
    split: str
    source: str
    validated: bool
    captured_at: Optional[str] = None
    compass_angle: Optional[float] = None
    quality_score: Optional[float] = None
    t_ref_window: Optional[str] = None

    def __post_init__(self):
        if not (self.image_id or "").strip():
            raise ValidationFailed("image_id is required")
        object.__setattr__(self, "lat", _require_lat(self.lat))
        object.__setattr__(self, "lon", _require_lon(self.lon))
        if self.split not in ALLOWED_SPLITS:
            raise ValidationFailed("split must be one of {0}".format(sorted(ALLOWED_SPLITS)))
        object.__setattr__(self, "delta_t", float(self.delta_t))

    def as_dict(self):
        payload = {
            "image_id": self.image_id,
            "lat": self.lat,
            "lon": self.lon,
            "city": self.city,
            "block_id": self.block_id,
            "delta_t": self.delta_t,
            "split": self.split,
            "source": self.source,
            "validated": self.validated,
            "captured_at": self.captured_at,
            "compass_angle": self.compass_angle,
            "quality_score": self.quality_score,
            "t_ref_window": self.t_ref_window,
        }
        payload.update(self.features.as_dict())
        return payload


@dataclass(frozen=True)
class Coefficients:
    intercept: float
    canopy: float
    asphalt: float
    sky: float
    building: float
    target_canopy_frac: float = 0.40

    def __post_init__(self):
        object.__setattr__(
            self, "target_canopy_frac", _require_fraction("target_canopy_frac", self.target_canopy_frac)
        )


@dataclass(frozen=True)
class ForecastPoint:
    timestamp: str
    temperature_c: float


@dataclass(frozen=True)
class InterventionEstimate:
    image_id: str
    city: str
    lat: float
    lon: float
    current_delta_t: float
    current_canopy_frac: float
    target_canopy_frac: float
    estimated_delta_t: float
    estimated_cooling_c: float
    indicative: bool = True
    validated: bool = False
