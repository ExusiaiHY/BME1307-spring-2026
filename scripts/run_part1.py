"""End-to-end Part 1 runner for carotid segmentation and quantification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from carotid_py.config import PART1_IMAGES_DIR, PART1_METADATA_FILE, PART1_TEMPLATE_FILE, Part1Paths
from carotid_py.data import crop_to_bbox, iter_samples, load_metadata, place_mask, resolve_search_bbox
from carotid_py.quantify import LITERATURE_DIAMETER_RANGE_MM, quantify_mask
from carotid_py.segmentation import overlay, segment_auto


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=PART1_METADATA_FILE, help="CSV metadata file for Part 1 samples.")
    parser.add_argument("--images-dir", type=Path, default=PART1_IMAGES_DIR, help="Directory containing Part 1 image files.")
    parser.add_argument("--save-masks", action="store_true", help="Write binary masks to outputs/part1/masks.")
    parser.add_argument("--save-overlays", action="store_true", help="Write segmentation overlays to outputs/part1/overlays.")
    return parser.parse_args(argv)


def _build_report(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    diameter = pd.to_numeric(df["diameter_used_mm"], errors="coerce")
    out = {
        "n_samples": int(len(df)),
        "n_with_metadata_roi": int((df["roi_source"] == "metadata_roi").sum()),
        "n_without_metadata_roi": int((df["roi_source"] != "metadata_roi").sum()),
        "n_with_physical_scale": int(df["pixel_spacing_mean_mm"].notna().sum()),
        "n_in_literature_range": int(pd.Series(df["diameter_in_literature_range"]).fillna(False).sum()),
        "literature_diameter_range_mm": list(LITERATURE_DIAMETER_RANGE_MM),
        "mean_diameter_used_mm": float(diameter.mean()) if diameter.notna().any() else None,
        "median_diameter_used_mm": float(diameter.median()) if diameter.notna().any() else None,
        "strategies": df["segmentation_strategy"].value_counts().to_dict(),
        "modalities": df["modality"].value_counts().to_dict(),
        "per_sample": rows,
    }
    return out


def main(args: argparse.Namespace) -> None:
    paths = Part1Paths()
    paths.ensure()

    metadata = load_metadata(metadata_file=args.metadata, images_dir=args.images_dir)
    print(
        f"[data] loaded {len(metadata)} Part 1 sample(s) from {args.metadata} "
        f"(template: {PART1_TEMPLATE_FILE})"
    )

    rows: list[dict] = []
    for sample in iter_samples(metadata):
        bbox = resolve_search_bbox(sample.metadata, sample.image_bgr.shape[:2], sample.modality)
        x0, y0, x1, y1, roi_source = bbox
        crop = crop_to_bbox(sample.image_bgr, (x0, y0, x1, y1))

        mask_crop, seg_meta = segment_auto(crop, modality=sample.modality)
        mask_full = place_mask(mask_crop, sample.image_bgr.shape[:2], (x0, y0, x1, y1))
        overlay_full = overlay(sample.image_bgr, mask_full)

        quant = quantify_mask(mask_crop, sample.metadata)
        row = {
            "sample_id": sample.sample_id,
            "file_name": sample.path.name,
            "path": str(sample.path),
            "modality": sample.modality,
            "roi_source": roi_source,
            "roi_x0": x0,
            "roi_y0": y0,
            "roi_x1": x1,
            "roi_y1": y1,
            "segmentation_strategy": seg_meta.strategy,
            "segmentation_fallback": seg_meta.fallback,
            "foreground_ratio": seg_meta.foreground_ratio,
            "centroid_offset": seg_meta.centroid_offset,
            **{k: sample.metadata.get(k) for k in sample.metadata.keys() if k not in {"path", "sample_id", "file_name", "modality"}},
            **quant,
            "segmentation_extras": json.dumps(seg_meta.extras, ensure_ascii=True),
        }
        rows.append(row)

        if args.save_masks:
            cv2.imwrite(str(paths.masks / f"{sample.sample_id}_mask.png"), mask_full.astype(np.uint8) * 255)
        if args.save_overlays:
            cv2.imwrite(str(paths.overlays / f"{sample.sample_id}_overlay.png"), overlay_full)

        print(
            f"[sample] id={sample.sample_id:>8s} modality={sample.modality:13s} "
            f"strategy={seg_meta.strategy:22s} roi={roi_source:18s} "
            f"diameter_mm={row['diameter_used_mm'] if row['diameter_used_mm'] is not None else 'NA'}"
        )

    df = pd.DataFrame(rows)
    df.to_csv(paths.measurements, index=False)
    report = _build_report(rows)
    paths.report.write_text(json.dumps(report, indent=2))
    print(f"[outputs] wrote {paths.measurements} and {paths.report}")


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
