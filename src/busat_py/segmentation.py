"""Segmentation strategies for the ROI crops.

Two strategies:

* ``segment_full``: trivially returns an all-foreground mask (baseline that
  treats the whole ROI as the lesion).
* ``segment_cv``: classical CV pipeline (Otsu + morphology) returning a lesion
  mask plus metadata, used as a BUSAT ``autosegment`` fallback while the MATLAB
  toolbox is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import cv2
import numpy as np
from skimage.filters import threshold_otsu
from skimage.morphology import binary_closing, binary_opening, disk, remove_small_objects
from skimage.measure import label, regionprops


@dataclass
class SegmentMeta:
    strategy: str
    fallback: bool = False
    foreground_ratio: float = 0.0
    centroid_offset: float = 0.0  # normalized distance from image center
    extras: dict = field(default_factory=dict)


def _to_gray(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr.ndim == 3:
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return image_bgr


def _suppress_caliper_marks(gray: np.ndarray) -> np.ndarray:
    """Reduce the impact of small bright scanner annotations (+/x markers).

    These are tiny bright blobs embedded in the tissue area. A small median
    filter followed by a morphological closing smooths them without destroying
    lesion-scale structure.
    """
    med = cv2.medianBlur(gray, 3)
    return cv2.morphologyEx(med, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))


def segment_full(image_bgr: np.ndarray) -> Tuple[np.ndarray, SegmentMeta]:
    h, w = image_bgr.shape[:2]
    mask = np.ones((h, w), dtype=bool)
    meta = SegmentMeta(strategy="full", fallback=False, foreground_ratio=1.0, centroid_offset=0.0)
    return mask, meta


def _fallback_center_mask(shape: Tuple[int, int]) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    y0, y1 = int(h * 0.2), int(h * 0.8)
    x0, x1 = int(w * 0.2), int(w * 0.8)
    mask[y0:y1, x0:x1] = True
    return mask


def segment_cv(
    image_bgr: np.ndarray,
    min_area_ratio: float = 0.02,
    max_area_ratio: float = 0.85,
) -> Tuple[np.ndarray, SegmentMeta]:
    """Classical lesion segmentation.

    Lesions in these B-mode ROIs are hypoechoic (dark). We smooth, threshold
    with Otsu inverted, clean with morphology, and pick the connected region
    whose centroid is closest to the image center among candidates above a
    minimum area.
    """
    gray = _to_gray(image_bgr)
    h, w = gray.shape
    image_area = h * w

    cleaned = _suppress_caliper_marks(gray)
    blurred = cv2.GaussianBlur(cleaned, ksize=(0, 0), sigmaX=1.5)

    try:
        thr = threshold_otsu(blurred)
    except ValueError:
        return _fallback_center_mask(gray.shape), SegmentMeta(
            strategy="cv", fallback=True, foreground_ratio=0.36, centroid_offset=0.0,
            extras={"reason": "otsu_failed"},
        )

    candidate = blurred < thr  # lesion is darker than background

    radius = max(2, min(h, w) // 40)
    candidate = binary_opening(candidate, disk(radius))
    candidate = binary_closing(candidate, disk(radius))

    min_area = int(image_area * min_area_ratio)
    candidate = remove_small_objects(candidate, min_size=max(min_area, 16))

    if not candidate.any():
        return _fallback_center_mask(gray.shape), SegmentMeta(
            strategy="cv", fallback=True, foreground_ratio=0.36, centroid_offset=0.0,
            extras={"reason": "no_candidate"},
        )

    labeled = label(candidate)
    center = np.array([h / 2.0, w / 2.0])
    diag = float(np.hypot(h, w))

    best = None
    for region in regionprops(labeled):
        area_ratio = region.area / image_area
        if area_ratio > max_area_ratio:
            continue
        centroid = np.array(region.centroid)
        dist = float(np.linalg.norm(centroid - center)) / diag
        # Score: prefer large, central regions. Equal weight on normalized
        # area and (1 - normalized distance).
        score = area_ratio - 0.5 * dist
        if best is None or score > best["score"]:
            best = {
                "region": region,
                "score": score,
                "area_ratio": area_ratio,
                "dist": dist,
            }

    if best is None:
        return _fallback_center_mask(gray.shape), SegmentMeta(
            strategy="cv", fallback=True, foreground_ratio=0.36, centroid_offset=0.0,
            extras={"reason": "no_region_passed_area_filter"},
        )

    mask = labeled == best["region"].label
    meta = SegmentMeta(
        strategy="cv",
        fallback=False,
        foreground_ratio=float(best["area_ratio"]),
        centroid_offset=float(best["dist"]),
    )
    return mask, meta


def overlay(image_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    """Return a BGR overlay with the mask tinted red for visualization."""
    overlay = image_bgr.copy()
    red = np.zeros_like(overlay)
    red[..., 2] = 255
    blended = cv2.addWeighted(overlay, 1.0, red, alpha, 0.0)
    out = image_bgr.copy()
    out[mask.astype(bool)] = blended[mask.astype(bool)]
    return out
