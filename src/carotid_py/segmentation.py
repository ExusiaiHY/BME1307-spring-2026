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


def _disk_mask(shape: Tuple[int, int], cx: float, cy: float, radius: float) -> np.ndarray:
    h, w = shape
    yy, xx = np.ogrid[:h, :w]
    return ((yy - cy) ** 2 + (xx - cx) ** 2) <= (radius ** 2)


def _hough_carotid_candidates(
    gray: np.ndarray,
    min_radius_px: int,
    max_radius_px: int,
) -> list[tuple[float, float, float]]:
    """Return (cx, cy, r) circle candidates on the inverted B-mode image."""
    med = cv2.medianBlur(gray, 7)
    inv = 255 - med
    blur = cv2.GaussianBlur(inv, (9, 9), 2)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(20, min_radius_px + max_radius_px),
        param1=80,
        param2=25,
        minRadius=int(min_radius_px),
        maxRadius=int(max_radius_px),
    )
    if circles is None:
        return []
    return [(float(c[0]), float(c[1]), float(c[2])) for c in circles[0]]


def _score_carotid_circle(
    gray: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
) -> dict | None:
    h, w = gray.shape
    # Exclude the sub-cutaneous / fascia band near the top and any candidates
    # that sit on the frame border; carotid lumen is deeper than ~0.2 * depth.
    if cx - radius * 0.6 < 0.04 * w or cx + radius * 0.6 > 0.96 * w:
        return None
    if cy < 0.22 * h or cy > 0.82 * h:
        return None
    interior = _disk_mask(gray.shape, cx, cy, radius * 0.7)
    if not interior.any():
        return None
    vals = gray[interior].astype(np.float32)
    mean_int = float(vals.mean())
    std_int = float(vals.std())
    if mean_int > 110:
        return None
    annulus_outer = _disk_mask(gray.shape, cx, cy, radius * 1.35)
    annulus = annulus_outer & ~_disk_mask(gray.shape, cx, cy, radius * 1.05)
    if annulus.any():
        ring_vals = gray[annulus].astype(np.float32)
        ring_mean = float(ring_vals.mean())
    else:
        ring_mean = mean_int
    contrast = ring_mean - mean_int
    # Reject candidates without a visible bright wall — subcutaneous shadows
    # and acoustic drop-outs look dark in the centre but also dark around.
    if contrast < 18.0:
        return None
    score = (
        (110.0 - mean_int)
        + 1.2 * contrast
        - 0.25 * std_int
    )
    return {
        "cx": cx,
        "cy": cy,
        "radius": radius,
        "mean_interior": mean_int,
        "std_interior": std_int,
        "ring_mean": ring_mean,
        "contrast": contrast,
        "score": score,
    }


def _refine_carotid_mask(
    gray: np.ndarray,
    cx: float,
    cy: float,
    radius: float,
) -> np.ndarray | None:
    h, w = gray.shape
    pad = int(max(radius * 1.6, 24))
    y0 = max(0, int(cy) - pad)
    y1 = min(h, int(cy) + pad + 1)
    x0 = max(0, int(cx) - pad)
    x1 = min(w, int(cx) + pad + 1)
    patch = gray[y0:y1, x0:x1]
    if patch.size == 0:
        return None
    patch_cx = cx - x0
    patch_cy = cy - y0
    inv = 1.0 - (patch.astype(np.float32) / 255.0)
    init = _disk_mask(patch.shape, patch_cx, patch_cy, radius * 0.55)
    try:
        refined = morphological_chan_vese(
            inv,
            num_iter=40,
            init_level_set=init.astype(np.int8),
            smoothing=2,
        ).astype(bool)
    except Exception:
        refined = init
    refined = binary_fill_holes(refined)
    radius_open = max(1, int(radius // 6))
    refined = binary_opening(refined, disk(radius_open))
    refined = binary_closing(refined, disk(max(1, radius_open + 1)))
    refined = remove_small_objects(refined, min_size=max(40, int(np.pi * (radius * 0.3) ** 2)))
    if not refined.any():
        return None
    labeled = label(refined)
    best_region = None
    best_overlap = -1.0
    for region in regionprops(labeled):
        ry, rx = region.centroid
        dist = float(np.hypot(ry - patch_cy, rx - patch_cx))
        if dist > radius * 1.2:
            continue
        if region.area < int(np.pi * (radius * 0.3) ** 2):
            continue
        if region.area > int(np.pi * (radius * 1.5) ** 2):
            continue
        per = region.perimeter if region.perimeter > 0 else 1e-6
        circ = 4.0 * np.pi * region.area / (per ** 2)
        overlap = circ - 0.01 * dist
        if overlap > best_overlap:
            best_overlap = overlap
            best_region = region
    if best_region is None:
        return None
    patch_mask = labeled == best_region.label
    full = np.zeros(gray.shape, dtype=bool)
    full[y0:y1, x0:x1] = patch_mask
    return full


def segment_bmode_carotid(
    image_bgr: np.ndarray,
    pixel_spacing_mm: float | None = None,
) -> tuple[np.ndarray, SegmentMeta]:
    """Segment the dark carotid lumen on a B-mode image.

    Uses Hough Circles on the inverted image to locate vessel-sized dark
    circular blobs, scores candidates by interior darkness and wall contrast,
    and refines the best seed with a morphological Chan-Vese inside a padded
    patch around the detected circle.
    """
    gray = _to_gray(image_bgr)
    h, w = gray.shape

    if pixel_spacing_mm is not None and pixel_spacing_mm > 0:
        min_r = max(8, int(2.0 / pixel_spacing_mm))
        max_r = max(min_r + 4, int(5.5 / pixel_spacing_mm))
    else:
        min_r = max(12, min(h, w) // 30)
        max_r = max(min_r + 8, min(h, w) // 7)

    candidates = _hough_carotid_candidates(gray, min_r, max_r)
    scored = [c for c in (_score_carotid_circle(gray, cx, cy, r) for cx, cy, r in candidates) if c]

    if not scored:
        fallback = _fallback_center_ellipse(gray.shape)
        return fallback, summarize_mask("bmode_carotid", fallback, fallback=True, extras={
            "reason": "no_circle_candidate",
            "min_radius_px": int(min_r),
            "max_radius_px": int(max_r),
        })

    best = max(scored, key=lambda c: c["score"])
    refined = _refine_carotid_mask(gray, best["cx"], best["cy"], best["radius"])
    if refined is None or not refined.any():
        fallback = _disk_mask(gray.shape, best["cx"], best["cy"], best["radius"])
        return fallback, summarize_mask("bmode_carotid_circle", fallback, fallback=True, extras={
            "reason": "active_contour_fallback_to_hough_circle",
            "cx": best["cx"],
            "cy": best["cy"],
            "radius": best["radius"],
            "mean_interior": best["mean_interior"],
            "score": best["score"],
        })
    return refined, summarize_mask("bmode_carotid", refined, extras={
        "cx": best["cx"],
        "cy": best["cy"],
        "hough_radius": best["radius"],
        "mean_interior": best["mean_interior"],
        "ring_mean": best["ring_mean"],
        "contrast": best["contrast"],
        "score": best["score"],
        "n_candidates": len(scored),
    })


def segment_color_doppler(
    image_bgr: np.ndarray,
    pixel_spacing_mm: float | None = None,
) -> tuple[np.ndarray, SegmentMeta]:
    """Segment color Doppler flow region as a vessel proxy.

    Falls back to the B-mode carotid detector when no color pixels exist in
    the frame, which is what happens when the image is actually a B-mode
    capture that was labeled as color_doppler.
    """
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
        bmode_mask, meta = segment_bmode_carotid(image_bgr, pixel_spacing_mm=pixel_spacing_mm)
        meta.strategy = "color_doppler_fallback_bmode"
        meta.fallback = True
        meta.extras["reason"] = "no_color_flow_detected"
        return bmode_mask, meta

    hull = convex_hull_image(mask)
    hull = binary_fill_holes(binary_dilation(hull, disk(max(1, radius))))
    return hull.astype(bool), summarize_mask("color_doppler", hull, extras={
        "selection_score": float(info["score"]),
    })


def segment_auto(
    image_bgr: np.ndarray,
    modality: str,
    pixel_spacing_mm: float | None = None,
) -> tuple[np.ndarray, SegmentMeta]:
    if modality == "color_doppler":
        return segment_color_doppler(image_bgr, pixel_spacing_mm=pixel_spacing_mm)
    return segment_bmode_carotid(image_bgr, pixel_spacing_mm=pixel_spacing_mm)


def overlay(image_bgr: np.ndarray, mask: np.ndarray, alpha: float = 0.4) -> np.ndarray:
    out = image_bgr.copy()
    red = np.zeros_like(out)
    red[..., 2] = 255
    blended = cv2.addWeighted(out, 1.0, red, alpha, 0.0)
    out[mask.astype(bool)] = blended[mask.astype(bool)]
    return out
