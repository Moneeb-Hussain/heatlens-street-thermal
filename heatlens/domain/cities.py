from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Tuple

from heatlens.errors import NotFoundError, ValidationFailed

METRES_PER_DEGREE_LAT = 111_320.0


@dataclass(frozen=True)
class BoundingBox:
    west: float
    south: float
    east: float
    north: float

    def contains(self, lat, lon):
        return self.south <= lat <= self.north and self.west <= lon <= self.east

    def as_ring(self):
        return [
            [self.west, self.south],
            [self.east, self.south],
            [self.east, self.north],
            [self.west, self.north],
            [self.west, self.south],
        ]


def downtown_bbox(lat, lon, half_km=1.6):
    """~10 km² downtown envelope. Expand after Day 1 coverage counts."""
    import math

    d_lat = (half_km * 1000.0) / METRES_PER_DEGREE_LAT
    d_lon = (half_km * 1000.0) / (METRES_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    return BoundingBox(lon - d_lon, lat - d_lat, lon + d_lon, lat + d_lat)


@dataclass(frozen=True)
class City:
    id: str
    name: str
    role: str
    bbox: BoundingBox
    timezone: str
    coverage_validated: bool
    center: Tuple[float, float]


CITIES = (
    City("phoenix", "Phoenix", "train", downtown_bbox(33.4484, -112.0740), "America/Phoenix", True, (33.4484, -112.0740)),
    City("atlanta", "Atlanta", "train", downtown_bbox(33.7490, -84.3880), "America/New_York", True, (33.7490, -84.3880)),
    City("houston", "Houston", "train", downtown_bbox(29.7604, -95.3698), "America/Chicago", True, (29.7604, -95.3698)),
    City("miami", "Miami", "holdout", downtown_bbox(25.7617, -80.1918), "America/New_York", True, (25.7617, -80.1918)),
    City("karachi", "Karachi", "transfer", downtown_bbox(24.8607, 67.0011), "Asia/Karachi", False, (24.8607, 67.0011)),
    City("lahore", "Lahore", "transfer", downtown_bbox(31.5204, 74.3587), "Asia/Karachi", False, (31.5204, 74.3587)),
)

_BY_ID: Dict[str, City] = {city.id: city for city in CITIES}
TRAIN_CITY_IDS: FrozenSet[str] = frozenset(c.id for c in CITIES if c.role == "train")
HOLD_OUT_CITY_IDS: FrozenSet[str] = frozenset(c.id for c in CITIES if c.role == "holdout")
TRANSFER_CITY_IDS: FrozenSet[str] = frozenset(c.id for c in CITIES if c.role == "transfer")


def get_city(city_id: str) -> City:
    key = (city_id or "").strip().lower()
    city = _BY_ID.get(key)
    if city is None:
        known = ", ".join(sorted(_BY_ID))
        raise NotFoundError("Unknown city '{0}'. Known: {1}".format(city_id, known))
    return city


def require_city(city_id):
    if not city_id or not str(city_id).strip():
        raise ValidationFailed("city is required")
    return get_city(city_id)
