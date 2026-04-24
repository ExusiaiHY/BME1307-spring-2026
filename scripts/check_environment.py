"""Check that the local or Docker environment can run the project workflows."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MPLCONFIGDIR = PROJECT_ROOT / ".cache" / "matplotlib"
os.environ.setdefault("MPLCONFIGDIR", str(DEFAULT_MPLCONFIGDIR))
DEFAULT_MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)

CORE_MODULES = {
    "cv2": "OpenCV image I/O and segmentation",
    "numpy": "array operations",
    "pandas": "CSV/XLSX tables",
    "skimage": "classical image processing",
    "sklearn": "classification and cross-validation",
    "matplotlib": "plots",
    "seaborn": "report plots",
    "PIL": "image loading",
    "openpyxl": "pathology.xlsx labels",
}

FM_MODULES = {
    "torch": "deep learning runtime",
    "torchvision": "PyTorch vision utilities",
    "open_clip": "OpenCLIP and BiomedCLIP encoders",
    "transformers": "SAM2 Hugging Face loader",
    "huggingface_hub": "model downloads and cache",
}


def _module_version(module: object) -> str:
    version = getattr(module, "__version__", "")
    return f" {version}" if version else ""


def check_imports(mode: str) -> int:
    modules = dict(CORE_MODULES)
    if mode == "fm":
        modules.update(FM_MODULES)

    failures = []
    print(f"[imports] checking mode={mode}")
    for name, purpose in modules.items():
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - environment dependent
            failures.append((name, exc))
            print(f"  FAIL {name:16s} {purpose} ({type(exc).__name__}: {exc})")
        else:
            print(f"  OK   {name:16s} {_module_version(module)}")

    if failures:
        print("\n[imports] missing or broken dependencies:")
        for name, exc in failures:
            print(f"  - {name}: {exc}")
        return 1
    return 0


def _expect_path(label: str, path: Path, required: bool = True) -> bool:
    exists = path.exists()
    status = "OK" if exists else ("MISS" if required else "SKIP")
    print(f"  {status:4s} {label:20s} {path}")
    return exists or not required


def check_data_paths() -> int:
    busat_data = Path(os.environ.get("BUSAT_DATA_DIR", "Breast-ultrasound-samples/Ultrasound Samples"))
    part1_metadata = Path(os.environ.get("PART1_METADATA_FILE", "data/metadata.csv"))
    part1_images = Path(os.environ.get("PART1_IMAGES_DIR", "data"))
    busat_masks = Path(os.environ.get("BUSAT_MASKS_DIR", "outputs/part2/busat_masks"))
    outputs = Path(os.environ.get("BUSAT_OUTPUTS_DIR", "outputs/part2")).parent

    print("[data] checking expected paths")
    checks = [
        _expect_path("BUSAT image dir", busat_data),
        _expect_path("pathology.xlsx", busat_data / "pathology.xlsx"),
        _expect_path("Part 1 metadata", part1_metadata),
        _expect_path("Part 1 image root", part1_images),
        _expect_path("outputs root", outputs, required=False),
        _expect_path("BUSAT masks", busat_masks, required=False),
    ]
    return 0 if all(checks[:4]) else 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["core", "fm"], default="core")
    parser.add_argument("--check-data", action="store_true", help="Also validate expected mounted/local data paths.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    rc = check_imports(args.mode)
    if args.check_data:
        rc = max(rc, check_data_paths())
    if rc == 0:
        print("[ok] environment looks usable")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
