# Part 1 Preparation Guide

## What Is Ready Now

The repository now includes a Part 1 pipeline that can be connected directly to
the real data collected on `2026-04-21`.

- Metadata template: `docs/part1_metadata_template.csv`
- Runner: `scripts/run_part1.py`
- Output files: `outputs/part1/measurements.csv`, `outputs/part1/segmentation_report.json`

## Recommended Data Layout

Create the following local structure after acquisition:

```text
part1_data/
  metadata.csv
  images/
    sample_001.png
    sample_002.png
    ...
```

`metadata.csv` can be created by copying `docs/part1_metadata_template.csv`.

## Required Metadata Fields

- `sample_id`: unique identifier used in output file names.
- `file_name`: image file name, relative to `part1_data/images/`.
- `modality`: `bmode` or `color_doppler`.

## Strongly Recommended Fields

- `pixel_spacing_mm`:
  required if you want diameter and area in physical units.
- `roi_x0`, `roi_y0`, `roi_x1`, `roi_y1`:
  recommended if the artery is not tightly centered in the frame.
- `machine_diameter_mm`:
  lets the pipeline compare segmentation-based diameter with the device-side
  manual measurement.
- `gain_db`, `range_db`, `depth_cm`:
  recommended manual acquisition labels for gain, dynamic range, and depth.
  The loader auto-maps them to the legacy internal keys
  `gain`, `dynamic_range`, and `depth_mm`.
- `frequency_mhz`, `image_enhancement`, `gray_map`, `frame_correlation`,
  `puncture_guidance`, `color_map`:
  optional scanner settings that are kept in the metadata and carried into the
  output tables for later analysis.
- `flow_gain`, `prf`, `angle_degree`, `frame_rate`, `b_suppression`,
  `wall_filter`, `post_processing`:
  optional Color Doppler settings for the color-flow acquisitions.

If ROI is missing, the runner falls back to a central search window so the
first pass can still run immediately after acquisition.

## Using The Current `data/` Folder

If the collected images are already stored under `data/`, create the metadata
file there and run:

```bash
python scripts/run_part1.py --metadata data/metadata.csv --images-dir data --save-masks --save-overlays
```

## Run

```bash
python scripts/run_part1.py --metadata part1_data/metadata.csv --images-dir part1_data/images --save-masks --save-overlays
```

## Current Segmentation Baselines

- `bmode_carotid`: dark-lumen segmentation for B-mode carotid ROIs.
- `color_doppler`: color-flow segmentation for Doppler images, with fallback to
  the B-mode lumen method if color flow is not detected.

These are first-pass baselines intended to make Part 1 runnable immediately.
After the real images arrive, we can refine the ROI policy and adjust the
scoring logic based on the actual acquisition style.
