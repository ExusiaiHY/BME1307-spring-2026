"""Segmentation strategies for the ROI crops.

Available strategies:

* ``segment_full``: treat the whole ROI as foreground.
* ``segment_cv``: threshold + morphology baseline.
* ``segment_refined``: center-prior seeded active contour refinement for
  tighter lesion boundaries on closely cropped ROIs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Tuple

import cv2
import numpy as np
from skimage.filters import threshold_otsu
from skimage.morphology import (
    binary_closing,
    binary_dilation,
    binary_opening,
    disk,
    remove_small_objects,
)
from skimage.measure import label, regionprops
from skimage.segmentation import morphological_chan_vese


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


def summarize_mask(
    strategy: str,
    mask: np.ndarray,
    fallback: bool = False,
    extras: dict | None = None,
) -> SegmentMeta:
    """Compute consistent summary metadata for a binary mask."""
    mask_b = mask.astype(bool)
    h, w = mask_b.shape
    ratio = float(mask_b.mean())
    if not mask_b.any():
        dist = float("nan")
    else:
        ys, xs = np.nonzero(mask_b)
        center = np.array([h / 2.0, w / 2.0])
        centroid = np.array([ys.mean(), xs.mean()])
        dist = float(np.linalg.norm(centroid - center) / max(np.hypot(h, w), 1.0))
    return SegmentMeta(
        strategy=strategy,
        fallback=fallback,
        foreground_ratio=ratio,
        centroid_offset=dist,
        extras=extras or {},
    )


def segment_full(image_bgr: np.ndarray) -> Tuple[np.ndarray, SegmentMeta]:
    h, w = image_bgr.shape[:2]
    mask = np.ones((h, w), dtype=bool)
    return mask, summarize_mask("full", mask)


def _fallback_center_mask(shape: Tuple[int, int]) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    y0, y1 = int(h * 0.2), int(h * 0.8)
    x0, x1 = int(w * 0.2), int(w * 0.8)
    mask[y0:y1, x0:x1] = True
    return mask


def _center_prior(shape: Tuple[int, int], sigma_scale: float = 0.32) -> np.ndarray:
    h, w = shape
    yy, xx = np.mgrid[:h, :w]
    cy, cx = h / 2.0, w / 2.0
    gy = ((yy - cy) / max(sigma_scale * h, 1.0)) ** 2
    gx = ((xx - cx) / max(sigma_scale * w, 1.0)) ** 2
    return np.exp(-0.5 * (gx + gy)).astype(np.float32)


def _best_region(
    candidate: np.ndarray,
    max_area_ratio: float = 0.85,
    center_weight: float = 0.5,
):
    labeled = label(candidate)
    if labeled.max() == 0:
        return None, None

    h, w = candidate.shape
    image_area = h * w
    center = np.array([h / 2.0, w / 2.0])
    diag = float(np.hypot(h, w))

    best = None
    for region in regionprops(labeled):
        area_ratio = region.area / image_area
        if area_ratio > max_area_ratio:
            continue
        centroid = np.array(region.centroid)
        dist = float(np.linalg.norm(centroid - center)) / max(diag, 1.0)
        score = area_ratio - center_weight * dist
        if best is None or score > best["score"]:
            best = {
                "region": region,
                "score": score,
                "area_ratio": area_ratio,
                "dist": dist,
            }

    if best is None:
        return None, None
    return labeled == best["region"].label, best


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
        fallback = _fallback_center_mask(gray.shape)
        return fallback, summarize_mask("cv", fallback, fallback=True, extras={
            "reason": "otsu_failed",
        })

    candidate = blurred < thr  # lesion is darker than background

    radius = max(2, min(h, w) // 40)
    candidate = binary_opening(candidate, disk(radius))
    candidate = binary_closing(candidate, disk(radius))

    min_area = int(image_area * min_area_ratio)
    candidate = remove_small_objects(candidate, min_size=max(min_area, 16))

    if not candidate.any():
        fallback = _fallback_center_mask(gray.shape)
        return fallback, summarize_mask("cv", fallback, fallback=True, extras={
            "reason": "no_candidate",
        })

    mask, best = _best_region(candidate, max_area_ratio=max_area_ratio, center_weight=0.5)
    if mask is None or best is None:
        fallback = _fallback_center_mask(gray.shape)
        return fallback, summarize_mask("cv", fallback, fallback=True, extras={
            "reason": "no_region_passed_area_filter",
        })

    return mask, summarize_mask("cv", mask, extras={
        "selection_score": float(best["score"]),
    })


def segment_refined(
    image_bgr: np.ndarray,
    seed_quantile: float = 0.78,
    active_contour_iters: int = 60,
) -> Tuple[np.ndarray, SegmentMeta]:
    """Hybrid classical segmentation with active contour refinement.

    The lesion is usually hypoechoic and roughly centered in the cropped ROI.
    We use a center-weighted darkness prior to initialize a seed mask, then
    refine it with morphological Chan-Vese inside a padded local window.
    """
    gray = _to_gray(image_bgr)
    h, w = gray.shape

    med = cv2.medianBlur(gray, 5)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(med)
    inv = 1.0 - (clahe.astype(np.float32) / 255.0)
    score = cv2.GaussianBlur(inv * _center_prior(gray.shape), ksize=(0, 0), sigmaX=1.2)

    try:
        thr = threshold_otsu(score)
    except ValueError:
        thr = float(np.quantile(score, seed_quantile))

    radius = max(1, min(h, w) // 60)
    seed = score >= max(thr, float(np.quantile(score, seed_quantile)))
    seed = binary_opening(seed, disk(radius))
    seed = binary_closing(seed, disk(max(1, radius + 1)))
    seed = remove_small_objects(seed, min_size=max(16, int(h * w * 0.005)))

    seed_mask, seed_info = _best_region(seed, max_area_ratio=0.6, center_weight=0.9)
    if seed_mask is None:
        fallback = _fallback_center_mask(gray.shape)
        return fallback, summarize_mask("refined", fallback, fallback=True, extras={
            "reason": "seed_not_found",
        })

    seed_mask = binary_dilation(seed_mask, disk(max(1, radius + 1)))
    ys, xs = np.nonzero(seed_mask)
    pad_y = max(6, h // 12)
    pad_x = max(6, w // 12)
    y0 = max(0, int(ys.min()) - pad_y)
    y1 = min(h, int(ys.max()) + pad_y + 1)
    x0 = max(0, int(xs.min()) - pad_x)
    x1 = min(w, int(xs.max()) + pad_x + 1)

    patch = inv[y0:y1, x0:x1]
    init = seed_mask[y0:y1, x0:x1]

    refined_patch = morphological_chan_vese(
        patch,
        num_iter=active_contour_iters,
        init_level_set=init.astype(np.int8),
        smoothing=2,
    ).astype(bool)
    refined_patch = remove_small_objects(
        refined_patch,
        min_size=max(16, int(refined_patch.size * 0.02)),
    )
    refined_patch = binary_closing(refined_patch, disk(max(1, radius)))
    refined_patch = binary_opening(refined_patch, disk(max(1, radius // 2)))

    refined_patch, refined_info = _best_region(
        refined_patch,
        max_area_ratio=0.85,
        center_weight=1.1,
    )
    if refined_patch is None:
        fallback = _fallback_center_mask(gray.shape)
        return fallback, summarize_mask("refined", fallback, fallback=True, extras={
            "reason": "active_contour_failed",
        })

    mask = np.zeros((h, w), dtype=bool)
    mask[y0:y1, x0:x1] = refined_patch
    meta = summarize_mask("refined", mask, extras={
        "seed_score": float(seed_info["score"]) if seed_info else 0.0,
        "refined_score": float(refined_info["score"]) if refined_info else 0.0,
        "bbox": [int(x0), int(x1), int(y0), int(y1)],
    })
    return mask, meta


SEGMENTERS: Dict[str, Callable[[np.ndarray], Tuple[np.ndarray, SegmentMeta]]] = {
    "full": segment_full,
    "cv": segment_cv,
    "refined": segment_refined,
}


def overlay(image_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    """Return a BGR overlay with the mask tinted red for visualization."""
    overlay = image_bgr.copy()
    red = np.zeros_like(overlay)
    red[..., 2] = 255
    blended = cv2.addWeighted(overlay, 1.0, red, alpha, 0.0)
    out = image_bgr.copy()
    out[mask.astype(bool)] = blended[mask.astype(bool)]
    return out
