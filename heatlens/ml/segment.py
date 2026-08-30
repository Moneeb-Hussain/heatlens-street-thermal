"""Fill canopy/asphalt/sky/building fractions from SegFormer (ADE20K).

Does not invent temperatures. Fractions come from a real semantic mask.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from heatlens.errors import CapabilityUnavailable, HeatLensError, ValidationFailed
from heatlens.ml.fractions import fractions_from_class_ids

SEGFORMER_ID = "nvidia/segformer-b0-finetuned-ade-512-512"
FRACTION_COLS = ("canopy_frac", "asphalt_frac", "sky_frac", "building_frac")


def _has_fractions(row) -> bool:
    try:
        for col in FRACTION_COLS:
            raw = row.get(col)
            if raw is None or raw == "":
                return False
            value = float(raw)
            if value < 0.0 or value > 1.0:
                return False
    except (TypeError, ValueError):
        return False
    return True


def _photo_path(photos_dir: Path, image_id: str) -> Path:
    for suffix in (".jpg", ".jpeg", ".png"):
        path = photos_dir / (image_id + suffix)
        if path.is_file():
            return path
    raise ValidationFailed("no photo for image_id {0} in {1}".format(image_id, photos_dir))


def _load_segformer(device):
    try:
        import torch
        from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    except ImportError as exc:
        raise CapabilityUnavailable(
            "SEGMENTER_NOT_AVAILABLE",
            "Install the ML extra first: pip install -e '.[ml]'",
        ) from exc
    processor = SegformerImageProcessor.from_pretrained(SEGFORMER_ID)
    model = SegformerForSemanticSegmentation.from_pretrained(SEGFORMER_ID)
    model.to(device)
    model.eval()
    return torch, processor, model


def _pick_device():
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def segment_image(path: Path, torch, processor, model, device) -> dict:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {key: value.to(device) for key, value in inputs.items()}
    with torch.no_grad():
        logits = model(**inputs).logits
    pred = logits.argmax(dim=1)[0].detach().cpu().reshape(-1).tolist()
    return fractions_from_class_ids(pred)


def fill_fractions(labels_path: Path, photos_dir: Path, out_path: Path, limit=None, skip_existing=True):
    with labels_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValidationFailed("labels CSV has no header")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    for col in FRACTION_COLS:
        if col not in fieldnames:
            fieldnames.append(col)

    todo = []
    for index, row in enumerate(rows):
        if skip_existing and _has_fractions(row):
            continue
        todo.append(index)
        if limit is not None and len(todo) >= limit:
            break
    if not todo:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return {"updated": 0, "n": len(rows), "out": str(out_path)}

    device = _pick_device()
    torch, processor, model = _load_segformer(device)
    updated = 0
    for step, index in enumerate(todo, start=1):
        row = rows[index]
        image_id = (row.get("image_id") or "").strip()
        if not image_id:
            raise ValidationFailed("row {0} has no image_id".format(index))
        path = _photo_path(photos_dir, image_id)
        fracs = segment_image(path, torch, processor, model, device)
        row.update(fracs)
        updated += 1
        sys.stderr.write(
            "[{0}/{1}] {2} canopy={3} asphalt={4} sky={5} building={6}\n".format(
                step,
                len(todo),
                image_id,
                fracs["canopy_frac"],
                fracs["asphalt_frac"],
                fracs["sky_frac"],
                fracs["building_frac"],
            )
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {"updated": updated, "n": len(rows), "out": str(out_path), "device": device}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Extract urban-form fractions from street images.")
    parser.add_argument("--labels", required=True, help="Teammate labels.csv (delta_t filled).")
    parser.add_argument("--photos", required=True, help="Folder of {image_id}.jpg files.")
    parser.add_argument("--out", default="data/labels.csv")
    parser.add_argument("--limit", type=int, default=None, help="Only segment this many photos (smoke test).")
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-segment rows that already have fractions.",
    )
    args = parser.parse_args(argv)
    report = fill_fractions(
        Path(args.labels),
        Path(args.photos),
        Path(args.out),
        limit=args.limit,
        skip_existing=not args.no_skip_existing,
    )
    sys.stdout.write(
        "updated {updated}/{n}  wrote {out}\n".format(**report)
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HeatLensError as exc:
        sys.stderr.write("{0}: {1}\n".format(exc.code, exc))
        raise SystemExit(2)
