"""Merge per-city label CSVs, then fit one pooled B1 model.

Use after Chicago (or any city) fractions are filled. Does not invent
temperatures or fractions. Later files win on duplicate image_id.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from heatlens.config import load_settings
from heatlens.errors import HeatLensError, ValidationFailed
from heatlens.ml.segment import FRACTION_COLS, _has_fractions
from heatlens.ml.train import fit_linear, inspect_dataset
from heatlens.store import LABEL_COLUMNS, load_labels_csv


def merge_label_rows(paths):
    fieldnames = []
    by_id = {}
    for path in paths:
        with Path(path).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValidationFailed("{0} has no header".format(path))
            for col in reader.fieldnames:
                if col not in fieldnames:
                    fieldnames.append(col)
            for row in reader:
                image_id = (row.get("image_id") or "").strip()
                if not image_id:
                    raise ValidationFailed("{0} has a row with no image_id".format(path))
                by_id[image_id] = row
    for col in FRACTION_COLS:
        if col not in fieldnames:
            fieldnames.append(col)
    return fieldnames, list(by_id.values())


def write_filled_labels(path: Path, fieldnames, rows):
    filled = [row for row in rows if _has_fractions(row)]
    if not filled:
        raise ValidationFailed("no rows with canopy/asphalt/sky/building fractions")
    ordered = [col for col in list(LABEL_COLUMNS) + ["source", "validated"] if col in fieldnames]
    extra = [col for col in fieldnames if col not in ordered]
    out_fields = ordered + extra
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(filled)
    return filled


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Merge city label CSVs and fit one pooled linear model.")
    parser.add_argument(
        "--labels",
        action="append",
        required=True,
        help="Label CSV path. Repeat per city. Later files overwrite the same image_id.",
    )
    parser.add_argument("--out", default=None, help="Combined labels path. Default: HEATLENS_LABELS_PATH.")
    parser.add_argument("--fit-linear", action="store_true", help="Fit B1 on the merged rows.")
    parser.add_argument("--write-segments", action="store_true", help="Write data/segments.json for the map.")
    args = parser.parse_args(argv)

    settings = load_settings()
    out_path = Path(args.out) if args.out else settings.labels_path
    fieldnames, rows = merge_label_rows(args.labels)
    filled = write_filled_labels(out_path, fieldnames, rows)
    skipped = len(rows) - len(filled)
    sys.stderr.write(
        "merged {0} unique ids, wrote {1} filled rows to {2} (skipped {3} without fractions)\n".format(
            len(rows), len(filled), out_path, skipped
        )
    )

    segments = load_labels_csv(out_path)
    report = inspect_dataset(segments)
    if not args.fit_linear:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    coefficients, metrics = fit_linear(
        segments,
        settings.coefficients_path,
        settings.segments_path if args.write_segments else None,
    )
    payload = {"dataset": report, "coefficients": coefficients.__dict__, "metrics": metrics}
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
