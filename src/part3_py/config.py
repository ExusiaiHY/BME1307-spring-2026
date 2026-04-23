"""Configuration for Part 3 foundation-model experiments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PART3_OUTPUTS_DIR = Path(os.environ.get("PART3_OUTPUTS_DIR", str(PROJECT_ROOT / "outputs" / "part3")))
PART3_CACHE_DIR = Path(os.environ.get("PART3_CACHE_DIR", str(PROJECT_ROOT / ".cache" / "part3")))

PART1_METADATA_FILE = Path(os.environ.get("PART3_PART1_METADATA_FILE", str(PROJECT_ROOT / "data" / "metadata.csv")))
PART1_IMAGES_DIR = Path(os.environ.get("PART3_PART1_IMAGES_DIR", str(PROJECT_ROOT / "data")))

# Official SAM 2 checkpoints are released in the Hiera family rather than
# under the older SAM "ViT-B" naming. We default to the base-sized checkpoint.
SAM2_MODEL_ID = os.environ.get("PART3_SAM2_MODEL_ID", "facebook/sam2-hiera-base-plus")

OPENCLIP_MODEL_NAME = os.environ.get("PART3_OPENCLIP_MODEL_NAME", "ViT-B-32")
OPENCLIP_PRETRAINED = os.environ.get("PART3_OPENCLIP_PRETRAINED", "laion2b_s34b_b79k")
BIOMEDCLIP_MODEL_ID = os.environ.get(
    "PART3_BIOMEDCLIP_MODEL_ID",
    "hf-hub:microsoft/BiomedCLIP-PubMedBERT_256-vit_base_patch16_224",
)


@dataclass(frozen=True)
class Part3Paths:
    outputs: Path = PART3_OUTPUTS_DIR
    cache: Path = PART3_CACHE_DIR
    hf_cache: Path = PART3_CACHE_DIR / "huggingface"
    metrics_dir: Path = PART3_OUTPUTS_DIR / "metrics"
    roc_dir: Path = PART3_OUTPUTS_DIR / "roc"
    overlays_dir: Path = PART3_OUTPUTS_DIR / "overlays"
    embeddings_dir: Path = PART3_OUTPUTS_DIR / "embeddings"
    part1_overlay_dir: Path = PART3_OUTPUTS_DIR / "overlays" / "part1_sam2"
    part2_overlay_dir: Path = PART3_OUTPUTS_DIR / "overlays" / "part2_sam2"
    part1_measurements: Path = PART3_OUTPUTS_DIR / "metrics" / "part1_sam2_measurements.csv"
    part1_report: Path = PART3_OUTPUTS_DIR / "metrics" / "part1_sam2_report.json"
    part2_segmentation_manifest: Path = PART3_OUTPUTS_DIR / "metrics" / "part2_sam2_manifest.csv"
    part2_segmentation_report: Path = PART3_OUTPUTS_DIR / "metrics" / "part2_sam2_report.json"
    classification_metrics: Path = PART3_OUTPUTS_DIR / "metrics" / "classification_foundation_models.csv"
    comparison_metrics: Path = PART3_OUTPUTS_DIR / "metrics" / "classification_comparison.csv"
    note_file: Path = PART3_OUTPUTS_DIR / "metrics" / "part3_notes.txt"

    def embedding_table(self, encoder_name: str) -> Path:
        return self.embeddings_dir / f"part2_embeddings_{encoder_name}.csv"

    def roc_plot(self, encoder_name: str, model_name: str) -> Path:
        return self.roc_dir / f"roc_{encoder_name}_{model_name}.png"

    def comparison_roc_plot(self, model_name: str) -> Path:
        return self.roc_dir / f"roc_compare_{model_name}.png"

    def part1_overlay(self, sample_id: str) -> Path:
        return self.part1_overlay_dir / f"{sample_id}_overlay.png"

    def part2_overlay(self, image_id: int) -> Path:
        return self.part2_overlay_dir / f"{image_id}_overlay.png"

    def ensure(self) -> None:
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.hf_cache.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.roc_dir.mkdir(parents=True, exist_ok=True)
        self.overlays_dir.mkdir(parents=True, exist_ok=True)
        self.embeddings_dir.mkdir(parents=True, exist_ok=True)
        self.part1_overlay_dir.mkdir(parents=True, exist_ok=True)
        self.part2_overlay_dir.mkdir(parents=True, exist_ok=True)

