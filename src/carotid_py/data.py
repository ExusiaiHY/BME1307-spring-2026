"""Data loading and ROI handling for Part 1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
import pandas as pd

from .config import PART1_IMAGES_DIR, PART1_METADATA_FILE, PART1_TEMPLATE_FILE


REQUIRED_COLUMNS = ("sample_id", "file_name", "modality")
OPTIONAL_COLUMNS = (
    "subject_id",
    "side",
    "gain",
    "dynamic_range",
    "depth_mm",
    "pixel_spacing_mm",
    "pixel_spacing_x_mm",
    "pixel_spacing_y_mm",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
    "machine_diameter_mm",
    "notes",
)
NUMERIC_COLUMNS = (
    "gain",
    "dynamic_range",
    "depth_mm",
    "pixel_spacing_mm",
    "pixel_spacing_x_mm",
    "pixel_spacing_y_mm",
    "roi_x0",
    "roi_y0",
    "roi_x1",
    "roi_y1",
    "machine_diameter_mm",
)
ROI_COLUMNS = ("roi_x0", "roi_y0", "roi_x1", "roi_y1")
VALID_MODALITIES = {"bmode", "color_doppler"}


@dataclass(frozen=True)
class Sample:
    sample_id: str
    modality: str
    path: Path
    image_bgr: np.ndarray
    metadata: dict


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _normalize_modality(value: str) -> str:
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "b_mode": "bmode",
        "bmode": "bmode",
        "doppler": "color_doppler",
        "color": "color_doppler",
        "color_doppler": "color_doppler",
    }
    if text not in aliases:
        raise ValueError(f"unsupported modality '{value}', expected one of {sorted(VALID_MODALITIES)}")
    return aliases[text]


def _coerce_numeric(df: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_metadata(
    metadata_file: Path = PART1_METADATA_FILE,
    images_dir: Path = PART1_IMAGES_DIR,
) -> pd.DataFrame:
    """Load Part 1 metadata and resolve image paths."""
    if not metadata_file.exists():
        raise FileNotFoundError(
            f"metadata file not found: {metadata_file}\n"
            f"Copy and fill the template first: {PART1_TEMPLATE_FILE}"
        )

    df = pd.read_csv(metadata_file)
    df = _normalize_columns(df)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"metadata missing required columns: {missing}")
    if df.empty:
        raise ValueError(
            f"metadata file {metadata_file} is empty. Fill it using template {PART1_TEMPLATE_FILE}"
        )

    df = _coerce_numeric(df, NUMERIC_COLUMNS)
    df["sample_id"] = df["sample_id"].astype(str).str.strip()
    df["file_name"] = df["file_name"].astype(str).str.strip()
    df["modality"] = df["modality"].map(_normalize_modality)

    def resolve_path(name: str) -> Path:
        path = Path(name)
        return path if path.is_absolute() else images_dir / path

    df["path"] = df["file_name"].map(resolve_path)
    missing_files = [str(p) for p in df["path"] if not p.exists()]
    if missing_files:
        raise FileNotFoundError(
            f"{len(missing_files)} image file(s) missing. First entries: {missing_files[:3]}"
        )

    return df.reset_index(drop=True)


def iter_samples(metadata: pd.DataFrame) -> Iterator[Sample]:
    for row in metadata.to_dict(orient="records"):
        img = cv2.imread(str(row["path"]), cv2.IMREAD_COLOR)
        if img is None:
            raise IOError(f"failed to read {row['path']}")
        yield Sample(
            sample_id=str(row["sample_id"]),
            modality=str(row["modality"]),
            path=Path(row["path"]),
            image_bgr=img,
            metadata=row,
        )


def resolve_search_bbox(meta: dict, image_shape: tuple[int, int], modality: str) -> tuple[int, int, int, int, str]:
    """Return the bbox used for segmentation.

    Priority:
    1. Use explicit ROI from metadata if present.
    2. Otherwise search within a central crop, which makes the first pass more
       robust before manual ROI tuning is available.
    """
    h, w = image_shape[:2]
    values = [meta.get(col) for col in ROI_COLUMNS]
    if all(pd.notna(v) for v in values):
        x0, y0, x1, y1 = [int(v) for v in values]
        x0 = max(0, min(x0, w - 1))
        x1 = max(x0 + 1, min(x1, w))
        y0 = max(0, min(y0, h - 1))
        y1 = max(y0 + 1, min(y1, h))
        return x0, y0, x1, y1, "metadata_roi"

    if modality == "color_doppler":
        x0, x1 = int(w * 0.15), int(w * 0.85)
        y0, y1 = int(h * 0.15), int(h * 0.85)
    else:
        x0, x1 = int(w * 0.2), int(w * 0.8)
        y0, y1 = int(h * 0.2), int(h * 0.8)
    return x0, y0, x1, y1, "auto_center_window"


def crop_to_bbox(image_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = bbox
    return image_bgr[y0:y1, x0:x1]


def place_mask(mask_crop: np.ndarray, full_shape: tuple[int, int], bbox: tuple[int, int, int, int]) -> np.ndarray:
    x0, y0, x1, y1 = bbox
    out = np.zeros(full_shape[:2], dtype=bool)
    out[y0:y1, x0:x1] = mask_crop.astype(bool)
    return out
