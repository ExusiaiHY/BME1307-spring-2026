"""Cross-validation metrics and ROC plotting."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.base import clone
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline

from .config import CV_N_SPLITS, RANDOM_SEED


@dataclass
class FoldResult:
    accuracy: float
    sensitivity: float
    specificity: float
    auc: float
    fpr: np.ndarray
    tpr: np.ndarray


def _per_fold_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> Tuple[float, float, float, float]:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    acc = (tp + tn) / max(tp + tn + fp + fn, 1)
    sens = tp / max(tp + fn, 1)
    spec = tn / max(tn + fp, 1)
    try:
        auc = roc_auc_score(y_true, y_score)
    except ValueError:
        auc = float("nan")
    return float(acc), float(sens), float(spec), float(auc)


def cross_validate_model(
    X: np.ndarray,
    y: np.ndarray,
    pipeline: Pipeline,
    n_splits: int = CV_N_SPLITS,
    random_state: int = RANDOM_SEED,
) -> Tuple[Dict[str, float], List[FoldResult]]:
    """Run stratified K-fold cross-validation.

    Returns an aggregated metrics dict (mean + std) and per-fold details
    (including ROC curves) so the caller can draw a summary ROC plot.
    """
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    folds: List[FoldResult] = []

    for train_idx, test_idx in skf.split(X, y):
        est = clone(pipeline)
        est.fit(X[train_idx], y[train_idx])

        if hasattr(est, "predict_proba"):
            y_score = est.predict_proba(X[test_idx])[:, 1]
        else:
            y_score = est.decision_function(X[test_idx])
        y_pred = est.predict(X[test_idx])

        acc, sens, spec, auc = _per_fold_metrics(y[test_idx], y_pred, y_score)
        fpr, tpr, _ = roc_curve(y[test_idx], y_score)
        folds.append(FoldResult(accuracy=acc, sensitivity=sens, specificity=spec, auc=auc, fpr=fpr, tpr=tpr))

    def agg(key: str) -> Tuple[float, float]:
        vals = np.array([getattr(f, key) for f in folds], dtype=float)
        return float(np.nanmean(vals)), float(np.nanstd(vals))

    acc_m, acc_s = agg("accuracy")
    sens_m, sens_s = agg("sensitivity")
    spec_m, spec_s = agg("specificity")
    auc_m, auc_s = agg("auc")

    summary = {
        "accuracy_mean": acc_m, "accuracy_std": acc_s,
        "sensitivity_mean": sens_m, "sensitivity_std": sens_s,
        "specificity_mean": spec_m, "specificity_std": spec_s,
        "auc_mean": auc_m, "auc_std": auc_s,
    }
    return summary, folds


def _interpolate_roc(folds: List[FoldResult], grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    tprs = []
    for f in folds:
        interp = np.interp(grid, f.fpr, f.tpr)
        interp[0] = 0.0
        tprs.append(interp)
    arr = np.vstack(tprs)
    mean_tpr = arr.mean(axis=0)
    std_tpr = arr.std(axis=0)
    mean_tpr[-1] = 1.0
    return mean_tpr, std_tpr


def plot_roc(folds: List[FoldResult], title: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grid = np.linspace(0.0, 1.0, 101)
    mean_tpr, std_tpr = _interpolate_roc(folds, grid)
    aucs = [f.auc for f in folds]

    fig, ax = plt.subplots(figsize=(5, 5))
    for i, f in enumerate(folds):
        ax.plot(f.fpr, f.tpr, alpha=0.3, label=f"fold {i+1} AUC={f.auc:.3f}")
    ax.plot(grid, mean_tpr, color="tab:red", linewidth=2,
            label=f"mean AUC={np.mean(aucs):.3f} ± {np.std(aucs):.3f}")
    ax.fill_between(grid, np.maximum(mean_tpr - std_tpr, 0), np.minimum(mean_tpr + std_tpr, 1),
                    color="tab:red", alpha=0.15)
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", alpha=0.6)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.01)
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
