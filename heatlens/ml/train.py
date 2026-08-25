"""Validate labels and refuse to train without a real dataset + torch extra."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from heatlens.config import load_settings
from heatlens.errors import CapabilityUnavailable, HeatLensError
from heatlens.ml.splits import assert_no_leakage
from heatlens.store import load_labels_csv


def inspect_dataset(segments):
    report = assert_no_leakage(segments)
    report["n"] = len(segments)
    report["by_city"] = dict(Counter(item.city for item in segments))
    report["by_split"] = dict(Counter(item.split for item in segments))
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fine-tune the HeatLens vision regressor.")
    parser.add_argument("--dry-run", action="store_true", help="Validate labels only; do not train.")
    args = parser.parse_args(argv)
    settings = load_settings()
    segments = load_labels_csv(settings.labels_path)
    report = inspect_dataset(segments)
    json.dump(report, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if args.dry_run:
        return 0
    raise CapabilityUnavailable(
        "TRAINING_DEPS_MISSING",
        "Dataset is valid ({0} rows). Install torch/timm and add a trained artefact "
        "before running a full train loop. Use --dry-run to re-validate.".format(report["n"]),
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
