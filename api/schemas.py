from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from heatlens.domain.cities import CITIES
from heatlens.errors import HeatLensError, NotFoundError, ValidationFailed


class ErrorBody(BaseModel):
    error: bool = True
    code: str
    message: str


class CityOut(BaseModel):
    id: str
    name: str
    role: str
    timezone: str
    coverage_validated: bool
    center_lat: float
    center_lon: float
    bbox: dict


class HealthOut(BaseModel):
    status: str
    version: str
    capabilities: dict


class FeaturesOut(BaseModel):
    canopy_frac: float
    asphalt_frac: float
    sky_frac: float
    building_frac: float


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    image_id: str
    lat: float
    lon: float
    city: str
    block_id: str
    delta_t: float
    split: str
    source: str
    validated: bool
    features: FeaturesOut
    captured_at: Optional[str] = None
    compass_angle: Optional[float] = None
    quality_score: Optional[float] = None
    t_ref_window: Optional[str] = None


class SegmentListOut(BaseModel):
    city: str
    count: int
    segments: list


class ForecastPointOut(BaseModel):
    timestamp: str
    temperature_c: float


class ForecastOut(BaseModel):
    city: str
    source: str
    points: list


class AbsoluteOut(BaseModel):
    city: str
    timestamp: Optional[str] = None
    city_temperature_c: float
    count: int
    segments: list


class FeaturesIn(BaseModel):
    canopy_frac: float = Field(..., ge=0.0, le=1.0)
    asphalt_frac: float = Field(..., ge=0.0, le=1.0)
    sky_frac: float = Field(..., ge=0.0, le=1.0)
    building_frac: float = Field(..., ge=0.0, le=1.0)


class PredictOut(BaseModel):
    delta_t: float
    model: str
    features: Optional[FeaturesOut] = None
    validated: bool = False


class RecommendOut(BaseModel):
    city: str
    indicative: bool = True
    count: int
    items: list
    canopy: Optional[float] = None
    target_canopy_frac: float = 0.4


class ValidatePairOut(BaseModel):
    image_id: str
    predicted_delta_t: Optional[float] = None
    reference_delta_t: float
    validated: bool


class ValidateOut(BaseModel):
    city: str
    count: int
    pairs: list


def cities_payload():
    rows = []
    for city in CITIES:
        rows.append(
            CityOut(
                id=city.id,
                name=city.name,
                role=city.role,
                timezone=city.timezone,
                coverage_validated=city.coverage_validated,
                center_lat=city.center[0],
                center_lon=city.center[1],
                bbox={
                    "west": city.bbox.west,
                    "south": city.bbox.south,
                    "east": city.bbox.east,
                    "north": city.bbox.north,
                },
            )
        )
    return rows


def error_status(exc: HeatLensError) -> int:
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ValidationFailed):
        return 422
    if exc.code.endswith("NOT_CONFIGURED") or exc.code.endswith("NOT_AVAILABLE") or exc.code.endswith("MISSING"):
        return 503
    if exc.code == "UPSTREAM":
        return 502
    return 400
