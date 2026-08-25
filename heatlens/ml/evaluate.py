"""Score predictions against labels. Does not invent a model."""

from __future__ import annotations

import argparse
import csv
import json
import sys

from heatlens.config import load_settings
from heatlens.errors import HeatLensError, ValidationFailed
from heatlens.ml.metrics import mae, r_squared, spearman_rho, top_decile_precision
from heatlens.store import load_labels_csv


def score(y_true, y_pred):
    return {
        "n": len(y_true),
        "mae_c": round(mae(y_true, y_pred), 4),
        "r_squared": round(r_squared(y_true, y_pred), 4),
        "spearman_rho": round(spearman_rho(y_true, y_pred), 4),
        "top_decile_precision": round(top_decile_precision(y_true, y_pred), 4),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate predicted delta_t against labels.")
    parser.add_argument("--predictions", required=True, help="CSV with image_id,y_pred")
    args = parser.parse_args(argv)
    settings = load_settings()
    labels = {row.image_id: row.delta_t for row in load_labels_csv(settings.labels_path)}
    y_true = []
    y_pred = []
    with open(args.predictions, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "image_id" not in reader.fieldnames or "y_pred" not in reader.fieldnames:
            raise ValidationFailed("predictions CSV must have image_id and y_pred")
        for row in reader:
            if row["image_id"] not in labels:
                raise ValidationFailed("unknown image_id {0}".format(row["image_id"]))
            y_true.append(labels[row["image_id"]])
            y_pred.append(float(row["y_pred"]))
    json.dump(score(y_true, y_pred), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
