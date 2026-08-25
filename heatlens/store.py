from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Optional, Protocol

from heatlens.domain.cities import require_city
from heatlens.domain.types import Coefficients, StreetSegment, UrbanFormFeatures
from heatlens.errors import CapabilityUnavailable, ValidationFailed

LABEL_COLUMNS = (
    "image_id",
    "lat",
    "lon",
    "city",
    "block_id",
    "captured_at",
    "compass_angle",
    "quality_score",
    "delta_t",
    "t_ref_window",
    "canopy_frac",
    "asphalt_frac",
    "sky_frac",
    "building_frac",
    "split",
)


class SegmentStore(Protocol):
    def list_segments(self, city_id: Optional[str] = None) -> List[StreetSegment]:
        ...


class JsonSegmentStore(object):
    def __init__(self, path: Path):
        self.path = path

    def list_segments(self, city_id: Optional[str] = None) -> List[StreetSegment]:
        if not self.path.is_file():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("segments", payload if isinstance(payload, list) else [])
        segments = [segment_from_dict(row) for row in rows]
        if city_id:
            city = require_city(city_id)
            return [item for item in segments if item.city == city.id]
        return segments

    def write_segments(self, segments: Iterable[StreetSegment], generated_at: Optional[str] = None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "version": 1,
            "generated_at": generated_at,
            "segments": [item.as_dict() for item in segments],
        }
        self.path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def segment_from_dict(row) -> StreetSegment:
    if not isinstance(row, dict):
        raise ValidationFailed("segment row must be an object")
    features = UrbanFormFeatures(
        canopy_frac=row["canopy_frac"],
        asphalt_frac=row["asphalt_frac"],
        sky_frac=row["sky_frac"],
        building_frac=row["building_frac"],
    )
    validated = bool(row.get("validated", row.get("source") == "fortyguard"))
    return StreetSegment(
        image_id=str(row["image_id"]),
        lat=row["lat"],
        lon=row["lon"],
        city=str(row["city"]).lower(),
        block_id=str(row.get("block_id") or ""),
        delta_t=row["delta_t"],
        features=features,
        split=str(row.get("split") or "train"),
        source=str(row.get("source") or "fortyguard"),
        validated=validated,
        captured_at=row.get("captured_at"),
        compass_angle=_opt_float(row.get("compass_angle")),
        quality_score=_opt_float(row.get("quality_score")),
        t_ref_window=row.get("t_ref_window"),
    )


def load_labels_csv(path: Path) -> List[StreetSegment]:
    if not path.is_file():
        raise CapabilityUnavailable("LABELS_NOT_AVAILABLE", "No labels file at {0}".format(path))
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [col for col in ("image_id", "lat", "lon", "city", "delta_t") if col not in (reader.fieldnames or [])]
        if missing:
            raise ValidationFailed("labels.csv missing columns: {0}".format(missing))
        return [segment_from_dict(_normalize_label(row)) for row in reader]


def write_labels_csv(path: Path, segments: Iterable[StreetSegment]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LABEL_COLUMNS) + ["source", "validated"])
        writer.writeheader()
        for segment in segments:
            row = segment.as_dict()
            writer.writerow({key: row.get(key, "") for key in writer.fieldnames})


def load_coefficients(path: Path) -> Coefficients:
    if not path.is_file():
        raise CapabilityUnavailable(
            "COEFFICIENTS_NOT_AVAILABLE",
            "No fitted coefficients at {0}. Run evaluation before ranking interventions.".format(path),
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = ("intercept", "canopy", "asphalt", "sky", "building")
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValidationFailed("coefficients.json missing keys: {0}".format(missing))
    return Coefficients(
        intercept=float(payload["intercept"]),
        canopy=float(payload["canopy"]),
        asphalt=float(payload["asphalt"]),
        sky=float(payload["sky"]),
        building=float(payload["building"]),
        target_canopy_frac=float(payload.get("target_canopy_frac", 0.40)),
    )


def _opt_float(value):
    if value is None or value == "":
        return None
    return float(value)


def _normalize_label(row):
    data = dict(row)
    data.setdefault("source", "fortyguard")
    data.setdefault("validated", True)
    data.setdefault("block_id", "")
    data.setdefault("split", "train")
    return data
