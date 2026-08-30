from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from api import deps
from api.schemas import (
    AbsoluteOut,
    FeaturesIn,
    ForecastOut,
    FeaturesOut,
    HealthOut,
    PredictOut,
    RecommendOut,
    SegmentListOut,
    SegmentOut,
    ValidateOut,
    ValidatePairOut,
    cities_payload,
)
from heatlens import __version__
from heatlens.domain.cities import require_city
from heatlens.domain.types import UrbanFormFeatures
from heatlens.errors import CapabilityUnavailable, HeatLensError, UpstreamError
from heatlens.services.fusion import fuse_segments
from heatlens.services.recommend import rank_interventions

router = APIRouter()

ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})


def _segment_out(segment) -> SegmentOut:
    return SegmentOut(
        image_id=segment.image_id,
        lat=segment.lat,
        lon=segment.lon,
        city=segment.city,
        block_id=segment.block_id,
        delta_t=segment.delta_t,
        split=segment.split,
        source=segment.source,
        validated=segment.validated,
        features=FeaturesOut(**segment.features.as_dict()),
        captured_at=segment.captured_at,
        compass_angle=segment.compass_angle,
        quality_score=segment.quality_score,
        t_ref_window=segment.t_ref_window,
    )


@router.get("/health", response_model=HealthOut)
def health():
    settings = deps.get_settings()
    return HealthOut(
        status="ok",
        version=__version__,
        capabilities={
            "segments": settings.has_segments(),
            "fortyguard": settings.has_fortyguard(),
            "mapillary": settings.has_mapillary(),
            "coefficients": settings.has_coefficients(),
            "model": settings.has_model(),
            "model_name": deps.model_capability(),
        },
    )


@router.get("/cities")
def list_cities():
    return {"cities": [row.model_dump() for row in cities_payload()]}


@router.get("/street-name")
def street_name(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    client = deps.get_nominatim()
    try:
        name = client.street_name(lat, lon)
    except Exception:
        name = None
    finally:
        client.close()
    return {"street": name, "source": "geocode"}


@router.get("/segments", response_model=SegmentListOut)
def list_segments(city: str = Query(..., min_length=1)):
    city_id = require_city(city).id
    segments = deps.get_store().list_segments(city_id)
    return SegmentListOut(
        city=city_id,
        count=len(segments),
        segments=[_segment_out(item).model_dump() for item in segments],
    )


def _city_temperature_c(city_id, timestamp):
    settings = deps.get_settings()
    if not settings.has_fortyguard_for(city_id):
        raise CapabilityUnavailable(
            "FORTYGUARD_NOT_CONFIGURED",
            "Cannot read live temperature without FORTYGUARD_API_KEY_{0} (or FORTYGUARD_API_KEY).".format(
                city_id.upper()
            ),
        )
    city_obj = require_city(city_id)
    if timestamp:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
    else:
        from ingest.fortyguard import default_heatmap_date

        moment = datetime.fromisoformat(default_heatmap_date() + "T14:00:00+00:00")
    from ingest.fortyguard import fetch_city_heatmap

    client = deps.get_fortyguard(city_id)
    try:
        _result, temperature = fetch_city_heatmap(
            city_obj,
            client,
            start_date=moment.date().isoformat(),
            start_time=moment.strftime("%H:%M"),
            filter_type=1,
            granularity=100,
        )
        return moment, temperature
    except HeatLensError:
        raise
    except Exception as exc:
        raise UpstreamError("FortyGuard city temperature failed: {0}".format(exc)) from exc
    finally:
        client.close()


@router.get("/forecast", response_model=ForecastOut)
def forecast(
    city: str = Query(..., min_length=1),
    timestamp: Optional[str] = Query(None),
):
    """One citywide snapshot. Each call is one cached FortyGuard heatmap job."""
    city_id = require_city(city).id
    moment, temperature = _city_temperature_c(city_id, timestamp)
    return ForecastOut(
        city=city_id,
        source="fortyguard",
        points=[
            {
                "timestamp": moment.isoformat().replace("+00:00", "Z"),
                "temperature_c": temperature,
            }
        ],
    )


@router.get("/absolute", response_model=AbsoluteOut)
def absolute_temperature(
    city: str = Query(..., min_length=1),
    timestamp: Optional[str] = Query(None),
):
    city_id = require_city(city).id
    moment, city_t = _city_temperature_c(city_id, timestamp)
    segments = deps.get_store().list_segments(city_id)
    return AbsoluteOut(
        city=city_id,
        timestamp=moment.isoformat(),
        city_temperature_c=city_t,
        count=len(segments),
        segments=fuse_segments(segments, city_t),
    )


@router.post("/predict", response_model=PredictOut)
async def predict_image(file: UploadFile = File(...)):
    settings = deps.get_settings()
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=422, detail="empty file")
    if len(payload) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="file exceeds max upload size")
    raise CapabilityUnavailable(
        "MODEL_NOT_AVAILABLE",
        "Image inference requires a trained artefact. Use POST /predict/features for B1.",
    )


@router.post("/predict/features", response_model=PredictOut)
def predict_features(body: FeaturesIn):
    model = deps.try_linear()
    features = UrbanFormFeatures(**body.model_dump())
    return PredictOut(
        delta_t=model.predict_delta_t(features),
        model=model.name,
        features=FeaturesOut(**features.as_dict()),
        validated=False,
    )


@router.get("/recommend", response_model=RecommendOut)
def recommend(
    city: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=500),
    target_canopy_frac: Optional[float] = Query(None, ge=0.0, le=1.0),
):
    city_id = require_city(city).id
    coefficients = deps.try_coefficients()
    segments = deps.get_store().list_segments(city_id)
    items = rank_interventions(segments, coefficients, target_canopy_frac, limit=limit)
    return RecommendOut(
        city=city_id,
        indicative=True,
        count=len(items),
        canopy=coefficients.canopy,
        target_canopy_frac=target_canopy_frac if target_canopy_frac is not None else coefficients.target_canopy_frac,
        items=[
            {
                "image_id": item.image_id,
                "lat": item.lat,
                "lon": item.lon,
                "current_delta_t": item.current_delta_t,
                "current_canopy_frac": item.current_canopy_frac,
                "target_canopy_frac": item.target_canopy_frac,
                "estimated_delta_t": item.estimated_delta_t,
                "estimated_cooling_c": item.estimated_cooling_c,
                "indicative": item.indicative,
                "validated": item.validated,
            }
            for item in items
        ],
    )


@router.get("/validate", response_model=ValidateOut)
def validate_view(city: str = Query(..., min_length=1)):
    city_id = require_city(city).id
    segments = deps.get_store().list_segments(city_id)
    model = None
    try:
        model = deps.try_linear()
    except CapabilityUnavailable:
        model = None
    pairs = [
        ValidatePairOut(
            image_id=item.image_id,
            predicted_delta_t=model.predict_delta_t(item.features) if model else None,
            reference_delta_t=item.delta_t,
            validated=item.validated,
        ).model_dump()
        for item in segments
    ]
    return ValidateOut(city=city_id, count=len(pairs), pairs=pairs)
