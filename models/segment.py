"""Segmentation runs only when a real backend is installed. This module does not invent fractions."""

from __future__ import annotations

import argparse
import sys

from heatlens.errors import CapabilityUnavailable, HeatLensError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract urban-form fractions from street images.")
    parser.parse_args(argv)
    raise CapabilityUnavailable(
        "SEGMENTER_NOT_AVAILABLE",
        "SegFormer (ADE20K) is not installed in this skeleton. "
        "Do not write placeholder canopy/asphalt fractions.",
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
