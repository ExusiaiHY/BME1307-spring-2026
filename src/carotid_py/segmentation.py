"""Segmentation baselines for carotid ultrasound images."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

import cv2
import numpy as np
from scipy.ndimage import binary_fill_holes
from skimage.filters import threshold_otsu
from skimage.measure import label, regionprops
from skimage.morphology import (
    binary_closing,
    binary_dilation,
    binary_opening,
    convex_hull_image,
    disk,
    remove_small_objects,
)
from skimage.segmentation import morphological_chan_vese


@dataclass
class SegmentMeta:
    strategy: str
    fallback: bool = False
    foreground_ratio: float = 0.0
    centroid_offset: float = 0.0
    extras: dict = field(default_factory=dict)


def _to_gray(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr.ndim == 3:
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return image_bgr


def _center_prior(shape: Tuple[int, int], sigma_scale: float = 0.28) -> np.ndarray:
    h, w = shape
    yy, xx = np.mgrid[:h, :w]
    cy, cx = h / 2.0, w / 2.0
    gy = ((yy - cy) / max(sigma_scale * h, 1.0)) ** 2
    gx = ((xx - cx) / max(sigma_scale * w, 1.0)) ** 2
    return np.exp(-0.5 * (gx + gy)).astype(np.float32)


def summarize_mask(
    strategy: str,
    mask: np.ndarray,
    fallback: bool = False,
    extras: dict | None = None,
) -> SegmentMeta:
    mask_b = mask.astype(bool)
    h, w = mask_b.shape
    ratio = float(mask_b.mean())
    if not mask_b.any():
        offset = float("nan")
    else:
        ys, xs = np.nonzero(mask_b)
        centroid = np.array([ys.mean(), xs.mean()])
        center = np.array([h / 2.0, w / 2.0])
        offset = float(np.linalg.norm(centroid - center) / max(np.hypot(h, w), 1.0))
    return SegmentMeta(
        strategy=strategy,
        fallback=fallback,
        foreground_ratio=ratio,
        centroid_offset=offset,
        extras=extras or {},
    )


def _fallback_center_ellipse(shape: Tuple[int, int]) -> np.ndarray:
    h, w = shape
    mask = np.zeros((h, w), dtype=np.uint8)
    center = (w // 2, h // 2)
    axes = (max(6, int(w * 0.12)), max(6, int(h * 0.12)))
    cv2.ellipse(mask, center, axes, 0, 0, 360, 1, thickness=-1)
    return mask.astype(bool)


def _select_best_region(
    candidate: np.ndarray,
    min_area_ratio: float,
    max_area_ratio: float,
) -> tuple[np.ndarray | None, dict | None]:
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
        if area_ratio < min_area_ratio or area_ratio > max_area_ratio:
            continue
        perimeter = float(region.perimeter) if region.perimeter > 0 else 1e-6
        circularity = min(1.5, 4.0 * np.pi * region.area / (perimeter ** 2))
        dist = float(np.linalg.norm(np.array(region.centroid) - center) / max(diag, 1.0))
        score = (
            1.6 * circularity
            + 0.8 * float(region.solidity)
            + 0.2 * area_ratio
            - 0.8 * dist
            - 0.3 * float(region.eccentricity)
        )
        if best is None or score > best["score"]:
            best = {
                "label": region.label,
                "score": score,
                "area_ratio": area_ratio,
                "circularity": circularity,
                "dist": dist,
            }

    if best is None:
        return None, None
    return labeled == best["label"], best


def segment_bmode_carotid(image_bgr: np.ndarray) -> tuple[np.ndarray, SegmentMeta]:
    """Segment dark carotid lumen from a B-mode image or ROI crop."""
    gray = _to_gray(image_bgr)
    h, w = gray.shape

    med = cv2.medianBlur(gray, 5)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(med)
    inv = 1.0 - (clahe.astype(np.float32) / 255.0)
    score = cv2.GaussianBlur(inv * _center_prior(gray.shape), (0, 0), 1.2)

    try:
        thr = threshold_otsu(score)
    except ValueError:
        thr = float(np.quantile(score, 0.82))

    radius = max(1, min(h, w) // 70)
    seed = score >= max(thr, float(np.quantile(score, 0.82)))
    seed = binary_opening(seed, disk(radius))
    seed = binary_closing(seed, disk(max(1, radius + 1)))
    seed = binary_fill_holes(seed)
    seed = remove_small_objects(seed, min_size=max(20, int(h * w * 0.002)))

    seed_mask, seed_info = _select_best_region(seed, min_area_ratio=0.002, max_area_ratio=0.25)
    if seed_mask is None:
        fallback = _fallback_center_ellipse(gray.shape)
        return fallback, summarize_mask("bmode_carotid", fallback, fallback=True, extras={
            "reason": "seed_not_found",
        })

    ys, xs = np.nonzero(binary_dilation(seed_mask, disk(max(1, radius + 1))))
    pad_y = max(6, h // 10)
    pad_x = max(6, w // 10)
    y0 = max(0, int(ys.min()) - pad_y)
    y1 = min(h, int(ys.max()) + pad_y + 1)
    x0 = max(0, int(xs.min()) - pad_x)
    x1 = min(w, int(xs.max()) + pad_x + 1)

    patch = inv[y0:y1, x0:x1]
    init = seed_mask[y0:y1, x0:x1]
    refined = morphological_chan_vese(
        patch,
        num_iter=50,
        init_level_set=init.astype(np.int8),
        smoothing=2,
    ).astype(bool)
    refined = binary_fill_holes(refined)
    refined = binary_closing(refined, disk(max(1, radius)))
    refined = binary_opening(refined, disk(max(1, radius // 2)))
    refined = remove_small_objects(refined, min_size=max(20, int(refined.size * 0.01)))

    refined_mask, refined_info = _select_best_region(refined, min_area_ratio=0.002, max_area_ratio=0.3)
    if refined_mask is None:
        fallback = _fallback_center_ellipse(gray.shape)
        return fallback, summarize_mask("bmode_carotid", fallback, fallback=True, extras={
            "reason": "active_contour_failed",
        })

    mask = np.zeros_like(gray, dtype=bool)
    mask[y0:y1, x0:x1] = refined_mask
    return mask, summarize_mask("bmode_carotid", mask, extras={
        "seed_score": float(seed_info["score"]),
        "refined_score": float(refined_info["score"]),
        "search_bbox": [int(x0), int(y0), int(x1), int(y1)],
    })


def segment_color_doppler(image_bgr: np.ndarray) -> tuple[np.ndarray, SegmentMeta]:
    """Segment color Doppler flow region as a vessel proxy."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[..., 1]
    val = hsv[..., 2]
    candidate = (sat > 70) & (val > 40)

    h, w = candidate.shape
    radius = max(1, min(h, w) // 80)
    candidate = binary_opening(candidate, disk(radius))
    candidate = binary_closing(candidate, disk(max(1, radius + 1)))
    candidate = remove_small_objects(candidate, min_size=max(12, int(h * w * 0.001)))

    mask, info = _select_best_region(candidate, min_area_ratio=0.001, max_area_ratio=0.35)
    if mask is None:
        bmode_mask, meta = segment_bmode_carotid(image_bgr)
        meta.strategy = "color_doppler_fallback_bmode"
        meta.fallback = True
        meta.extras["reason"] = "no_color_flow_detected"
        return bmode_mask, meta

    hull = convex_hull_image(mask)
    hull = binary_fill_holes(binary_dilation(hull, disk(max(1, radius))))
    return hull.astype(bool), summarize_mask("color_doppler", hull, extras={
        "selection_score": float(info["score"]),
    })


def segment_auto(image_bgr: np.ndarray, modality: str) -> tuple[np.ndarray, SegmentMeta]:
    if modality == "color_doppler":
        return segment_color_doppler(image_bgr)
    return segment_bmode_carotid(image_bgr)


def overlay(image_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    out = image_bgr.copy()
    red = np.zeros_like(out)
    red[..., 2] = 255
    blended = cv2.addWeighted(out, 1.0, red, alpha, 0.0)
    out[mask.astype(bool)] = blended[mask.astype(bool)]
    return out
