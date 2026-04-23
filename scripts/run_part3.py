"""Part 3 runner: SAM 2 prompted segmentation + CLIP embedding classification."""

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

from busat_py.data import iter_images as iter_part2_images
from busat_py.data import load_labels as load_part2_labels
from carotid_py.data import crop_to_bbox, place_mask, resolve_search_bbox
from carotid_py.data import iter_samples as iter_part1_samples
from carotid_py.data import load_metadata as load_part1_metadata
from carotid_py.quantify import LITERATURE_DIAMETER_RANGE_MM, quantify_mask
from part3_py.config import PART1_IMAGES_DIR, PART1_METADATA_FILE, Part3Paths
from part3_py.evaluate import (
    evaluate_embedding_table,
    evaluate_part2_baseline_table,
    plot_roc_comparison,
)
from part3_py.models import (
    configure_hf_cache,
    load_biomedclip_encoder,
    load_openclip_encoder,
    load_sam2_segmenter,
    resolve_device,
)
from part3_py.segmentation import (
    hough_carotid_prompt,
    image_center_prompt,
    Prompt,
    render_overlay,
    summarize_part2_sam2_mask,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", default="auto", help="torch device: auto / cpu / cuda / mps")
    parser.add_argument("--skip-segmentation", action="store_true", help="Skip SAM2 segmentation runs.")
    parser.add_argument("--skip-classification", action="store_true", help="Skip CLIP embedding classification.")
    parser.add_argument(
        "--skip-part2-overlays",
        action="store_true",
        help="Skip writing Part 2 overlay PNGs to save time and disk.",
    )
    parser.add_argument(
        "--part2-max-images",
        type=int,
        default=None,
        help="Optional cap for Part 2 SAM2 segmentation / embedding extraction during quick tests.",
    )
    parser.add_argument(
        "--comparison-strategies",
        nargs="+",
        default=["refined", "busat"],
        help="Existing Part 2 feature tables to include in ROC comparison plots.",
    )
    return parser.parse_args(argv)


def _part1_report(rows: list[dict]) -> dict:
    df = pd.DataFrame(rows)
    diameter = pd.to_numeric(df["diameter_used_mm"], errors="coerce")
    mask_score = pd.to_numeric(df["sam2_iou_score"], errors="coerce")
    return {
        "n_samples": int(len(df)),
        "prompt_sources": df["prompt_source"].value_counts().to_dict(),
        "mean_foreground_ratio": float(pd.to_numeric(df["foreground_ratio"], errors="coerce").mean()),
        "mean_sam2_iou_score": float(mask_score.mean()),
        "n_in_literature_range": int(pd.Series(df["diameter_in_literature_range"]).fillna(False).sum()),
        "literature_diameter_range_mm": list(LITERATURE_DIAMETER_RANGE_MM),
        "mean_diameter_used_mm": float(diameter.mean()) if diameter.notna().any() else None,
        "per_sample": rows,
    }


def run_part1_sam2(paths: Part3Paths, device: str) -> None:
    sam2 = load_sam2_segmenter(resolve_device(device), paths.hf_cache)
    metadata = load_part1_metadata(metadata_file=PART1_METADATA_FILE, images_dir=PART1_IMAGES_DIR)
    rows: list[dict] = []

    print(f"[part1] loaded {len(metadata)} sample(s) from {PART1_METADATA_FILE}")
    for sample in iter_part1_samples(metadata):
        prompt = hough_carotid_prompt(
            sample.image_bgr,
            pixel_spacing_mm=sample.metadata.get("pixel_spacing_mm"),
        )
        if prompt.source == "hough_circle":
            mask, sam_meta = sam2.segment_from_point(
                sample.image_bgr,
                prompt.xy,
                preferred_max_area_ratio=0.35,
                prefer_smallest=False,
            )
        else:
            bbox = resolve_search_bbox(sample.metadata, sample.image_bgr.shape[:2], sample.modality)
            x0, y0, x1, y1, roi_source = bbox
            crop = crop_to_bbox(sample.image_bgr, (x0, y0, x1, y1))
            prompt_crop = hough_carotid_prompt(
                crop,
                pixel_spacing_mm=sample.metadata.get("pixel_spacing_mm"),
            )
            mask_crop, sam_meta = sam2.segment_from_point(
                crop,
                prompt_crop.xy,
                preferred_max_area_ratio=0.20 if prompt_crop.source == "center_fallback" else 0.35,
                prefer_smallest=(prompt_crop.source == "center_fallback"),
            )
            mask = place_mask(mask_crop, sample.image_bgr.shape[:2], (x0, y0, x1, y1))
            prompt = Prompt(
                x=float(x0 + prompt_crop.x),
                y=float(y0 + prompt_crop.y),
                source=f"crop_{prompt_crop.source}",
                extras={
                    **prompt_crop.extras,
                    "roi_source": roi_source,
                    "roi_x0": int(x0),
                    "roi_y0": int(y0),
                    "roi_x1": int(x1),
                    "roi_y1": int(y1),
                },
            )
        prompt.extras["selected_iou_score"] = sam_meta["selected_iou_score"]

        overlay = render_overlay(sample.image_bgr, mask, prompt, title=sample.sample_id)
        cv2.imwrite(str(paths.part1_overlay(sample.sample_id)), overlay)

        quant = quantify_mask(mask, sample.metadata)
        row = {
            "sample_id": sample.sample_id,
            "file_name": sample.path.name,
            "path": str(sample.path),
            "modality": sample.modality,
            "prompt_x": float(prompt.x),
            "prompt_y": float(prompt.y),
            "prompt_source": prompt.source,
            "foreground_ratio": float(mask.astype(bool).mean()),
            "sam2_iou_score": float(sam_meta["selected_iou_score"]),
            "sam2_mask_index": int(sam_meta["selected_mask_index"]),
            **{k: sample.metadata.get(k) for k in sample.metadata.keys() if k != "path"},
            **quant,
            "prompt_extras": json.dumps(prompt.extras, ensure_ascii=True),
            "sam2_extras": json.dumps(sam_meta, ensure_ascii=True),
        }
        rows.append(row)
        print(
            f"[part1] sample={sample.sample_id:>22s} "
            f"prompt={prompt.source:15s} "
            f"iou={sam_meta['selected_iou_score']:.3f} "
            f"diameter_mm={row['diameter_used_mm'] if row['diameter_used_mm'] is not None else 'NA'}"
        )

    df = pd.DataFrame(rows)
    df.to_csv(paths.part1_measurements, index=False)
    report = _part1_report(rows)
    paths.part1_report.write_text(json.dumps(report, indent=2))
    print(f"[part1] wrote {paths.part1_measurements} and {paths.part1_report}")


def run_part2_sam2(paths: Part3Paths, device: str, max_images: int | None, save_overlays: bool) -> None:
    sam2 = load_sam2_segmenter(resolve_device(device), paths.hf_cache)
    labels = load_part2_labels()
    rows: list[dict] = []

    print(f"[part2-seg] loaded {len(labels)} sample(s)")
    iterator = iter_part2_images(labels)
    for idx, sample in enumerate(iterator):
        if max_images is not None and idx >= max_images:
            break

        prompt = image_center_prompt(sample.image_bgr.shape[:2])
        mask, sam_meta = sam2.segment_from_point(sample.image_bgr, prompt.xy)
        prompt.extras["selected_iou_score"] = sam_meta["selected_iou_score"]

        if save_overlays:
            overlay = render_overlay(
                sample.image_bgr,
                mask,
                prompt,
                title=f"id={sample.image_id} label={sample.label}",
            )
            cv2.imwrite(str(paths.part2_overlay(sample.image_id)), overlay)

        summary = summarize_part2_sam2_mask(mask)
        row = {
            "image_id": int(sample.image_id),
            "label": int(sample.label),
            "prompt_x": float(prompt.x),
            "prompt_y": float(prompt.y),
            "prompt_source": prompt.source,
            "foreground_ratio": float(summary["foreground_ratio"]),
            "centroid_offset": float(summary["centroid_offset"]),
            "sam2_iou_score": float(sam_meta["selected_iou_score"]),
            "sam2_mask_index": int(sam_meta["selected_mask_index"]),
            "prompt_extras": json.dumps(prompt.extras, ensure_ascii=True),
            "sam2_extras": json.dumps(sam_meta, ensure_ascii=True),
        }
        rows.append(row)
        if idx < 5 or (idx + 1) % 20 == 0:
            print(
                f"[part2-seg] image={sample.image_id:>3d} "
                f"label={sample.label} iou={sam_meta['selected_iou_score']:.3f} "
                f"fg={row['foreground_ratio']:.3f}"
            )

    df = pd.DataFrame(rows).sort_values("image_id").reset_index(drop=True)
    df.to_csv(paths.part2_segmentation_manifest, index=False)
    report = {
        "n_samples": int(len(df)),
        "mean_foreground_ratio": float(pd.to_numeric(df["foreground_ratio"], errors="coerce").mean()),
        "median_foreground_ratio": float(pd.to_numeric(df["foreground_ratio"], errors="coerce").median()),
        "mean_centroid_offset": float(pd.to_numeric(df["centroid_offset"], errors="coerce").mean()),
        "mean_sam2_iou_score": float(pd.to_numeric(df["sam2_iou_score"], errors="coerce").mean()),
        "label_counts": df["label"].value_counts().to_dict(),
        "prompt_sources": df["prompt_source"].value_counts().to_dict(),
    }
    paths.part2_segmentation_report.write_text(json.dumps(report, indent=2))
    print(f"[part2-seg] wrote {paths.part2_segmentation_manifest} and {paths.part2_segmentation_report}")


def _embedding_rows(samples, encoder) -> list[dict]:
    rows: list[dict] = []
    for idx, sample in enumerate(samples):
        emb = encoder.encode_image_bgr(sample.image_bgr)
        row = {
            "image_id": int(sample.image_id),
            "label": int(sample.label),
        }
        row.update({f"emb_{i:04d}": float(v) for i, v in enumerate(emb.tolist())})
        rows.append(row)
        if idx < 3 or (idx + 1) % 20 == 0:
            print(f"[embed] encoder={encoder.name:10s} image={sample.image_id:>3d}")
    return rows


def run_classification(paths: Part3Paths, device: str, max_images: int | None, comparison_strategies: list[str]) -> None:
    labels = load_part2_labels()
    samples = list(iter_part2_images(labels))
    if max_images is not None:
        samples = samples[:max_images]
    print(f"[classify] extracting embeddings for {len(samples)} sample(s)")

    encoders = [
        load_openclip_encoder(resolve_device(device), paths.hf_cache),
        load_biomedclip_encoder(resolve_device(device), paths.hf_cache),
    ]

    foundation_metric_rows: list[dict] = []
    foundation_folds: dict[str, dict[str, list]] = {}
    for encoder in encoders:
        rows = _embedding_rows(samples, encoder)
        df = pd.DataFrame(rows).sort_values("image_id").reset_index(drop=True)
        out_path = paths.embedding_table(encoder.name)
        df.to_csv(out_path, index=False)
        print(f"[classify] wrote {out_path} ({df.shape})")

        metric_rows, folds_by_model = evaluate_embedding_table(df, encoder.name, paths.roc_dir)
        foundation_metric_rows.extend(metric_rows)
        foundation_folds[encoder.name] = folds_by_model
        for row in metric_rows:
            print(
                f"[cv] source={row['experiment']:10s} model={row['model']:6s} "
                f"acc={row['accuracy_mean']:.3f}±{row['accuracy_std']:.3f} "
                f"auc={row['auc_mean']:.3f}±{row['auc_std']:.3f}"
            )

    foundation_df = pd.DataFrame(foundation_metric_rows)
    foundation_df.to_csv(paths.classification_metrics, index=False)

    baseline_rows: list[dict] = []
    baseline_folds: dict[str, dict[str, list]] = {}
    for strategy in comparison_strategies:
        feature_path = ROOT / "outputs" / "part2" / f"features_{strategy}.csv"
        if not feature_path.exists():
            raise FileNotFoundError(f"missing Part 2 feature table for comparison: {feature_path}")
        df = pd.read_csv(feature_path)
        rows, folds_by_model = evaluate_part2_baseline_table(df, strategy)
        baseline_rows.extend(rows)
        baseline_folds[strategy] = folds_by_model

    comparison_df = pd.concat(
        [
            pd.DataFrame(baseline_rows),
            foundation_df,
        ],
        ignore_index=True,
    )
    comparison_df.to_csv(paths.comparison_metrics, index=False)

    for model_name in ["logreg", "svm", "rf"]:
        curves = {}
        for strategy in comparison_strategies:
            curves[strategy] = baseline_folds[strategy][model_name]
        for encoder in encoders:
            curves[encoder.name] = foundation_folds[encoder.name][model_name]
        plot_roc_comparison(
            curves,
            title=f"ROC Comparison — model={model_name}",
            out_path=paths.comparison_roc_plot(model_name),
        )
    print(f"[classify] wrote {paths.classification_metrics} and {paths.comparison_metrics}")


def write_notes(paths: Part3Paths) -> None:
    note = (
        "Part 3 notes:\n"
        "- Segmentation uses the official SAM2 Hiera base-plus checkpoint via Hugging Face.\n"
        "- SAM2 does not ship an ultrasound-specialist checkpoint; note this explicitly in the report.\n"
        "- Classification uses image embeddings from OpenCLIP and BiomedCLIP on the Part 2 dataset.\n"
    )
    paths.note_file.write_text(note)


def main(args: argparse.Namespace) -> None:
    paths = Part3Paths()
    paths.ensure()
    configure_hf_cache(paths.hf_cache)
    print(f"[env] device={resolve_device(args.device)}")
    print(f"[env] outputs={paths.outputs}")

    if not args.skip_segmentation:
        run_part1_sam2(paths=paths, device=args.device)
        run_part2_sam2(
            paths=paths,
            device=args.device,
            max_images=args.part2_max_images,
            save_overlays=not args.skip_part2_overlays,
        )

    if not args.skip_classification:
        run_classification(
            paths=paths,
            device=args.device,
            max_images=args.part2_max_images,
            comparison_strategies=args.comparison_strategies,
        )

    write_notes(paths)


if __name__ == "__main__":
    main(parse_args(sys.argv[1:]))
