"""HTTP-free tool functions for the MCP / agent layer."""

from __future__ import annotations

from typing import Optional

from heatlens.config import Settings
from heatlens.domain.cities import CITIES, require_city
from heatlens.services.recommend import rank_interventions
from heatlens.store import JsonSegmentStore, load_coefficients

TOOLS = (
    {
        "name": "list_cities",
        "description": "List HeatLens study cities and their train/holdout/transfer role.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_segments",
        "description": "List street segments for a city with predicted or labelled delta_t.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
    {
        "name": "rank_interventions",
        "description": "Rank streets by indicative cooling from extra canopy. Requires fitted coefficients.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                "target_canopy_frac": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["city"],
        },
    },
)


def dispatch(name, arguments=None, settings: Optional[Settings] = None):
    args = arguments or {}
    settings = settings or Settings()
    if name == "list_cities":
        return {
            "cities": [
                {"id": city.id, "name": city.name, "role": city.role, "validated": city.coverage_validated}
                for city in CITIES
            ]
        }
    if name == "list_segments":
        city = require_city(args.get("city"))
        store = JsonSegmentStore(settings.segments_path)
        segments = store.list_segments(city.id)
        return {"city": city.id, "count": len(segments), "segments": [item.as_dict() for item in segments]}
    if name == "rank_interventions":
        city = require_city(args.get("city"))
        coefficients = load_coefficients(settings.coefficients_path)
        store = JsonSegmentStore(settings.segments_path)
        items = rank_interventions(
            store.list_segments(city.id),
            coefficients,
            args.get("target_canopy_frac"),
            limit=int(args.get("limit") or 50),
        )
        return {
            "city": city.id,
            "indicative": True,
            "items": [
                {
                    "image_id": item.image_id,
                    "estimated_cooling_c": item.estimated_cooling_c,
                    "current_canopy_frac": item.current_canopy_frac,
                    "validated": item.validated,
                }
                for item in items
            ],
        }
    raise ValueError("unknown tool {0}".format(name))
