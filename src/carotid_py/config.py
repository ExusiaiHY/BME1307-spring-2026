"""Configuration for the Part 1 carotid workflow."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_PART1_ROOT = PROJECT_ROOT / "part1_data"
PART1_ROOT = Path(os.environ.get("PART1_ROOT", str(DEFAULT_PART1_ROOT)))
PART1_IMAGES_DIR = Path(os.environ.get("PART1_IMAGES_DIR", str(PART1_ROOT / "images")))
PART1_METADATA_FILE = Path(os.environ.get("PART1_METADATA_FILE", str(PART1_ROOT / "metadata.csv")))
PART1_TEMPLATE_FILE = PROJECT_ROOT / "docs" / "part1_metadata_template.csv"

DEFAULT_PART1_OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "part1"
PART1_OUTPUTS_DIR = Path(os.environ.get("PART1_OUTPUTS_DIR", str(DEFAULT_PART1_OUTPUTS_DIR)))


@dataclass(frozen=True)
class Part1Paths:
    outputs: Path = PART1_OUTPUTS_DIR
    masks: Path = PART1_OUTPUTS_DIR / "masks"
    overlays: Path = PART1_OUTPUTS_DIR / "overlays"
    measurements: Path = PART1_OUTPUTS_DIR / "measurements.csv"
    report: Path = PART1_OUTPUTS_DIR / "segmentation_report.json"

    def ensure(self) -> None:
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.masks.mkdir(parents=True, exist_ok=True)
        self.overlays.mkdir(parents=True, exist_ok=True)
