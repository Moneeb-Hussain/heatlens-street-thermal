"""Mapillary Graph API — 50 m radius search (max radius the platform allows)."""

from __future__ import annotations

from typing import Optional

import httpx

from heatlens.clients.cache import ResponseCache, cache_key
from heatlens.errors import CapabilityUnavailable, UpstreamError, ValidationFailed

IMAGE_FIELDS = (
    "id,geometry,computed_geometry,captured_at,compass_angle,camera_type,"
    "is_pano,quality_score,thumb_1024_url"
)
MAX_RADIUS_M = 50


class MapillaryClient(object):
    def __init__(self, access_token, cache: Optional[ResponseCache] = None, transport=None):
        if not access_token:
            raise CapabilityUnavailable(
                "MAPILLARY_NOT_CONFIGURED",
                "MAPILLARY_ACCESS_TOKEN is not set.",
            )
        self._token = access_token
        self._cache = cache
        self._client = httpx.Client(
            base_url="https://graph.mapillary.com",
            timeout=httpx.Timeout(20.0, connect=10.0),
            transport=transport,
        )

    def close(self):
        self._client.close()

    def best_image(self, lat, lon, radius_m=MAX_RADIUS_M):
        if radius_m <= 0 or radius_m > MAX_RADIUS_M:
            raise ValidationFailed("Mapillary radius must be in (0, 50] metres")
        key = cache_key("mapillary", lat, lon, radius_m)
        if self._cache:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.record("mapillary", "/images", "cache_hit", cache_hit=True)
                return cached
        params = {
            "access_token": self._token,
            "fields": IMAGE_FIELDS,
            "lat": lat,
            "lng": lon,
            "radius": radius_m,
            "limit": 1,
        }
        try:
            response = self._client.get("/images", params=params)
        except httpx.HTTPError as exc:
            raise UpstreamError("Mapillary request failed: {0}".format(exc)) from exc
        if response.status_code >= 400:
            raise UpstreamError("Mapillary HTTP {0}".format(response.status_code))
        try:
            body = response.json()
        except ValueError as exc:
            raise UpstreamError("Mapillary returned non-JSON") from exc
        rows = body.get("data") or []
        image = rows[0] if rows else None
        if self._cache:
            self._cache.put(key, image)
            self._cache.record("mapillary", "/images", "ok", cache_hit=False)
        return image
