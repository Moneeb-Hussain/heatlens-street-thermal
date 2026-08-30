"""Map a semantic mask to HeatLens urban-form fractions. No invented values."""

from __future__ import annotations

# ADE20K ids used by nvidia/segformer-b*-ade (0-indexed).
ADE_TREE = 4
ADE_GRASS = 9
ADE_PLANT = 17
ADE_ROAD = 6
ADE_SKY = 2
ADE_BUILDING = 1

CANOPY_IDS = frozenset({ADE_TREE, ADE_GRASS, ADE_PLANT})
ASPHALT_IDS = frozenset({ADE_ROAD})
SKY_IDS = frozenset({ADE_SKY})
BUILDING_IDS = frozenset({ADE_BUILDING})


def fractions_from_class_ids(class_ids) -> dict:
    """Pixel fractions from a flat sequence of ADE20K class ids.

    `class_ids` is any iterable of ints (row-major mask). Empty mask raises.
    """
    counts = {"canopy": 0, "asphalt": 0, "sky": 0, "building": 0, "n": 0}
    for raw in class_ids:
        cid = int(raw)
        counts["n"] += 1
        if cid in CANOPY_IDS:
            counts["canopy"] += 1
        elif cid in ASPHALT_IDS:
            counts["asphalt"] += 1
        elif cid in SKY_IDS:
            counts["sky"] += 1
        elif cid in BUILDING_IDS:
            counts["building"] += 1
    n = counts["n"]
    if n <= 0:
        raise ValueError("semantic mask is empty")
    total = float(n)
    return {
        "canopy_frac": round(counts["canopy"] / total, 4),
        "asphalt_frac": round(counts["asphalt"] / total, 4),
        "sky_frac": round(counts["sky"] / total, 4),
        "building_frac": round(counts["building"] / total, 4),
    }
