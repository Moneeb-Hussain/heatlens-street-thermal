"""Bulk street-photo download from Mapillary for a city's sampling grid.

Owned by: you (see README "Files you own"). Uses the already-built
MapillaryClient and photo-quality filters — this file is the missing
"walk the grid, keep good photos, save them to disk" driver.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator, Optional

import httpx

from heatlens.clients.mapillary import MapillaryClient
from heatlens.domain.cities import City
from heatlens.ingest.filters import is_usable_image
from heatlens.ingest.grid import GRID_SPACING_M, iter_city_grid, spread_order


class DownloadResult(object):
    """One outcome per grid point: accepted photo, or the reason it was skipped."""

    __slots__ = ("lat", "lon", "block_id", "image", "accepted", "reason", "photo_path")

    def __init__(self, lat, lon, block_id, image=None, accepted=False, reason="no_photo", photo_path=None):
        self.lat = lat
        self.lon = lon
        self.block_id = block_id
        self.image = image
        self.accepted = accepted
        self.reason = reason
        self.photo_path = photo_path


def download_city_photos(
    city: City,
    mapillary: MapillaryClient,
    out_dir: Path,
    spacing_m: float = GRID_SPACING_M,
    limit: Optional[int] = None,
    sleep_s: float = 0.0,
    downloader: Optional[httpx.Client] = None,
) -> Iterator[DownloadResult]:
    """Walk the city's 50m sampling grid, pull the best Mapillary photo within
    50m of each point, keep it if it passes quality filters (no panos, no
    fisheye, daylight hours, in-bbox, min quality score — see ingest/filters.py),
    and save the JPEG to ``out_dir/<image_id>.jpg``.

    Yields one DownloadResult per grid point visited (accepted or not) so the
    caller can report coverage stats without holding everything in memory.
    Safe to re-run: already-downloaded image files are not re-fetched, and a
    photo already matched to a previous grid point in this run is skipped
    (dense grid, sparse imagery — many points share the same nearest photo).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    http = downloader or httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))
    owns_http = downloader is None
    seen_images = set()
    n = 0
    # Spread order, not raw grid order: iter_city_grid walks row-by-row, so a
    # plain --limit truncation (or a run stopped/batched partway through)
    # would only ever sample one geographic corner of the city. Confirmed on
    # real data (Atlanta): first-300-in-order got 1/300 kept vs 19/300 for an
    # evenly-spread 300. spread_order() makes every prefix representative.
    ordered_points = spread_order(list(iter_city_grid(city, spacing_m)))
    try:
        for lat, lon, block in ordered_points:
            if limit is not None and n >= limit:
                return
            n += 1
            image = mapillary.best_image(lat, lon)
            if not image:
                yield DownloadResult(lat, lon, block, reason="no_photo")
                continue
            ok, reason = is_usable_image(image, city)
            if not ok:
                yield DownloadResult(lat, lon, block, image=image, reason=reason)
                continue
            image_id = str(image["id"])
            if image_id in seen_images:
                yield DownloadResult(lat, lon, block, image=image, reason="duplicate_image")
                continue
            seen_images.add(image_id)
            photo_path = out_dir / "{0}.jpg".format(image_id)
            if not photo_path.exists():
                url = image.get("thumb_1024_url")
                if not url:
                    yield DownloadResult(lat, lon, block, image=image, reason="no_thumb_url")
                    continue
                response = http.get(url)
                response.raise_for_status()
                photo_path.write_bytes(response.content)
            yield DownloadResult(
                lat, lon, block, image=image, accepted=True, reason="ok", photo_path=photo_path
            )
            if sleep_s:
                time.sleep(sleep_s)
    finally:
        if owns_http:
            http.close()
