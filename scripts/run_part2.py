"""End-to-end runner for Part 2.

Data → segmentation strategies → features → 3 classifiers × 5-fold CV →
metrics.csv + ROC plots + segmentation report.
"""

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

from busat_py.classify import make_models
from busat_py.config import BUSAT_MASKS_DIR, RunPaths
from busat_py.data import basic_stats, iter_images, load_labels
from busat_py.evaluate import cross_validate_model, plot_roc
from busat_py.features import extract_all
from busat_py.segmentation import SEGMENTERS, SegmentMeta, summarize_mask


DEFAULT_STRATEGIES = ("full", "cv", "refined")
ALL_STRATEGIES = (*DEFAULT_STRATEGIES, "busat")


def _load_busat_mask(image_id: int, image_shape: tuple[int, int], masks_dir: Path):
    mask_path = masks_dir / f"{image_id}_mask.png"
    mask_img = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask_img is None:
        raise FileNotFoundError(
            f"BUSAT mask missing for image_id={image_id}: expected {mask_path}"
        )
    mh, mw = mask_img.shape[:2]
    ih, iw = image_shape
    # BUSAT's autosegment crops the image to a multiple of its lattice window
    # (16 px) before segmenting, so the returned mask is up to 15 px shorter in
    # each axis. Pad the top-left-aligned mask back to the original shape.
    if mh > ih or mw > iw:
        raise ValueError(
            f"BUSAT mask larger than image for id={image_id}: "
            f"mask={mask_img.shape[:2]} image={image_shape}"
        )
    padded = np.zeros((ih, iw), dtype=bool)
    padded[:mh, :mw] = mask_img > 0
    return padded, summarize_mask("busat", padded, extras={
        "source": mask_path.name,
        "mask_shape": [int(mh), int(mw)],
        "image_shape": [int(ih), int(iw)],
    })


def build_feature_tables(
    save_masks: bool,
    paths: RunPaths,
    strategies: list[str],
    busat_masks_dir: Path,
):
    labels = load_labels()
    stats = basic_stats(labels)
    print(f"[data] loaded {stats['n']} samples ({stats['positive']}P / {stats['negative']}N)")

    rows_by_strategy = {strategy: [] for strategy in strategies}
    meta_by_strategy = {strategy: [] for strategy in strategies}

    for sample in iter_images(labels):
        base = {"image_id": sample.image_id, "label": sample.label}
        for strategy in strategies:
            if strategy == "busat":
                mask, meta = _load_busat_mask(
                    image_id=sample.image_id,
                    image_shape=sample.image_bgr.shape[:2],
                    masks_dir=busat_masks_dir,
                )
            else:
                mask, meta = SEGMENTERS[strategy](sample.image_bgr)

            rows_by_strategy[strategy].append({**base, **extract_all(sample.image_bgr, mask)})
            meta_by_strategy[strategy].append({
                "image_id": sample.image_id,
                "label": sample.label,
                "strategy": meta.strategy,
                "fallback": meta.fallback,
                "foreground_ratio": meta.foreground_ratio,
                "centroid_offset": meta.centroid_offset,
                "extras": meta.extras,
            })

            if save_masks:
                out = (mask.astype(np.uint8) * 255)
                cv2.imwrite(str(paths.masks / f"{sample.image_id}_{strategy}_mask.png"), out)

    dfs = {}
    for strategy, rows in rows_by_strategy.items():
        df = pd.DataFrame(rows)
        df.to_csv(paths.feature_table(strategy), index=False)
        dfs[strategy] = df
        print(f"[features] wrote {paths.feature_table(strategy).name} ({df.shape})")

    report = {
        "strategies": {
            strategy: _segmentation_report(records)
            for strategy, records in meta_by_strategy.items()
        }
    }
    paths.segmentation_report.write_text(json.dumps(report, indent=2))
    for strategy, summary in report["strategies"].items():
        print(
            f"[segmentation] strategy={strategy:7s} "
            f"fallback_count={summary['fallback_count']} / {summary['n']} "
            f"mean_fg_ratio={summary['mean_foreground_ratio']:.3f}"
        )

    return dfs


def _segmentation_report(meta_records):
    n = len(meta_records)
    fallback = sum(1 for r in meta_records if r["fallback"])
    ratios = np.array([r["foreground_ratio"] for r in meta_records], dtype=float)
    offsets = np.array([r["centroid_offset"] for r in meta_records], dtype=float)
    return {
        "n": n,
        "fallback_count": int(fallback),
        "mean_foreground_ratio": float(np.nanmean(ratios)),
        "median_foreground_ratio": float(np.nanmedian(ratios)),
        "min_foreground_ratio": float(np.nanmin(ratios)),
        "max_foreground_ratio": float(np.nanmax(ratios)),
        "mean_centroid_offset": float(np.nanmean(offsets)),
        "per_image": meta_records,
    }


def evaluate_table(df: pd.DataFrame, mask_name: str, paths: RunPaths):
    feature_cols = [c for c in df.columns if c not in ("image_id", "label")]
    X = df[feature_cols].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy(dtype=int)

    models = make_models()
    summaries = []
    for model_name, pipeline in models.items():
        summary, folds = cross_validate_model(X, y, pipeline)
        summaries.append({"mask": mask_name, "model": model_name, **summary})

        title = f"ROC — mask={mask_name} model={model_name}"
        plot_roc(folds, title, paths.outputs / f"roc_{mask_name}_{model_name}.png")

        print(f"[cv] mask={mask_name:4s} model={model_name:6s} "
              f"acc={summary['accuracy_mean']:.3f}±{summary['accuracy_std']:.3f} "
              f"sens={summary['sensitivity_mean']:.3f} "
              f"spec={summary['specificity_mean']:.3f} "
              f"auc={summary['auc_mean']:.3f}±{summary['auc_std']:.3f}")

    return summaries


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save-masks",
        action="store_true",
        help="Save binary masks for each requested strategy under outputs/part2/masks/.",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(DEFAULT_STRATEGIES),
        choices=list(ALL_STRATEGIES),
        help="Segmentation strategies to evaluate.",
    )
    parser.add_argument(
        "--busat-masks-dir",
        type=Path,
        default=BUSAT_MASKS_DIR,
        help="Directory containing pre-exported BUSAT mask PNG files named <image_id>_mask.png.",
    )
    return parser.parse_args(argv)


def main(save_masks: bool = False, strategies: list[str] | None = None, busat_masks_dir: Path = BUSAT_MASKS_DIR) -> None:
    paths = RunPaths()
    paths.ensure()
    strategies = strategies or list(DEFAULT_STRATEGIES)

    dfs = build_feature_tables(
        save_masks=save_masks,
        paths=paths,
        strategies=strategies,
        busat_masks_dir=busat_masks_dir,
    )

    rows = []
    for strategy, df in dfs.items():
        rows.extend(evaluate_table(df, mask_name=strategy, paths=paths))

    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(paths.metrics, index=False)
    print(f"[metrics] wrote {paths.metrics}")


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(
        save_masks=args.save_masks,
        strategies=args.strategies,
        busat_masks_dir=args.busat_masks_dir,
    )
