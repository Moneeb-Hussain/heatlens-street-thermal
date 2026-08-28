"""FortyGuard Temperature API client.

POST /v1/heatmap then poll GET /v1/status/{activity_id}.
US coverage only. Does not invent temperatures when the key is missing.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from heatlens.clients.cache import ResponseCache, cache_key
from heatlens.domain.cities import City
from heatlens.errors import CapabilityUnavailable, UpstreamError, ValidationFailed

FILTER_SINGLE_HOUR = 1
FILTER_RANGE_HOURS = 2
FILTER_SINGLE_DAY = 3
ALLOWED_GRANULARITY = frozenset({60, 80, 100})
TERMINAL_OK = frozenset({"completed", "succeeded"})
TERMINAL_FAIL = frozenset({"failed", "error"})


class FortyGuardClient(object):
    def __init__(self, api_key, base_url, cache: Optional[ResponseCache] = None, transport=None):
        if not api_key:
            raise CapabilityUnavailable(
                "FORTYGUARD_NOT_CONFIGURED",
                "FORTYGUARD_API_KEY is not set. HeatLens will not fabricate temperatures.",
            )
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._cache = cache
        self._client = httpx.Client(
            base_url=self._base,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
        )

    def close(self):
        self._client.close()

    def heatmap(
        self,
        city: City,
        start_date,
        start_time="14:00",
        filter_type=FILTER_SINGLE_HOUR,
        granularity=100,
        end_time=None,
        end_date=None,
        poll_seconds=5.0,
        max_polls=120,
    ):
        if granularity not in ALLOWED_GRANULARITY:
            raise ValidationFailed("granularity must be 60, 80, or 100 metres")
        if filter_type not in (FILTER_SINGLE_HOUR, FILTER_RANGE_HOURS, FILTER_SINGLE_DAY):
            raise ValidationFailed("filter_type must be 1, 2, or 3")
        payload = {
            "polygon_aoi": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"city": city.id},
                        "geometry": {"type": "Polygon", "coordinates": [city.bbox.as_ring()]},
                    }
                ],
            },
            "date_time": _date_time(start_date, start_time, filter_type, end_time, end_date),
            "granularity": granularity,
        }
        key = cache_key("heatmap", payload)
        if self._cache:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.record("fortyguard", "/v1/heatmap", "cache_hit", cache_hit=True)
                return cached

        activity_id = self._submit("/v1/heatmap", payload)
        result = self._poll(activity_id, poll_seconds=poll_seconds, max_polls=max_polls)
        if self._cache:
            self._cache.put(key, result)
            self._cache.record(
                "fortyguard", "/v1/heatmap", "completed", activity_id=activity_id, cache_hit=False
            )
        return result

    def _submit(self, path, payload) -> str:
        try:
            response = self._client.post(path, json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamError("FortyGuard submit failed: {0}".format(_safe(exc))) from exc
        data = _decode(response)
        activity_id = (data.get("data") or {}).get("activity_id")
        if not activity_id:
            raise UpstreamError("FortyGuard submit returned no activity_id")
        return activity_id

    def _poll(self, activity_id, poll_seconds, max_polls):
        path = "/v1/status/{0}".format(activity_id)
        for attempt in range(max_polls):
            try:
                response = self._client.get(path)
            except httpx.HTTPError as exc:
                raise UpstreamError("FortyGuard poll failed: {0}".format(_safe(exc))) from exc
            if response.status_code == 404:
                # Freshly submitted activities can be briefly unqueryable right
                # after /v1/heatmap returns an activity_id (seen on newly
                # created accounts). Not a real failure unless it never clears.
                if attempt == max_polls - 1:
                    raise UpstreamError(
                        "FortyGuard activity {0} never became queryable (still 404 after {1} polls)".format(
                            activity_id, max_polls
                        )
                    )
                time.sleep(poll_seconds)
                continue
            data = _decode(response)
            body = data.get("data") or {}
            status = str(body.get("status") or data.get("message") or "").lower()
            if status in TERMINAL_OK:
                return body.get("result") or body
            if status in TERMINAL_FAIL:
                raise UpstreamError("FortyGuard activity {0} failed".format(activity_id))
            time.sleep(poll_seconds)
        raise UpstreamError("FortyGuard activity {0} timed out".format(activity_id))


def parse_tile_temperature(feature):
    """Read a heatmap tile's temperature.

    Confirmed against a real (non-empty) response 2026-08-28: each feature's
    `properties` carries `average_temperature` (plus `min_temperature` /
    `max_temperature`) directly -- not nested under a `Temperature_stats`
    object as originally guessed. Keeping the old candidate keys as a
    fallback in case a different city/plan tier shapes it differently.
    """
    props = feature.get("properties") or {}
    for key in (
        "average_temperature",
        "temperature",
        "Temperature",
        "tcm",
        "temp",
        "value",
    ):
        if key in props and props[key] is not None:
            return float(props[key])
    stats = props.get("Temperature_stats") or props.get("temperature_stats") or {}
    if isinstance(stats, dict) and stats.get("Mean") is not None:
        return float(stats["Mean"])
    raise ValidationFailed("heatmap tile has no recognised temperature property")


def city_mean_from_stats(result):
    """City-wide mean temperature from a heatmap result's `stats_data`.

    NOTE: as of 2026-08-28 we've only ever seen `stats_data` populated with
    `activity_id` / `n_cells` (real tile data lives under `map_data`, see
    parse_tile_temperature). Whether FortyGuard's `stats_data` ever carries
    a city-wide mean at all -- and under what key -- is still unconfirmed.
    The candidate keys below are checked but NOT invented from nothing: if
    none match, this raises rather than guessing, per the project's
    never-fabricate-a-temperature rule. If this keeps raising once real
    `n_cells > 0` data is flowing, fall back to computing the mean from the
    tile temperatures in `map_data` instead (see ingest/fortyguard.py).
    """
    stats = (result or {}).get("stats_data") or {}
    temp_stats = stats.get("Temperature_stats") or stats.get("temperature_stats") or stats
    mean = None
    if isinstance(temp_stats, dict):
        mean = (
            temp_stats.get("Mean")
            or temp_stats.get("mean")
            or temp_stats.get("average_temperature")
            or temp_stats.get("mean_temperature")
        )
    if mean is None:
        raise ValidationFailed("heatmap stats_data has no recognised mean-temperature field")
    return float(mean)


def _date_time(start_date, start_time, filter_type, end_time, end_date):
    body = {"start_date": start_date, "filter_type": filter_type}
    if filter_type in (FILTER_SINGLE_HOUR, FILTER_RANGE_HOURS):
        body["start_time"] = start_time
    if filter_type == FILTER_RANGE_HOURS:
        if not end_time:
            raise ValidationFailed("end_time is required for filter_type=2")
        body["end_time"] = end_time
    if end_date:
        body["end_date"] = end_date
    return body


def _decode(response: httpx.Response) -> dict:
    if response.status_code >= 400:
        raise UpstreamError(
            "FortyGuard HTTP {0}: {1}".format(response.status_code, _safe(response.text[:300]))
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise UpstreamError("FortyGuard returned non-JSON") from exc
    if data.get("error") is True:
        raise UpstreamError(data.get("message") or "FortyGuard error")
    return data


def _safe(text):
    return str(text).replace("api-key", "api-key[redacted]")
