"""End-to-end runner for Part 2 baseline.

Data → segmentation (full vs classical CV) → features → 3 classifiers × 5-fold
CV → metrics.csv + ROC plots + segmentation report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from busat_py.classify import make_models
from busat_py.config import RunPaths
from busat_py.data import basic_stats, iter_images, load_labels
from busat_py.evaluate import cross_validate_model, plot_roc
from busat_py.features import extract_all
from busat_py.segmentation import SegmentMeta, segment_cv, segment_full


def build_feature_tables(save_masks: bool, paths: RunPaths):
    labels = load_labels()
    stats = basic_stats(labels)
    print(f"[data] loaded {stats['n']} samples ({stats['positive']}P / {stats['negative']}N)")

    rows_full, rows_cv = [], []
    meta_records = []

    for sample in iter_images(labels):
        mask_full, _ = segment_full(sample.image_bgr)
        mask_cv, meta_cv = segment_cv(sample.image_bgr)

        base = {"image_id": sample.image_id, "label": sample.label}
        rows_full.append({**base, **extract_all(sample.image_bgr, mask_full)})
        rows_cv.append({**base, **extract_all(sample.image_bgr, mask_cv)})

        meta_records.append({
            "image_id": sample.image_id,
            "label": sample.label,
            "strategy": meta_cv.strategy,
            "fallback": meta_cv.fallback,
            "foreground_ratio": meta_cv.foreground_ratio,
            "centroid_offset": meta_cv.centroid_offset,
            "extras": meta_cv.extras,
        })

        if save_masks:
            out = (mask_cv.astype(np.uint8) * 255)
            cv2.imwrite(str(paths.masks / f"{sample.image_id}_mask.png"), out)

    df_full = pd.DataFrame(rows_full)
    df_cv = pd.DataFrame(rows_cv)
    df_full.to_csv(paths.features_full, index=False)
    df_cv.to_csv(paths.features_cv, index=False)
    print(f"[features] wrote {paths.features_full.name} ({df_full.shape}) and "
          f"{paths.features_cv.name} ({df_cv.shape})")

    report = _segmentation_report(meta_records)
    paths.segmentation_report.write_text(json.dumps(report, indent=2))
    print(f"[segmentation] fallback_count={report['fallback_count']} / {report['n']} "
          f"mean_fg_ratio={report['mean_foreground_ratio']:.3f}")

    return df_full, df_cv


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


def main(save_masks: bool = False) -> None:
    paths = RunPaths()
    paths.ensure()

    df_full, df_cv = build_feature_tables(save_masks=save_masks, paths=paths)

    rows = []
    rows.extend(evaluate_table(df_full, mask_name="full", paths=paths))
    rows.extend(evaluate_table(df_cv, mask_name="cv", paths=paths))

    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(paths.metrics, index=False)
    print(f"[metrics] wrote {paths.metrics}")


if __name__ == "__main__":
    save = "--save-masks" in sys.argv
    main(save_masks=save)
