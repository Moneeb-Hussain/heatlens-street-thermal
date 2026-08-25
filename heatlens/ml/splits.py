"""Spatial-block split checks. Random splits are forbidden."""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Set

from heatlens.domain.cities import HOLD_OUT_CITY_IDS, TRAIN_CITY_IDS
from heatlens.domain.types import StreetSegment
from heatlens.errors import ValidationFailed


def leakage_report(segments: Iterable[StreetSegment]) -> Dict[str, object]:
    items = list(segments)
    by_split = defaultdict(set)  # type: Dict[str, Set[str]]
    for segment in items:
        by_split[segment.split].add(segment.block_id)

    leaked = sorted((by_split["train"] | by_split["val"]) & by_split["test"])
    holdout_in_train = sorted(
        {
            segment.city
            for segment in items
            if segment.city in HOLD_OUT_CITY_IDS and segment.split in ("train", "val")
        }
    )
    train_city_as_holdout = sorted(
        {
            segment.city
            for segment in items
            if segment.city in TRAIN_CITY_IDS and segment.split == "holdout_city"
        }
    )
    return {
        "leaked_blocks": leaked,
        "holdout_cities_in_train": holdout_in_train,
        "train_cities_marked_holdout": train_city_as_holdout,
        "ok": not leaked and not holdout_in_train and not train_city_as_holdout,
    }


def assert_no_leakage(segments: List[StreetSegment]):
    report = leakage_report(segments)
    if not report["ok"]:
        raise ValidationFailed("spatial leakage detected: {0}".format(report))
    return report
