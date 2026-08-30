"""Quality filters for Mapillary frames (Day 2 ingest)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from heatlens.domain.cities import City

REJECT_CAMERA_TYPES = frozenset({"fisheye", "equirectangular", "spherical"})
DAYLIGHT_START_HOUR = 10
DAYLIGHT_END_HOUR = 16
MAX_AGE_DAYS = 365 * 7  # bumped 5->7yr per Moneeb 2026-08-26: Atlanta raw data showed a Dec-2019 bulk capture wave that a 5yr cutoff still missed; 7yr recovered 6.3%->40.7% kept
MIN_QUALITY = 0.40


def is_usable_image(image, city: City, now=None, min_quality=MIN_QUALITY):
    """Return (ok, reason). `image` is a dict of Mapillary fields."""
    if image.get("is_pano") is True:
        return False, "panorama"
    camera = (image.get("camera_type") or "").lower()
    if camera in REJECT_CAMERA_TYPES:
        return False, "camera_type:{0}".format(camera)
    quality = image.get("quality_score")
    if quality is not None and float(quality) < min_quality:
        return False, "quality_score"
    captured = _as_utc(image.get("captured_at"))
    if captured is None:
        return False, "missing_captured_at"
    clock = now or datetime.now(timezone.utc)
    if captured < clock - timedelta(days=MAX_AGE_DAYS):
        return False, "stale"
    local = captured.astimezone(ZoneInfo(city.timezone))
    if local.hour < DAYLIGHT_START_HOUR or local.hour >= DAYLIGHT_END_HOUR:
        return False, "not_daylight"
    geometry = image.get("computed_geometry") or image.get("geometry") or {}
    coords = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if not coords or len(coords) < 2:
        return False, "missing_geometry"
    lon, lat = float(coords[0]), float(coords[1])
    if not city.bbox.contains(lat, lon):
        return False, "outside_bbox"
    return True, "ok"


def _as_utc(value) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        millis = float(value)
        seconds = millis / 1000.0 if millis > 10_000_000_000 else millis
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
