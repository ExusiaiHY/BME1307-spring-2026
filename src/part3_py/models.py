"""Model loading for Part 3."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import torch
from PIL import Image

from .config import (
    BIOMEDCLIP_MODEL_ID,
    OPENCLIP_MODEL_NAME,
    OPENCLIP_PRETRAINED,
    SAM2_MODEL_ID,
)


def configure_hf_cache(cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_dir / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir / "transformers"))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")


def _with_temp_env(key: str, value: str):
    class _EnvCtx:
        def __enter__(self_nonlocal):
            self_nonlocal._old = os.environ.get(key)
            os.environ[key] = value

        def __exit__(self_nonlocal, exc_type, exc, tb):
            if self_nonlocal._old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = self_nonlocal._old

    return _EnvCtx()


def resolve_device(device: str = "auto") -> torch.device:
    if device != "auto":
        return torch.device(device)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _to_rgb_pil(image_bgr: np.ndarray) -> Image.Image:
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(image_rgb)


def _move_batch_to_device(batch: dict, device: torch.device) -> dict:
    out = {}
    for key, value in batch.items():
        if hasattr(value, "to"):
            out[key] = value.to(device)
        else:
            out[key] = value
    return out


@dataclass
class ImageEncoder:
    name: str
    model: torch.nn.Module
    preprocess: Callable[[Image.Image], torch.Tensor]
    device: torch.device

    def encode_image_bgr(self, image_bgr: np.ndarray) -> np.ndarray:
        image = _to_rgb_pil(image_bgr)
        tensor = self.preprocess(image).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            embedding = self.model.encode_image(tensor)
            embedding = torch.nn.functional.normalize(embedding, dim=-1)
        return embedding[0].detach().cpu().numpy().astype(np.float32)


@dataclass
class Sam2Segmenter:
    model_id: str
    model: torch.nn.Module
    processor: object
    device: torch.device

    def segment_from_point(
        self,
        image_bgr: np.ndarray,
        point_xy: tuple[float, float],
        point_label: int = 1,
        preferred_max_area_ratio: float | None = None,
        prefer_smallest: bool = False,
    ) -> tuple[np.ndarray, dict]:
        image = _to_rgb_pil(image_bgr)
        point_x, point_y = [float(v) for v in point_xy]
        inputs = self.processor(
            images=image,
            input_points=[[[[point_x, point_y]]]],
            input_labels=[[[int(point_label)]]],
            return_tensors="pt",
        )
        inputs = _move_batch_to_device(inputs, self.device)
        with torch.inference_mode():
            outputs = self.model(**inputs)

        masks = self.processor.post_process_masks(
            outputs.pred_masks.detach().cpu(),
            inputs["original_sizes"].detach().cpu(),
        )
        mask_tensor = masks[0][0]
        iou_scores = outputs.iou_scores.detach().cpu().numpy()[0, 0]
        px = int(np.clip(round(point_x), 0, mask_tensor.shape[-1] - 1))
        py = int(np.clip(round(point_y), 0, mask_tensor.shape[-2] - 1))

        candidates = []
        for idx in range(mask_tensor.shape[0]):
            mask_np = mask_tensor[idx].numpy().astype(bool)
            area_ratio = float(mask_np.mean())
            contains_point = bool(mask_np[py, px])
            adjusted_iou = float(iou_scores[idx])
            if preferred_max_area_ratio is not None and area_ratio > preferred_max_area_ratio:
                adjusted_iou -= 2.0 * float(area_ratio - preferred_max_area_ratio)
            candidates.append({
                "index": int(idx),
                "mask": mask_np,
                "area_ratio": area_ratio,
                "iou_score": float(iou_scores[idx]),
                "adjusted_iou": adjusted_iou,
                "contains_point": contains_point,
            })

        valid = [c for c in candidates if c["contains_point"]] or candidates
        if prefer_smallest:
            if preferred_max_area_ratio is not None:
                within = [c for c in valid if c["area_ratio"] <= preferred_max_area_ratio]
                if within:
                    valid = within
            best = min(valid, key=lambda c: (c["area_ratio"], -c["iou_score"]))
        else:
            best = max(valid, key=lambda c: c["adjusted_iou"])

        best_idx = int(best["index"])
        best_mask = best["mask"]

        meta = {
            "model_id": self.model_id,
            "selected_mask_index": best_idx,
            "iou_scores": [float(x) for x in iou_scores.tolist()],
            "selected_iou_score": float(iou_scores[best_idx]),
            "selected_area_ratio": float(best["area_ratio"]),
            "selection_mode": "prefer_smallest" if prefer_smallest else "adjusted_iou",
            "candidate_summary": [
                {
                    "index": c["index"],
                    "area_ratio": c["area_ratio"],
                    "iou_score": c["iou_score"],
                    "adjusted_iou": c["adjusted_iou"],
                    "contains_point": c["contains_point"],
                }
                for c in candidates
            ],
        }
        return best_mask, meta


def load_openclip_encoder(device: torch.device, cache_dir: Path) -> ImageEncoder:
    import open_clip

    try:
        model, _, preprocess = open_clip.create_model_and_transforms(
            OPENCLIP_MODEL_NAME,
            pretrained=OPENCLIP_PRETRAINED,
            device=device,
            precision="fp32",
            cache_dir=str(cache_dir),
        )
    except Exception as exc:  # pragma: no cover - network/cache dependent
        try:
            with _with_temp_env("HF_HUB_OFFLINE", "1"):
                model, _, preprocess = open_clip.create_model_and_transforms(
                    OPENCLIP_MODEL_NAME,
                    pretrained=OPENCLIP_PRETRAINED,
                    device=device,
                    precision="fp32",
                    cache_dir=str(cache_dir),
                )
        except Exception as cached_exc:
            raise RuntimeError(
                "failed to load OpenCLIP weights; either allow network access or pre-populate the Hugging Face cache "
                f"under {cache_dir}"
            ) from cached_exc or exc
    model.eval()
    return ImageEncoder(
        name="openclip",
        model=model,
        preprocess=preprocess,
        device=device,
    )


def load_biomedclip_encoder(device: torch.device, cache_dir: Path) -> ImageEncoder:
    import open_clip

    try:
        model, preprocess = open_clip.create_model_from_pretrained(
            BIOMEDCLIP_MODEL_ID,
            device=device,
            precision="fp32",
            cache_dir=str(cache_dir),
        )
    except Exception as exc:  # pragma: no cover - network/cache dependent
        try:
            with _with_temp_env("HF_HUB_OFFLINE", "1"):
                model, preprocess = open_clip.create_model_from_pretrained(
                    BIOMEDCLIP_MODEL_ID,
                    device=device,
                    precision="fp32",
                    cache_dir=str(cache_dir),
                )
        except Exception as cached_exc:
            raise RuntimeError(
                "failed to load BiomedCLIP weights; either allow network access or pre-populate the Hugging Face cache "
                f"under {cache_dir}"
            ) from cached_exc or exc
    model.eval()
    return ImageEncoder(
        name="biomedclip",
        model=model,
        preprocess=preprocess,
        device=device,
    )


def load_sam2_segmenter(device: torch.device, cache_dir: Path, model_id: str = SAM2_MODEL_ID) -> Sam2Segmenter:
    configure_hf_cache(cache_dir)
    from transformers import AutoModelForMaskGeneration, AutoProcessor

    try:
        processor = AutoProcessor.from_pretrained(model_id, cache_dir=str(cache_dir))
        model = AutoModelForMaskGeneration.from_pretrained(model_id, cache_dir=str(cache_dir)).to(device)
    except Exception as exc:  # pragma: no cover - network/cache dependent
        try:
            processor = AutoProcessor.from_pretrained(
                model_id,
                cache_dir=str(cache_dir),
                local_files_only=True,
            )
            model = AutoModelForMaskGeneration.from_pretrained(
                model_id,
                cache_dir=str(cache_dir),
                local_files_only=True,
            ).to(device)
        except Exception as cached_exc:
            raise RuntimeError(
                "failed to load SAM2 weights; either allow network access or pre-populate the Hugging Face cache "
                f"under {cache_dir}"
            ) from cached_exc or exc
    model.eval()
    return Sam2Segmenter(model_id=model_id, model=model, processor=processor, device=device)
