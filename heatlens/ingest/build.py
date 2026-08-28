from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from heatlens.config import load_settings
from heatlens.domain.cities import CITIES, get_city
from heatlens.errors import CapabilityUnavailable, HeatLensError, UpstreamError, ValidationFailed
from heatlens.ingest.grid import GRID_SPACING_M, iter_city_grid
from heatlens.store import LABEL_COLUMNS

# ingest/imagery.py and ingest/fortyguard.py live at the repo root, not inside
# the installed `heatlens` package, so make sure they're importable no matter
# how this module was invoked (python -m, the heatlens-ingest console script,
# or pytest).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="HeatLens dataset build (grid counts, or full photo+label pull).")
    parser.add_argument("--city", help="Single city id. Default: all study cities.")
    parser.add_argument("--spacing-m", type=float, default=GRID_SPACING_M)
    parser.add_argument("--json", action="store_true", help="Print machine-readable output.")
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Download photos + pull FortyGuard labels and append to data/labels.csv "
        "(needs MAPILLARY_ACCESS_TOKEN; FORTYGUARD_API_KEY for delta_t on US cities).",
    )
    parser.add_argument("--limit", type=int, default=None, help="Cap grid points visited per city (for a quick test run).")
    parser.add_argument(
        "--backfill-delta-t",
        action="store_true",
        help="Don't re-download anything -- just fill in delta_t for existing data/labels.csv "
        "rows that don't have it yet (e.g. photos pulled before a FortyGuard key was available "
        "for that city's state). Needs FORTYGUARD_API_KEY_<CITY_ID> (or FORTYGUARD_API_KEY) set "
        "for each city with rows to backfill.",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    cities = [get_city(args.city)] if args.city else list(CITIES)

    if args.backfill_delta_t:
        return _backfill_delta_t(cities, settings)

    if args.pull:
        return _pull(cities, settings, args)

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


def _backfill_delta_t(cities, settings) -> int:
    from ingest.fortyguard import default_heatmap_date, delta_t_for_point, fetch_city_heatmap
    from heatlens.clients.cache import ResponseCache
    from heatlens.clients.fortyguard import FortyGuardClient

    labels_path = settings.labels_path
    if not labels_path.is_file():
        sys.stderr.write("{0} doesn't exist yet -- run --pull first.\n".format(labels_path))
        return 2

    with labels_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)

    wanted_city_ids = {c.id for c in cities}
    cache = ResponseCache(settings.cache_path)
    summary = []
    try:
        for city in cities:
            if city.id not in wanted_city_ids or city.role not in ("train", "holdout"):
                continue
            fg_key = settings.fortyguard_api_key_for(city.id)
            if fg_key is None:
                sys.stderr.write(
                    "{0}: no FortyGuard key configured (FORTYGUARD_API_KEY_{1}) -- skipping.\n".format(
                        city.id, city.id.upper()
                    )
                )
                continue
            city_rows = [r for r in rows if r.get("city") == city.id and not (r.get("delta_t") or "").strip()]
            if not city_rows:
                continue
            fortyguard = FortyGuardClient(fg_key, settings.fortyguard_base_url, cache=cache)
            try:
                query_date = default_heatmap_date()
                heatmap_result, city_mean = fetch_city_heatmap(city, fortyguard, start_date=query_date, start_time="14:00")
            except (CapabilityUnavailable, UpstreamError, ValidationFailed) as exc:
                sys.stderr.write("{0}: FortyGuard heatmap unavailable ({1}) -- skipping.\n".format(city.id, exc))
                fortyguard.close()
                continue
            filled = 0
            failed = 0
            for row in city_rows:
                try:
                    row["delta_t"] = delta_t_for_point(heatmap_result, city_mean, float(row["lat"]), float(row["lon"]))
                    row["t_ref_window"] = "14:00"
                    row["source"] = "mapillary+fortyguard"
                    row["validated"] = True
                    filled += 1
                except UpstreamError as exc:
                    sys.stderr.write("{0}: {1}\n".format(row.get("image_id"), exc))
                    failed += 1
            fortyguard.close()
            summary.append({"city": city.id, "filled": filled, "failed": failed, "candidates": len(city_rows)})
    finally:
        cache.close()

    with labels_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    for row in summary:
        sys.stdout.write(
            "{city:10}  filled={filled:4d}/{candidates:<4d}  failed={failed:4d}\n".format(**row)
        )
    sys.stdout.write("\nUpdated {0}\n".format(labels_path))
    return 0


def _pull(cities, settings, args) -> int:
    from ingest.fortyguard import default_heatmap_date, delta_t_for_point, fetch_city_heatmap
    from ingest.imagery import download_city_photos
    from heatlens.clients.cache import ResponseCache
    from heatlens.clients.mapillary import MapillaryClient

    if not settings.has_mapillary():
        sys.stderr.write("MAPILLARY_ACCESS_TOKEN is not set — cannot pull photos. Add it to .env first.\n")
        return 2

    cache = ResponseCache(settings.cache_path)
    mapillary = MapillaryClient(settings.mapillary_access_token, cache=cache)
    # FortyGuard locks one account to one US state (confirmed by their support
    # 2026-08-27) -- so we can't share one client across cities in different
    # states. _pull_city builds its own client per city, using
    # FORTYGUARD_API_KEY_<CITY_ID> if set, falling back to FORTYGUARD_API_KEY.

    labels_path = settings.labels_path
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not labels_path.exists() or labels_path.stat().st_size == 0
    existing_ids = _existing_image_ids(labels_path)

    summary = []
    try:
        with labels_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(LABEL_COLUMNS) + ["source", "validated"])
            if write_header:
                writer.writeheader()
            for city in cities:
                summary.append(
                    _pull_city(
                        city,
                        mapillary,
                        cache,
                        settings,
                        args,
                        writer,
                        existing_ids,
                        delta_t_for_point,
                        fetch_city_heatmap,
                        download_city_photos,
                    )
                )
    finally:
        mapillary.close()
        cache.close()

    if args.json:
        json.dump({"cities": summary}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for row in summary:
            sys.stdout.write(
                "{city:10}  photos_kept={photos_kept:4d}  labelled={labelled:4d}  "
                "skipped={skipped:4d}\n".format(**row)
            )
        sys.stdout.write("\nWrote/updated {0}\n".format(labels_path))
    return 0


def _existing_image_ids(labels_path: Path):
    if not labels_path.exists():
        return set()
    ids = set()
    with labels_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("image_id"):
                ids.add(row["image_id"])
    return ids


def _assign_split(city, block_id):
    """Deterministic 85/15 split at the 1km-block level so a block never
    appears in both train and test — see heatlens/ml/splits.py leakage check.
    Miami (holdout role) is always 'holdout_city', never trained on.
    """
    if city.role == "holdout":
        return "holdout_city"
    digest = hashlib.sha1(block_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:4], 16) % 100
    return "train" if bucket < 85 else "test"


def _pull_city(
    city,
    mapillary,
    cache,
    settings,
    args,
    writer,
    existing_ids,
    delta_t_for_point,
    fetch_city_heatmap,
    download_city_photos,
):
    from heatlens.clients.fortyguard import FortyGuardClient

    raw_dir = settings.data_dir / "raw" / city.id
    heatmap_result = None
    city_mean = None
    # FortyGuard is US coverage only — never attempt (or fabricate) delta_t
    # for the transfer cities (Karachi/Lahore). README: mark them unvalidated.
    fortyguard = None
    fg_key = settings.fortyguard_api_key_for(city.id)
    has_fg = fg_key is not None and city.role in ("train", "holdout")
    if has_fg:
        fortyguard = FortyGuardClient(fg_key, settings.fortyguard_base_url, cache=cache)
        query_date = default_heatmap_date()
        try:
            heatmap_result, city_mean = fetch_city_heatmap(city, fortyguard, start_date=query_date, start_time="14:00")
        except (CapabilityUnavailable, UpstreamError, ValidationFailed) as exc:
            # ValidationFailed included: covers FortyGuard's response not matching
            # our assumed shape (city_mean_from_stats / tile parsing), which we've
            # now confirmed happens against the real API. Don't let a parsing
            # problem block the whole photo pull -- fall back to photos-only.
            sys.stderr.write("{0}: FortyGuard heatmap unavailable ({1}) — labels will skip delta_t.\n".format(city.id, exc))
            has_fg = False
    elif fg_key is None and city.role in ("train", "holdout"):
        sys.stderr.write(
            "{0}: no FortyGuard key configured (set FORTYGUARD_API_KEY_{1} in .env for this city's state) "
            "— will download photos but skip delta_t.\n".format(city.id, city.id.upper())
        )

    photos_kept = 0
    labelled = 0
    skipped = 0
    for result in download_city_photos(city, mapillary, raw_dir, spacing_m=args.spacing_m, limit=args.limit):
        if not result.accepted:
            skipped += 1
            continue
        image_id = str(result.image["id"])
        if image_id in existing_ids:
            continue
        photos_kept += 1
        row = {
            "image_id": image_id,
            "lat": result.lat,
            "lon": result.lon,
            "city": city.id,
            "block_id": result.block_id,
            "captured_at": result.image.get("captured_at"),
            "compass_angle": result.image.get("compass_angle"),
            "quality_score": result.image.get("quality_score"),
            "delta_t": "",
            "t_ref_window": "",
            # AI person fills these in from SegFormer — see README.
            "canopy_frac": "",
            "asphalt_frac": "",
            "sky_frac": "",
            "building_frac": "",
            "split": _assign_split(city, result.block_id),
            "source": "mapillary+fortyguard" if has_fg else "mapillary",
            "validated": bool(has_fg),
        }
        if has_fg:
            try:
                row["delta_t"] = delta_t_for_point(heatmap_result, city_mean, result.lat, result.lon)
                row["t_ref_window"] = "14:00"
                labelled += 1
            except UpstreamError as exc:
                sys.stderr.write("{0}: {1}\n".format(image_id, exc))
                row["validated"] = False
        writer.writerow(row)
        existing_ids.add(image_id)

    if fortyguard is not None:
        fortyguard.close()

    return {"city": city.id, "photos_kept": photos_kept, "labelled": labelled, "skipped": skipped}


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
