"""Evaluation utilities for Part 3."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / ".cache" / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from busat_py.classify import make_models
from busat_py.evaluate import FoldResult, cross_validate_model, plot_roc


def evaluate_embedding_table(
    df: pd.DataFrame,
    encoder_name: str,
    out_dir: Path,
) -> tuple[list[dict], dict[str, list[FoldResult]]]:
    feature_cols = [c for c in df.columns if c not in {"image_id", "label"}]
    X = df[feature_cols].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy(dtype=int)

    rows: list[dict] = []
    folds_by_model: dict[str, list[FoldResult]] = {}
    for model_name, pipeline in make_models().items():
        summary, folds = cross_validate_model(X, y, pipeline)
        rows.append({
            "source": "part3_embedding",
            "experiment": encoder_name,
            "model": model_name,
            **summary,
        })
        folds_by_model[model_name] = folds
        plot_roc(
            folds,
            title=f"ROC — encoder={encoder_name} model={model_name}",
            out_path=out_dir / f"roc_{encoder_name}_{model_name}.png",
        )
    return rows, folds_by_model


def evaluate_part2_baseline_table(
    df: pd.DataFrame,
    strategy_name: str,
) -> tuple[list[dict], dict[str, list[FoldResult]]]:
    feature_cols = [c for c in df.columns if c not in {"image_id", "label"}]
    X = df[feature_cols].to_numpy(dtype=np.float64)
    y = df["label"].to_numpy(dtype=int)

    rows: list[dict] = []
    folds_by_model: dict[str, list[FoldResult]] = {}
    for model_name, pipeline in make_models().items():
        summary, folds = cross_validate_model(X, y, pipeline)
        rows.append({
            "source": "part2_baseline",
            "experiment": strategy_name,
            "model": model_name,
            **summary,
        })
        folds_by_model[model_name] = folds
    return rows, folds_by_model


def _interpolate_roc(folds: list[FoldResult], grid: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tprs = []
    aucs = []
    for fold in folds:
        interp = np.interp(grid, fold.fpr, fold.tpr)
        interp[0] = 0.0
        tprs.append(interp)
        aucs.append(fold.auc)
    arr = np.vstack(tprs)
    mean_tpr = arr.mean(axis=0)
    mean_tpr[-1] = 1.0
    std_tpr = arr.std(axis=0)
    return mean_tpr, std_tpr, np.asarray(aucs, dtype=float)


def plot_roc_comparison(
    curves: dict[str, list[FoldResult]],
    title: str,
    out_path: Path,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid = np.linspace(0.0, 1.0, 101)
    fig, ax = plt.subplots(figsize=(5.5, 5.0))

    for label, folds in curves.items():
        mean_tpr, std_tpr, aucs = _interpolate_roc(folds, grid)
        ax.plot(grid, mean_tpr, linewidth=2, label=f"{label} AUC={np.nanmean(aucs):.3f} ± {np.nanstd(aucs):.3f}")
        ax.fill_between(
            grid,
            np.maximum(mean_tpr - std_tpr, 0.0),
            np.minimum(mean_tpr + std_tpr, 1.0),
            alpha=0.12,
        )

    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", alpha=0.6)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.01)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160)
    plt.close(fig)
