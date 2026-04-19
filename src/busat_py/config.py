"""Central paths and run configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Override with BUSAT_DATA_DIR (e.g. /data in the Docker image) so the code
# works both from a local clone and from a container with the dataset mounted
# at an arbitrary path.
_DEFAULT_DATA_DIR = PROJECT_ROOT / "Breast-ultrasound-samples" / "Ultrasound Samples"
DATA_DIR = Path(os.environ.get("BUSAT_DATA_DIR", str(_DEFAULT_DATA_DIR)))
LABELS_FILE = DATA_DIR / "pathology.xlsx"

_DEFAULT_OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "part2"
OUTPUTS_DIR = Path(os.environ.get("BUSAT_OUTPUTS_DIR", str(_DEFAULT_OUTPUTS_DIR)))
MASKS_DIR = OUTPUTS_DIR / "masks"
_DEFAULT_BUSAT_MASKS_DIR = OUTPUTS_DIR / "busat_masks"
BUSAT_MASKS_DIR = Path(os.environ.get("BUSAT_MASKS_DIR", str(_DEFAULT_BUSAT_MASKS_DIR)))

RANDOM_SEED = 42
CV_N_SPLITS = 5

# Image ids in this dataset run from 2.jpg to 121.jpg (120 files, no "1.jpg").
# The label row at index i corresponds to image id (i + FIRST_IMAGE_ID).
FIRST_IMAGE_ID = 2
EXPECTED_COUNT = 120
EXPECTED_POSITIVE = 46
EXPECTED_NEGATIVE = 74


@dataclass(frozen=True)
class RunPaths:
    outputs: Path = OUTPUTS_DIR
    masks: Path = MASKS_DIR
    features_full: Path = OUTPUTS_DIR / "features_full.csv"
    features_cv: Path = OUTPUTS_DIR / "features_cv.csv"
    features_refined: Path = OUTPUTS_DIR / "features_refined.csv"
    metrics: Path = OUTPUTS_DIR / "metrics.csv"
    segmentation_report: Path = OUTPUTS_DIR / "segmentation_report.json"
    busat_masks: Path = BUSAT_MASKS_DIR

    def feature_table(self, strategy: str) -> Path:
        return self.outputs / f"features_{strategy}.csv"

    def ensure(self) -> None:
        self.outputs.mkdir(parents=True, exist_ok=True)
        self.masks.mkdir(parents=True, exist_ok=True)
