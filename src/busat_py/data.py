"""Dataset loading for Part 2."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
import pandas as pd

from .config import (
    DATA_DIR,
    EXPECTED_COUNT,
    EXPECTED_NEGATIVE,
    EXPECTED_POSITIVE,
    FIRST_IMAGE_ID,
    LABELS_FILE,
)


@dataclass(frozen=True)
class Sample:
    image_id: int
    label: int
    path: Path
    image_bgr: np.ndarray


def load_labels(labels_file: Path = LABELS_FILE) -> pd.DataFrame:
    """Read pathology labels and attach absolute image paths.

    Row i in the excel maps to image id ``FIRST_IMAGE_ID + i``. The dataset
    lacks ``1.jpg`` on disk, so we anchor at ``FIRST_IMAGE_ID`` rather than at
    1.
    """
    df = pd.read_excel(labels_file)
    if "P/N" not in df.columns:
        raise ValueError(f"expected 'P/N' column in {labels_file}, got {df.columns.tolist()}")

    df = df.rename(columns={"P/N": "label"})
    df["label"] = df["label"].astype(int)
    df["image_id"] = df.index + FIRST_IMAGE_ID
    df["path"] = df["image_id"].apply(lambda i: DATA_DIR / f"{i}.jpg")

    missing = [str(p) for p in df["path"] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"{len(missing)} image file(s) missing, first: {missing[:3]}")

    return df[["image_id", "label", "path"]].reset_index(drop=True)


def basic_stats(labels: pd.DataFrame) -> dict:
    counts = labels["label"].value_counts().to_dict()
    stats = {
        "n": int(len(labels)),
        "positive": int(counts.get(1, 0)),
        "negative": int(counts.get(0, 0)),
    }
    if stats["n"] != EXPECTED_COUNT:
        raise AssertionError(f"expected {EXPECTED_COUNT} rows, got {stats['n']}")
    if stats["positive"] != EXPECTED_POSITIVE or stats["negative"] != EXPECTED_NEGATIVE:
        raise AssertionError(
            f"unexpected label distribution {stats}, "
            f"expected P={EXPECTED_POSITIVE} N={EXPECTED_NEGATIVE}"
        )
    return stats


def iter_images(labels: pd.DataFrame) -> Iterator[Sample]:
    for row in labels.itertuples(index=False):
        img = cv2.imread(str(row.path), cv2.IMREAD_COLOR)
        if img is None:
            raise IOError(f"failed to read {row.path}")
        yield Sample(image_id=int(row.image_id), label=int(row.label), path=row.path, image_bgr=img)
