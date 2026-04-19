"""Quantification helpers for Part 1 carotid segmentation."""

from __future__ import annotations

from typing import Dict

import numpy as np
from skimage.measure import label, regionprops


LITERATURE_DIAMETER_RANGE_MM = (4.3, 7.7)


def _largest_region(mask: np.ndarray):
    labeled = label(mask.astype(bool))
    if labeled.max() == 0:
        return None
    return max(regionprops(labeled), key=lambda r: r.area)


def _spacing_from_meta(meta: dict) -> tuple[float | None, float | None]:
    sx = meta.get("pixel_spacing_x_mm")
    sy = meta.get("pixel_spacing_y_mm")
    s = meta.get("pixel_spacing_mm")

    sx = float(sx) if sx is not None and np.isfinite(sx) else None
    sy = float(sy) if sy is not None and np.isfinite(sy) else None
    s = float(s) if s is not None and np.isfinite(s) else None

    if sx is None and s is not None:
        sx = s
    if sy is None and s is not None:
        sy = s
    return sx, sy


def quantify_mask(mask: np.ndarray, meta: dict) -> Dict[str, float | str | bool | None]:
    region = _largest_region(mask)
    sx, sy = _spacing_from_meta(meta)
    mean_spacing = float(np.nanmean([v for v in (sx, sy) if v is not None])) if any(v is not None for v in (sx, sy)) else None

    out: Dict[str, float | str | bool | None] = {
        "mask_nonempty": bool(region is not None),
        "pixel_spacing_x_mm": sx,
        "pixel_spacing_y_mm": sy,
        "pixel_spacing_mean_mm": mean_spacing,
    }
    if region is None:
        zero_keys = [
            "area_px",
            "perimeter_px",
            "equiv_diameter_px",
            "major_axis_px",
            "minor_axis_px",
            "circularity",
            "eccentricity",
            "solidity",
            "extent",
            "centroid_x_px",
            "centroid_y_px",
            "bbox_x0",
            "bbox_y0",
            "bbox_x1",
            "bbox_y1",
        ]
        out.update({k: 0.0 for k in zero_keys})
        out.update({
            "area_mm2": None,
            "equiv_diameter_mm": None,
            "major_axis_mm_approx": None,
            "minor_axis_mm_approx": None,
            "diameter_used_mm": None,
            "diameter_in_literature_range": None,
            "machine_diameter_abs_error_mm": None,
            "machine_diameter_rel_error": None,
        })
        return out

    area = float(region.area)
    perimeter = float(region.perimeter) if region.perimeter > 0 else 1e-6
    circularity = 4.0 * np.pi * area / (perimeter ** 2)
    minr, minc, maxr, maxc = region.bbox

    out.update({
        "area_px": area,
        "perimeter_px": perimeter,
        "equiv_diameter_px": float(region.equivalent_diameter),
        "major_axis_px": float(region.major_axis_length),
        "minor_axis_px": float(region.minor_axis_length),
        "circularity": float(circularity),
        "eccentricity": float(region.eccentricity),
        "solidity": float(region.solidity),
        "extent": float(region.extent),
        "centroid_x_px": float(region.centroid[1]),
        "centroid_y_px": float(region.centroid[0]),
        "bbox_x0": int(minc),
        "bbox_y0": int(minr),
        "bbox_x1": int(maxc),
        "bbox_y1": int(maxr),
    })

    if sx is not None and sy is not None and mean_spacing is not None:
        area_mm2 = area * sx * sy
        equiv_diameter_mm = float(region.equivalent_diameter) * mean_spacing
        major_axis_mm = float(region.major_axis_length) * mean_spacing
        minor_axis_mm = float(region.minor_axis_length) * mean_spacing
    else:
        area_mm2 = None
        equiv_diameter_mm = None
        major_axis_mm = None
        minor_axis_mm = None

    diameter_used_mm = minor_axis_mm if minor_axis_mm is not None else equiv_diameter_mm
    low, high = LITERATURE_DIAMETER_RANGE_MM
    in_range = None if diameter_used_mm is None else (low <= diameter_used_mm <= high)

    out.update({
        "area_mm2": area_mm2,
        "equiv_diameter_mm": equiv_diameter_mm,
        "major_axis_mm_approx": major_axis_mm,
        "minor_axis_mm_approx": minor_axis_mm,
        "diameter_used_mm": diameter_used_mm,
        "diameter_in_literature_range": in_range,
    })

    machine_diameter = meta.get("machine_diameter_mm")
    if machine_diameter is not None and np.isfinite(machine_diameter) and diameter_used_mm is not None:
        machine_diameter = float(machine_diameter)
        abs_error = diameter_used_mm - machine_diameter
        rel_error = abs(abs_error) / max(abs(machine_diameter), 1e-6)
    else:
        abs_error = None
        rel_error = None
    out["machine_diameter_abs_error_mm"] = abs_error
    out["machine_diameter_rel_error"] = rel_error
    return out
