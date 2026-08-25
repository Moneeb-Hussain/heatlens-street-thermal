from __future__ import annotations

import argparse
import json
import sys

from heatlens.config import load_settings
from heatlens.domain.cities import CITIES, get_city
from heatlens.errors import HeatLensError
from heatlens.ingest.grid import GRID_SPACING_M, iter_city_grid


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="HeatLens dataset build (grid + coverage counts).")
    parser.add_argument("--city", help="Single city id. Default: all study cities.")
    parser.add_argument("--spacing-m", type=float, default=GRID_SPACING_M)
    parser.add_argument("--json", action="store_true", help="Print machine-readable counts.")
    args = parser.parse_args(argv)

    settings = load_settings()
    cities = [get_city(args.city)] if args.city else list(CITIES)
    report = []
    for city in cities:
        count = sum(1 for _ in iter_city_grid(city, args.spacing_m))
        report.append(
            {
                "city": city.id,
                "role": city.role,
                "grid_points": count,
                "spacing_m": args.spacing_m,
                "coverage_validated": city.coverage_validated,
                "mapillary_configured": settings.has_mapillary(),
                "fortyguard_configured": settings.has_fortyguard(),
            }
        )

    if args.json:
        json.dump({"cities": report}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for row in report:
            sys.stdout.write(
                "{city:10}  role={role:8}  grid={grid_points:6d}  "
                "mapillary={mapillary_configured}  fortyguard={fortyguard_configured}\n".format(**row)
            )
        if not settings.has_mapillary() or not settings.has_fortyguard():
            sys.stdout.write(
                "\nKeys missing. Grid counts only — image pull and labelling "
                "require MAPILLARY_ACCESS_TOKEN and FORTYGUARD_API_KEY.\n"
            )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
