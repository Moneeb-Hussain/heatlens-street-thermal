"""Turn a city-wide FortyGuard heatmap into a delta_t label per street point.

Owned by: you (see README "Files you own"). FortyGuardClient.heatmap() already
submits + polls + caches one heatmap job per city. This file's job is the
part that was never built: matching a lat/lon photo location to the nearest
heatmap tile and turning (tile_temp, city_mean) into delta_t.

RESOLVED 2026-08-28 against a real, correctly state-matched account
(Atlanta/GA): the original `{"features": [...]}` guess was wrong. The real
shape is `{"map_data": {"type": "FeatureCollection", "features": [...]},
"stats_data": {"activity_id": ..., "n_cells": ...}}`, and each feature's
`properties` carries `average_temperature` directly (see
clients/fortyguard.py::parse_tile_temperature). `_iter_tile_points()` below
now reads `map_data.features` (old guesses kept as fallbacks, harmless).
`stats_data` itself has never been observed with a city-wide mean field, so
`fetch_city_heatmap()` computes the city mean from the tile temperatures
directly instead of guessing a `stats_data` key that may not exist.

ALSO RESOLVED 2026-08-28: querying "today" (or any very recent date)
consistently returns an empty `map_data.features` / `n_cells: 0`, even with
a correctly state-matched key — FortyGuard's real-time processing has a
lag. Querying a date >= 8 days in the past returned real tile data.
`default_heatmap_date()` below picks a date with a safe margin; the exact
minimum lag was not pinned down (untested between 1-7 days), so widen
HEATMAP_DATE_LAG_DAYS if a fresh account/city still comes back empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from heatlens.clients.fortyguard import FortyGuardClient, city_mean_from_stats, parse_tile_temperature
from heatlens.domain.cities import City
from heatlens.errors import UpstreamError, ValidationFailed

HEATMAP_DATE_LAG_DAYS = 7


def default_heatmap_date() -> str:
    """A `start_date` for FortyGuard with enough lag to have real data.

    See module docstring: "today" reliably returns zero tiles. 8 days back
    is confirmed to work; this uses 7 as a slightly tighter but still-safe
    margin. Widen if a query still comes back empty.
    """
    return (datetime.now(timezone.utc).date() - timedelta(days=HEATMAP_DATE_LAG_DAYS)).isoformat()


def fetch_city_heatmap(city: City, client: FortyGuardClient, **heatmap_kwargs):
    """One (cached) FortyGuard heatmap job for the whole city.

    Returns (raw_result, city_mean_c). Cheap to call once per city per run —
    ResponseCache means a second call with the same date/time/granularity is
    a cache hit, not a new billed request.
    """
    result = client.heatmap(city, **heatmap_kwargs)
    try:
        mean_c = city_mean_from_stats(result)
    except ValidationFailed:
        # stats_data has never been observed carrying a city-wide mean --
        # fall back to the mean of the real per-tile temperatures we DO have
        # confirmed (map_data.features[].properties.average_temperature).
        # This is a computed mean of real observed data, not an invented
        # number, so it doesn't break the never-fabricate-temperatures rule.
        mean_c = _mean_from_tiles(result)
    return result, mean_c


def _mean_from_tiles(result) -> float:
    temps = [temp for _lat, _lon, temp in _iter_tile_points(result)]
    if not temps:
        raise UpstreamError("FortyGuard heatmap has no tiles to average for a city mean")
    return sum(temps) / len(temps)


def _iter_tile_points(result):
    features = None
    found_empty_map_data = False
    if isinstance(result, dict):
        map_data = result.get("map_data")
        if isinstance(map_data, dict) and isinstance(map_data.get("features"), list):
            features = map_data["features"]
            found_empty_map_data = features == []
        elif isinstance(result.get("features"), list):
            features = result["features"]
        elif isinstance(result.get("geojson"), dict):
            features = result["geojson"].get("features")
        elif isinstance(result.get("tiles"), list):
            features = result["tiles"]
    if not features:
        if found_empty_map_data:
            raise UpstreamError(
                "FortyGuard heatmap has 0 tiles for this query (empty map_data.features / "
                "n_cells: 0). Not a schema problem -- likely the query date is too recent "
                "(see default_heatmap_date()) or this account/city has no coverage yet."
            )
        keys = sorted(result.keys()) if isinstance(result, dict) else type(result).__name__
        raise UpstreamError(
            "Could not find a tile/feature list in the FortyGuard heatmap result "
            "(top-level keys: {0}). Inspect a real response and update "
            "ingest/fortyguard.py::_iter_tile_points before trusting any delta_t "
            "it produces.".format(keys)
        )
    for feature in features:
        geometry = (feature.get("geometry") or {}) if isinstance(feature, dict) else {}
        point = _representative_point(geometry.get("type"), geometry.get("coordinates"))
        if point is None:
            continue
        lon, lat = point
        try:
            temp = parse_tile_temperature(feature)
        except Exception:
            continue
        yield lat, lon, temp


def _representative_point(geom_type, coords) -> Optional[Tuple[float, float]]:
    if not coords:
        return None
    if geom_type == "Point":
        return float(coords[0]), float(coords[1])
    if geom_type == "Polygon":
        ring = coords[0]
        return _centroid(ring)
    if geom_type == "MultiPolygon":
        ring = coords[0][0]
        return _centroid(ring)
    return None


def _centroid(ring):
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return sum(lons) / len(lons), sum(lats) / len(lats)


def nearest_tile_temperature(result, lat, lon):
    """Nearest heatmap tile's temperature to (lat, lon).

    City grids here are ~3.2km across, so plain Euclidean distance in
    degrees (not haversine) is accurate enough to pick the nearest tile.
    """
    best = None
    best_dist = None
    for tile_lat, tile_lon, temp in _iter_tile_points(result):
        d = (tile_lat - lat) ** 2 + (tile_lon - lon) ** 2
        if best_dist is None or d < best_dist:
            best_dist = d
            best = temp
    if best is None:
        raise UpstreamError("FortyGuard heatmap has no usable tiles near ({0}, {1})".format(lat, lon))
    return best


def delta_t_for_point(result, city_mean_c, lat, lon):
    """delta_t = tile temperature at this point minus the city-wide mean."""
    tile_temp = nearest_tile_temperature(result, lat, lon)
    return round(tile_temp - city_mean_c, 2)
