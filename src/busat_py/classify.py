"""Classifier factories for Part 2 baseline."""

from __future__ import annotations

from typing import Dict

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .config import RANDOM_SEED


def make_models() -> Dict[str, Pipeline]:
    """Return three classifiers wrapped in pipelines with standardized features.

    All models use ``class_weight='balanced'`` because the label distribution
    is 74 negative / 46 positive (roughly 1.6:1).
    """
    return {
        "logreg": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                C=1.0,
                penalty="l2",
                class_weight="balanced",
                solver="liblinear",
                max_iter=2000,
                random_state=RANDOM_SEED,
            )),
        ]),
        "svm": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(
                C=1.0,
                kernel="rbf",
                gamma="scale",
                probability=True,
                class_weight="balanced",
                random_state=RANDOM_SEED,
            )),
        ]),
        "rf": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(
                n_estimators=300,
                max_depth=None,
                class_weight="balanced",
                random_state=RANDOM_SEED,
                n_jobs=-1,
            )),
        ]),
    }
