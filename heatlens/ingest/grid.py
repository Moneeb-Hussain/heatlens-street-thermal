"""50 m sampling grid and 1 km spatial blocks. Pure Python — no GeoPandas."""

from __future__ import annotations

import math
from typing import Iterator, List, Tuple

from heatlens.domain.cities import BoundingBox, City
from heatlens.errors import ValidationFailed

METRES_PER_DEGREE_LAT = 111_320.0
GRID_SPACING_M = 50.0
BLOCK_SIZE_M = 1_000.0


def metres_to_degrees(lat, metres):
    d_lat = metres / METRES_PER_DEGREE_LAT
    cos_lat = math.cos(math.radians(lat))
    if abs(cos_lat) < 1e-6:
        raise ValidationFailed("cannot build a lon grid at the pole")
    d_lon = metres / (METRES_PER_DEGREE_LAT * cos_lat)
    return d_lat, d_lon


def grid_centroids(bbox: BoundingBox, spacing_m=GRID_SPACING_M) -> List[Tuple[float, float]]:
    if spacing_m <= 0:
        raise ValidationFailed("spacing_m must be positive")
    mid_lat = (bbox.south + bbox.north) / 2.0
    d_lat, d_lon = metres_to_degrees(mid_lat, spacing_m)
    points = []
    lat = bbox.south + d_lat / 2.0
    while lat <= bbox.north:
        lon = bbox.west + d_lon / 2.0
        while lon <= bbox.east:
            if bbox.contains(lat, lon):
                points.append((round(lat, 7), round(lon, 7)))
            lon += d_lon
        lat += d_lat
    return points


def block_id(lat, lon, block_m=BLOCK_SIZE_M) -> str:
    d_lat, d_lon = metres_to_degrees(lat, block_m)
    lat_idx = int(math.floor(lat / d_lat))
    lon_idx = int(math.floor(lon / d_lon))
    return "b_{0}_{1}".format(lat_idx, lon_idx)


def iter_city_grid(city: City, spacing_m=GRID_SPACING_M) -> Iterator[Tuple[float, float, str]]:
    for lat, lon in grid_centroids(city.bbox, spacing_m):
        yield lat, lon, block_id(lat, lon)


def spread_order(points):
    """Reorder a finite sequence of points so that ANY prefix (first 50, first
    500, all of it) is spread across the whole area instead of clustered in
    one corner.

    iter_city_grid() walks row-by-row (south->north, west->east), so a plain
    `--limit N` truncation only ever samples one geographic strip. We saw this
    bite us for real on Atlanta: the first 300 grid points in raw order gave
    1/300 kept, while an evenly-spread 300 gave 19/300 — an ~19x difference
    from ordering alone. This uses a golden-ratio stride (additive recurrence
    / Fibonacci sampling — a standard low-discrepancy trick) so every prefix
    of the reordered list is a representative sample, which matters when a
    pull is capped by --limit or handed over in batches before it finishes.
    """
    items = list(points)
    n = len(items)
    if n <= 2:
        return items
    stride = max(round(n * 0.6180339887498949), 1)  # golden ratio conjugate
    while math.gcd(stride, n) != 1:
        stride += 1
        if stride >= n:
            stride = 1
            break
    return [items[(i * stride) % n] for i in range(n)]
