"""Fit the B1 linear model: delta_t from SegFormer urban-form fractions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from heatlens.config import load_settings
from heatlens.errors import CapabilityUnavailable, HeatLensError, ValidationFailed
from heatlens.ml.linear import LinearFeatureRegressor
from heatlens.ml.metrics import mae, r_squared, spearman_rho, top_decile_precision
from heatlens.ml.ols import fit_delta_t_coefficients
from heatlens.ml.splits import assert_no_leakage
from heatlens.store import JsonSegmentStore, load_labels_csv, write_coefficients


def inspect_dataset(segments):
    report = assert_no_leakage(segments)
    report["n"] = len(segments)
    report["by_city"] = dict(Counter(item.city for item in segments))
    report["by_split"] = dict(Counter(item.split for item in segments))
    return report


def _score_split(model, rows):
    if not rows:
        return None
    y_true = [item.delta_t for item in rows]
    y_pred = [model.predict_delta_t(item.features) for item in rows]
    return {
        "n": len(rows),
        "mae_c": round(mae(y_true, y_pred), 4),
        "r_squared": round(r_squared(y_true, y_pred), 4),
        "spearman_rho": round(spearman_rho(y_true, y_pred), 4),
        "top_decile_precision": round(top_decile_precision(y_true, y_pred), 4),
    }


def fit_linear(segments, coefficients_path: Path, segments_path=None):
    train_rows = [item for item in segments if item.split == "train"]
    test_rows = [item for item in segments if item.split == "test"]
    if len(train_rows) < 5:
        raise ValidationFailed("need at least 5 train rows with fractions + delta_t")
    train_dicts = []
    for item in train_rows:
        row = item.as_dict()
        row["captured_at"] = item.captured_at
        train_dicts.append(row)
    coefficients = fit_delta_t_coefficients(train_dicts)
    model = LinearFeatureRegressor(coefficients)
    metrics = {
        "train": _score_split(model, train_rows),
        "test": _score_split(model, test_rows),
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "n_train": len(train_rows),
        "n_test": len(test_rows),
        "note": "B1: summer-weighted OLS; canopy from leaf-on residuals, clipped to <= 0.",
    }
    write_coefficients(coefficients_path, coefficients, extra={"metrics": metrics})
    if segments_path is not None:
        JsonSegmentStore(segments_path).write_segments(
            segments, generated_at=metrics["fitted_at"]
        )
    return coefficients, metrics


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fit HeatLens models from labelled street photos.")
    parser.add_argument("--dry-run", action="store_true", help="Validate labels only; do not train.")
    parser.add_argument("--fit-linear", action="store_true", help="Fit B1 linear delta_t model from fractions.")
    parser.add_argument("--labels", default=None, help="Override HEATLENS_LABELS_PATH.")
    parser.add_argument("--write-segments", action="store_true", help="Write data/segments.json for the map.")
    args = parser.parse_args(argv)
    settings = load_settings()
    labels_path = Path(args.labels) if args.labels else settings.labels_path
    try:
        segments = load_labels_csv(labels_path)
    except ValidationFailed as exc:
        raise CapabilityUnavailable(
            "LABELS_NOT_AVAILABLE",
            "{0}. Run: python -m heatlens.ml.segment --labels <csv> --photos <dir> --out data/labels.csv".format(exc),
        ) from exc
    report = inspect_dataset(segments)
    if args.dry_run and not args.fit_linear:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if args.fit_linear:
        coefficients, metrics = fit_linear(
            segments,
            settings.coefficients_path,
            settings.segments_path if args.write_segments else None,
        )
        payload = {"dataset": report, "coefficients": coefficients.__dict__, "metrics": metrics}
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        if coefficients.canopy > 0:
            sys.stderr.write(
                "warning: canopy coefficient is positive ({0:.3f}). "
                "More trees predicting hotter — winter photos vs summer labels can cause this.\n".format(
                    coefficients.canopy
                )
            )
        return 0
    raise CapabilityUnavailable(
        "TRAINING_DEPS_MISSING",
        "Dataset is valid ({0} rows). For hackathon B1 run --fit-linear. "
        "A vision ONNX regressor is not wired yet.".format(report["n"]),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
