"""Reverse-geocode a lat/lon to an OSM street label. Cached. No invented names."""

from __future__ import annotations

from typing import Optional

import httpx

from heatlens.clients.cache import ResponseCache, cache_key

PHOTON_URL = "https://photon.komoot.io/reverse"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "HeatLens/0.1 (street-thermal hackathon)"
ROAD_KEYS = (
    "road",
    "pedestrian",
    "residential",
    "footway",
    "path",
    "cycleway",
    "highway",
)


def road_from_address(address) -> Optional[str]:
    if not isinstance(address, dict):
        return None
    for key in ROAD_KEYS:
        value = (address.get(key) or "").strip()
        if value:
            return value
    return None


def road_from_display_name(display_name) -> Optional[str]:
    if not isinstance(display_name, str) or not display_name.strip():
        return None
    for part in display_name.split(","):
        value = part.strip()
        if not value:
            continue
        if value.replace("-", "").isdigit():
            continue
        return value
    return None


def road_from_nominatim(payload) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    return road_from_address(payload.get("address")) or road_from_display_name(
        payload.get("display_name")
    )


def road_from_photon(payload) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    features = payload.get("features") or []
    if not features or not isinstance(features[0], dict):
        return None
    props = features[0].get("properties") or {}
    if not isinstance(props, dict):
        return None
    street = (props.get("street") or "").strip()
    if street:
        return street
    name = (props.get("name") or "").strip()
    if not name:
        return None
    if props.get("osm_key") == "highway" or props.get("type") in ("street", "house"):
        return name
    return name


def intersection_label(roads):
    unique = []
    for name in roads:
        if name and name not in unique:
            unique.append(name)
        if len(unique) == 2:
            break
    if not unique:
        return None
    if len(unique) == 1:
        return unique[0]
    return "{0} & {1}".format(unique[0], unique[1])


class NominatimClient(object):
    def __init__(self, cache: Optional[ResponseCache] = None, transport=None):
        self._cache = cache
        self._client = httpx.Client(
            timeout=httpx.Timeout(12.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            transport=transport,
            trust_env=False,
        )

    def close(self):
        self._client.close()

    def street_name(self, lat, lon) -> Optional[str]:
        lat_f = float(lat)
        lon_f = float(lon)
        return self._road_photon(lat_f, lon_f) or self._road_nominatim(lat_f, lon_f)

    def _cached(self, provider, lat, lon):
        rounded = "{0:.5f},{1:.5f}".format(lat, lon)
        key = cache_key(provider, {"at": rounded})
        if self._cache:
            cached = self._cache.get(key)
            if cached is not None:
                return key, cached.get("road")
        return key, None

    def _store(self, key, provider, path, road):
        if self._cache:
            self._cache.put(key, {"road": road})
            self._cache.record(provider, path, "ok", cache_hit=False)

    def _road_photon(self, lat, lon) -> Optional[str]:
        key, cached = self._cached("photon", lat, lon)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                PHOTON_URL,
                params={"lat": "{0:.6f}".format(lat), "lon": "{0:.6f}".format(lon)},
            )
            response.raise_for_status()
            road = road_from_photon(response.json())
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        self._store(key, "photon", "/reverse", road)
        return road

    def _road_nominatim(self, lat, lon) -> Optional[str]:
        key, cached = self._cached("nominatim", lat, lon)
        if cached is not None:
            return cached
        try:
            response = self._client.get(
                NOMINATIM_URL,
                params={
                    "lat": "{0:.6f}".format(lat),
                    "lon": "{0:.6f}".format(lon),
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "zoom": 18,
                },
                timeout=httpx.Timeout(22.0, connect=6.0),
            )
            response.raise_for_status()
            road = road_from_nominatim(response.json())
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        self._store(key, "nominatim", "/reverse", road)
        return road
