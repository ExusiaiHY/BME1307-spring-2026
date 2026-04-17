"""Shape, intensity and texture features for a (image, mask) pair."""

from __future__ import annotations

from typing import Dict

import cv2
import numpy as np
from scipy.stats import kurtosis, skew
from skimage.feature import graycomatrix, graycoprops, local_binary_pattern
from skimage.measure import label, regionprops


GLCM_DISTANCES = (1, 3)
GLCM_ANGLES = (0.0, np.pi / 4.0, np.pi / 2.0, 3.0 * np.pi / 4.0)
GLCM_PROPS = ("contrast", "dissimilarity", "homogeneity", "ASM", "energy", "correlation")
GLCM_LEVELS = 32

LBP_RADIUS = 1
LBP_POINTS = 8 * LBP_RADIUS
LBP_METHOD = "uniform"
LBP_BINS = LBP_POINTS + 2  # uniform + 1 non-uniform bucket


def _to_gray(image_bgr: np.ndarray) -> np.ndarray:
    if image_bgr.ndim == 3:
        return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return image_bgr


def shape_features(mask: np.ndarray) -> Dict[str, float]:
    mask = mask.astype(bool)
    labeled = label(mask)
    if labeled.max() == 0:
        return _zero_shape()

    # Use the largest connected region for shape descriptors.
    regions = regionprops(labeled)
    region = max(regions, key=lambda r: r.area)

    area = float(region.area)
    perimeter = float(region.perimeter) if region.perimeter > 0 else 1e-6
    circularity = 4.0 * np.pi * area / (perimeter ** 2)
    minor = float(region.minor_axis_length) if region.minor_axis_length > 0 else 1e-6
    aspect = float(region.major_axis_length) / minor

    return {
        "shape_area": area,
        "shape_perimeter": perimeter,
        "shape_equiv_diameter": float(region.equivalent_diameter),
        "shape_eccentricity": float(region.eccentricity),
        "shape_solidity": float(region.solidity),
        "shape_extent": float(region.extent),
        "shape_circularity": float(circularity),
        "shape_aspect_ratio": float(aspect),
        "shape_major_axis": float(region.major_axis_length),
        "shape_minor_axis": float(region.minor_axis_length),
    }


def _zero_shape() -> Dict[str, float]:
    keys = [
        "shape_area", "shape_perimeter", "shape_equiv_diameter", "shape_eccentricity",
        "shape_solidity", "shape_extent", "shape_circularity", "shape_aspect_ratio",
        "shape_major_axis", "shape_minor_axis",
    ]
    return {k: 0.0 for k in keys}


def intensity_features(image_bgr: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
    gray = _to_gray(image_bgr)
    values = gray[mask.astype(bool)].astype(np.float64)
    if values.size == 0:
        return {f"intensity_{k}": 0.0 for k in
                ["mean", "std", "min", "max", "median", "skew", "kurt", "p10", "p90", "entropy"]}

    hist, _ = np.histogram(values, bins=32, range=(0, 255), density=True)
    hist = hist + 1e-12
    entropy = float(-np.sum(hist * np.log2(hist)) * (256 / 32))  # bin-width weighting

    return {
        "intensity_mean": float(values.mean()),
        "intensity_std": float(values.std()),
        "intensity_min": float(values.min()),
        "intensity_max": float(values.max()),
        "intensity_median": float(np.median(values)),
        "intensity_skew": float(skew(values, bias=False)) if values.size > 2 else 0.0,
        "intensity_kurt": float(kurtosis(values, bias=False)) if values.size > 3 else 0.0,
        "intensity_p10": float(np.percentile(values, 10)),
        "intensity_p90": float(np.percentile(values, 90)),
        "intensity_entropy": entropy,
    }


def glcm_features(image_bgr: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
    gray = _to_gray(image_bgr)
    mask_b = mask.astype(bool)
    if not mask_b.any():
        return {f"glcm_{p}": 0.0 for p in GLCM_PROPS}

    ys, xs = np.where(mask_b)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    patch = gray[y0:y1, x0:x1]
    patch_mask = mask_b[y0:y1, x0:x1]

    quant = (patch.astype(np.float32) / 256.0 * GLCM_LEVELS).astype(np.uint8)
    quant = np.clip(quant, 0, GLCM_LEVELS - 1)
    # Force non-masked pixels to 0 so co-occurrences outside mask are suppressed
    # when we later ignore the 0-row/col. Simpler: replace with 0 and mask them
    # in the GLCM output indirectly by computing on patch then averaging — for
    # small ROIs this is acceptable.
    quant[~patch_mask] = 0

    if patch.shape[0] < 4 or patch.shape[1] < 4:
        return {f"glcm_{p}": 0.0 for p in GLCM_PROPS}

    try:
        glcm = graycomatrix(
            quant,
            distances=list(GLCM_DISTANCES),
            angles=list(GLCM_ANGLES),
            levels=GLCM_LEVELS,
            symmetric=True,
            normed=True,
        )
    except ValueError:
        return {f"glcm_{p}": 0.0 for p in GLCM_PROPS}

    out: Dict[str, float] = {}
    for prop in GLCM_PROPS:
        values = graycoprops(glcm, prop)
        out[f"glcm_{prop}"] = float(values.mean())
    return out


def lbp_features(image_bgr: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
    gray = _to_gray(image_bgr)
    mask_b = mask.astype(bool)
    if not mask_b.any():
        return {f"lbp_bin{i}": 0.0 for i in range(LBP_BINS)}

    lbp = local_binary_pattern(gray, LBP_POINTS, LBP_RADIUS, method=LBP_METHOD)
    values = lbp[mask_b]
    hist, _ = np.histogram(values, bins=LBP_BINS, range=(0, LBP_BINS), density=True)
    return {f"lbp_bin{i}": float(hist[i]) for i in range(LBP_BINS)}


def extract_all(image_bgr: np.ndarray, mask: np.ndarray) -> Dict[str, float]:
    feats: Dict[str, float] = {}
    feats.update(shape_features(mask))
    feats.update(intensity_features(image_bgr, mask))
    feats.update(glcm_features(image_bgr, mask))
    feats.update(lbp_features(image_bgr, mask))
    return feats
