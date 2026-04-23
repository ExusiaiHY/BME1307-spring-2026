"""Prompt generation and overlay helpers for Part 3 segmentation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from busat_py.segmentation import summarize_mask as summarize_part2_mask
from carotid_py.data import crop_to_bbox, resolve_search_bbox
from carotid_py.segmentation import (
    _hough_carotid_candidates,
    _score_carotid_circle,
    _to_gray as carotid_to_gray,
    overlay as carotid_overlay,
    segment_auto as carotid_segment_auto,
)


@dataclass
class Prompt:
    x: float
    y: float
    source: str
    extras: dict[str, Any]

    @property
    def xy(self) -> tuple[float, float]:
        return self.x, self.y


def _radius_range(image_shape: tuple[int, int], pixel_spacing_mm: float | None) -> tuple[int, int]:
    h, w = image_shape
    if pixel_spacing_mm is not None and pixel_spacing_mm > 0:
        min_r = max(8, int(2.0 / pixel_spacing_mm))
        max_r = max(min_r + 4, int(5.5 / pixel_spacing_mm))
    else:
        min_r = max(12, min(h, w) // 30)
        max_r = max(min_r + 8, min(h, w) // 7)
    return int(min_r), int(max_r)


def hough_carotid_prompt(image_bgr: np.ndarray, pixel_spacing_mm: float | None = None) -> Prompt:
    gray = carotid_to_gray(image_bgr)
    h, w = gray.shape
    min_r, max_r = _radius_range(gray.shape, pixel_spacing_mm)
    circles = _hough_carotid_candidates(gray, min_r, max_r)
    scored = [c for c in (_score_carotid_circle(gray, cx, cy, r) for cx, cy, r in circles) if c]
    if not scored:
        return Prompt(
            x=float(w / 2.0),
            y=float(h / 2.0),
            source="center_fallback",
            extras={
                "reason": "no_hough_candidate",
                "min_radius_px": int(min_r),
                "max_radius_px": int(max_r),
            },
        )
    best = max(scored, key=lambda item: item["score"])
    return Prompt(
        x=float(best["cx"]),
        y=float(best["cy"]),
        source="hough_circle",
        extras={
            "radius_px": float(best["radius"]),
            "mean_interior": float(best["mean_interior"]),
            "ring_mean": float(best["ring_mean"]),
            "contrast": float(best["contrast"]),
            "score": float(best["score"]),
            "n_candidates": int(len(scored)),
        },
    )


def image_center_prompt(image_shape: tuple[int, int]) -> Prompt:
    h, w = image_shape[:2]
    return Prompt(
        x=float(w / 2.0),
        y=float(h / 2.0),
        source="image_center",
        extras={},
    )


def part1_baseline_prompt(image_bgr: np.ndarray, metadata: dict, modality: str) -> Prompt:
    bbox = resolve_search_bbox(metadata, image_bgr.shape[:2], modality)
    x0, y0, x1, y1, roi_source = bbox
    crop = crop_to_bbox(image_bgr, (x0, y0, x1, y1))
    mask_crop, seg_meta = carotid_segment_auto(
        crop,
        modality=modality,
        pixel_spacing_mm=metadata.get("pixel_spacing_mm"),
    )
    if mask_crop.any():
        ys, xs = np.nonzero(mask_crop)
        x = float(x0 + xs.mean())
        y = float(y0 + ys.mean())
        reason = "baseline_mask_centroid"
    else:
        x = float((x0 + x1) / 2.0)
        y = float((y0 + y1) / 2.0)
        reason = "roi_center"
    return Prompt(
        x=x,
        y=y,
        source="part1_baseline_fallback",
        extras={
            "reason": reason,
            "roi_source": roi_source,
            "roi_x0": int(x0),
            "roi_y0": int(y0),
            "roi_x1": int(x1),
            "roi_y1": int(y1),
            "baseline_strategy": seg_meta.strategy,
            "baseline_fallback": bool(seg_meta.fallback),
        },
    )


def render_overlay(
    image_bgr: np.ndarray,
    mask: np.ndarray,
    prompt: Prompt,
    title: str | None = None,
) -> np.ndarray:
    out = carotid_overlay(image_bgr, mask)
    cv2.circle(out, (int(round(prompt.x)), int(round(prompt.y))), 5, (0, 255, 255), thickness=-1)
    cv2.circle(out, (int(round(prompt.x)), int(round(prompt.y))), 10, (0, 255, 255), thickness=2)
    if prompt.source == "hough_circle" and "radius_px" in prompt.extras:
        cv2.circle(
            out,
            (int(round(prompt.x)), int(round(prompt.y))),
            int(round(prompt.extras["radius_px"])),
            (255, 255, 0),
            thickness=1,
        )
    lines = [title] if title else []
    lines.append(f"prompt={prompt.source}")
    if "selected_iou_score" in prompt.extras:
        lines.append(f"SAM2 IoU={prompt.extras['selected_iou_score']:.3f}")
    for i, text in enumerate([line for line in lines if line]):
        cv2.putText(
            out,
            text,
            (12, 24 + 22 * i),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return out


def summarize_part2_sam2_mask(mask: np.ndarray) -> dict[str, float]:
    meta = summarize_part2_mask("sam2_center_point", mask)
    return {
        "foreground_ratio": float(meta.foreground_ratio),
        "centroid_offset": float(meta.centroid_offset),
    }
