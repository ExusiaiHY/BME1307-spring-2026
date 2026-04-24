#!/usr/bin/env python3
"""
Build report-ready figures for BME1307 final report.
Outputs go to outputs/report_figures/.
"""

import shutil
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MPLCONFIGDIR = ROOT / ".cache" / "matplotlib"
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import cv2
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUTDIR = ROOT / "outputs" / "report_figures"
OUTDIR.mkdir(parents=True, exist_ok=True)
PAPER_FIGDIR = ROOT / "paper" / "figures"

PART1_MEAS = ROOT / "outputs" / "part1" / "measurements.csv"
PART1_SAM2 = ROOT / "outputs" / "part3" / "metrics" / "part1_sam2_measurements.csv"
PART2_FEAT_REFINED = ROOT / "outputs" / "part2" / "features_refined.csv"
PART2_FEAT_BUSAT = ROOT / "outputs" / "part2" / "features_busat.csv"
PART2_METRICS = ROOT / "outputs" / "part2" / "metrics.csv"
PART2_MASKDIR = ROOT / "outputs" / "part2" / "masks"
PART2_IMGDIR = ROOT / "Breast-ultrasound-samples" / "Ultrasound Samples"
PART3_COMP = ROOT / "outputs" / "part3" / "metrics" / "classification_comparison.csv"
NOTIONDIR = ROOT / "outputs" / "notion"

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams["figure.dpi"] = 150


def savefig(name, fig=None):
    path = OUTDIR / name
    (fig or plt.gcf()).savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig or plt.gcf())
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Part 1
# ---------------------------------------------------------------------------
def build_part1_figures():
    print("\n=== Part 1 figures ===")
    df = pd.read_csv(PART1_MEAS)
    df_sam2 = pd.read_csv(PART1_SAM2)

    # 1a. Diameter summary with literature range
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(df))
    bars = ax.bar(x, df["diameter_used_mm"], color="#4c78a8", edgecolor="black", linewidth=0.5)
    ax.axhspan(4.3, 7.7, color="green", alpha=0.1, label="Literature normal range (4.3–7.7 mm)")
    ax.axhline(6.38, color="red", linestyle="--", linewidth=1.5, label="Median = 6.38 mm")
    ax.set_xticks(x)
    ax.set_xticklabels([s.split("_")[-1] for s in df["sample_id"]], rotation=45, ha="right")
    ax.set_ylabel("Diameter (mm)")
    ax.set_xlabel("Sample")
    ax.set_title("Part 1: Carotid Artery Diameter Measurements (Classical Segmentation)")
    ax.legend(loc="upper left")
    ax.set_ylim(0, 10)
    for bar, val, in_range in zip(bars, df["diameter_used_mm"], df["diameter_in_literature_range"]):
        color = "black" if in_range else "red"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                f"{val:.2f}", ha="center", va="bottom", fontsize=9, color=color, fontweight="bold" if not in_range else "normal")
    savefig("fig1a_part1_diameter_summary.png", fig)

    # 1b. Classical vs SAM2 diameter comparison
    df_merge = pd.merge(
        df[["sample_id", "diameter_used_mm"]].rename(columns={"diameter_used_mm": "classical"}),
        df_sam2[["sample_id", "diameter_used_mm"]].rename(columns={"diameter_used_mm": "sam2"}),
        on="sample_id"
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(df_merge))
    width = 0.35
    ax.bar(x - width / 2, df_merge["classical"], width, label="Classical", color="#4c78a8", edgecolor="black")
    ax.bar(x + width / 2, df_merge["sam2"], width, label="SAM2 (zero-shot)", color="#f58518", edgecolor="black")
    ax.axhspan(4.3, 7.7, color="green", alpha=0.1)
    ax.set_xticks(x)
    ax.set_xticklabels([s.split("_")[-1] for s in df_merge["sample_id"]], rotation=45, ha="right")
    ax.set_ylabel("Diameter (mm)")
    ax.set_title("Part 1: Classical Segmentation vs SAM2 Zero-Shot Segmentation")
    ax.legend()
    ax.set_ylim(0, 12)
    savefig("fig1b_part1_classical_vs_sam2.png", fig)

    # 1c. Measurement table as a figure
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.axis("tight")
    ax.axis("off")
    table_data = df[["sample_id", "modality", "gain_db", "range_db", "diameter_used_mm", "diameter_in_literature_range"]].copy()
    table_data.columns = ["Sample ID", "Modality", "Gain (dB)", "Range (dB)", "Diameter (mm)", "In Range?"]
    table = ax.table(cellText=table_data.round(2).astype(str).values, colLabels=table_data.columns,
                     cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    fig.suptitle("Part 1: Measurement Summary", fontsize=14, y=0.95)
    savefig("fig1c_part1_measurement_table.png", fig)


# ---------------------------------------------------------------------------
# Part 2
# ---------------------------------------------------------------------------
def build_part2_figures():
    print("\n=== Part 2 figures ===")

    # 2a. Segmentation examples: pick 3 images, show original + 4 masks
    image_ids = [3, 6, 8]
    fig, axes = plt.subplots(len(image_ids), 5, figsize=(16, 10))
    strategies = ["original", "full", "cv", "refined", "busat"]
    for row, image_id in enumerate(image_ids):
        img_path = PART2_IMGDIR / f"{image_id}.jpg"
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        for col, strat in enumerate(strategies):
            ax = axes[row, col]
            if strat == "original":
                ax.imshow(img_color)
                ax.set_title(f"ID {image_id} (Original)", fontsize=10)
            else:
                mask_path = PART2_MASKDIR / f"{image_id}_{strat}_mask.png"
                if mask_path.exists():
                    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                    overlay = img_color.copy()
                    overlay[mask > 0] = [255, 0, 0]
                    blended = cv2.addWeighted(img_color, 0.6, overlay, 0.4, 0)
                    ax.imshow(blended)
                    # compute foreground ratio
                    fg_ratio = (mask > 0).sum() / mask.size
                    ax.set_title(f"{strat}\nfg={fg_ratio:.3f}", fontsize=9)
                else:
                    ax.text(0.5, 0.5, "N/A", transform=ax.transAxes, ha="center", va="center")
            ax.axis("off")
    fig.suptitle("Part 2: Segmentation Strategy Comparison (Overlay)", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    savefig("fig2a_part2_segmentation_examples.png", fig)

    # 2b. Feature distribution by label (refined mask)
    df_feat = pd.read_csv(PART2_FEAT_REFINED)
    key_features = [
        "shape_circularity", "shape_eccentricity", "shape_solidity",
        "intensity_mean", "intensity_std", "glcm_contrast"
    ]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    for ax, col in zip(axes.ravel(), key_features):
        sns.boxplot(
            data=df_feat,
            x="label",
            y=col,
            hue="label",
            ax=ax,
            palette="Set2",
            width=0.5,
            legend=False,
        )
        ax.set_title(col.replace("_", " ").title())
        ax.set_xlabel("Label (0=Benign, 1=Malignant)")
    fig.suptitle("Part 2: Feature Distributions by Label (Refined Segmentation)", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    savefig("fig2b_part2_feature_distribution.png", fig)

    # 2c. Metrics comparison: grouped bar chart for AUC and ACC
    df_m = pd.read_csv(PART2_METRICS)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    # AUC
    pivot_auc = df_m.pivot(index="mask", columns="model", values="auc_mean")
    pivot_auc_std = df_m.pivot(index="mask", columns="model", values="auc_std")
    pivot_auc = pivot_auc.reindex(["full", "cv", "refined", "busat"])
    pivot_auc_std = pivot_auc_std.reindex(["full", "cv", "refined", "busat"])
    pivot_auc.plot(kind="bar", ax=axes[0], yerr=pivot_auc_std.values.T, capsize=4, edgecolor="black", rot=0)
    axes[0].set_title("AUC by Segmentation Strategy & Classifier")
    axes[0].set_ylabel("AUC")
    axes[0].set_ylim(0.75, 1.0)
    axes[0].legend(title="Classifier", loc="lower right")
    axes[0].axhline(0.9, color="gray", linestyle="--", linewidth=1)
    # ACC
    pivot_acc = df_m.pivot(index="mask", columns="model", values="accuracy_mean")
    pivot_acc_std = df_m.pivot(index="mask", columns="model", values="accuracy_std")
    pivot_acc = pivot_acc.reindex(["full", "cv", "refined", "busat"])
    pivot_acc_std = pivot_acc_std.reindex(["full", "cv", "refined", "busat"])
    pivot_acc.plot(kind="bar", ax=axes[1], yerr=pivot_acc_std.values.T, capsize=4, edgecolor="black", rot=0)
    axes[1].set_title("Accuracy by Segmentation Strategy & Classifier")
    axes[1].set_ylabel("Accuracy")
    axes[1].set_ylim(0.7, 1.0)
    axes[1].legend(title="Classifier", loc="lower right")
    axes[1].axhline(0.85, color="gray", linestyle="--", linewidth=1)
    fig.suptitle("Part 2: Classification Performance Across Segmentation Strategies", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    savefig("fig2c_part2_metrics_comparison.png", fig)

    # 2d. Feature number impact (RFE-style) — required by project description
    print("  Computing feature number impact...")
    X = df_feat.drop(columns=["image_id", "label"]).values
    y = df_feat["label"].values
    feature_names = df_feat.drop(columns=["image_id", "label"]).columns.tolist()

    # Compute importances on full data (for ordering)
    rf_full = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    rf_full.fit(X, y)
    importances = rf_full.feature_importances_
    sorted_idx = np.argsort(importances)[::-1]

    n_features = X.shape[1]
    ks = list(range(1, n_features + 1, 2))  # every 2 to save time
    if n_features not in ks:
        ks.append(n_features)

    results = []
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for k in ks:
        idx = sorted_idx[:k]
        Xk = X[:, idx]
        scaler = StandardScaler()
        Xs = scaler.fit_transform(Xk)
        for clf_name, clf in [("SVM", SVC(kernel="rbf", probability=True, random_state=42)),
                               ("Random Forest", RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1))]:
            aucs = []
            for train_i, test_i in cv.split(Xs, y):
                clf.fit(Xs[train_i], y[train_i])
                proba = clf.predict_proba(Xs[test_i])[:, 1]
                aucs.append(roc_auc_score(y[test_i], proba))
            results.append({"k": k, "classifier": clf_name, "auc_mean": np.mean(aucs), "auc_std": np.std(aucs)})
    df_rfe = pd.DataFrame(results)

    fig, ax = plt.subplots(figsize=(10, 6))
    for clf_name, color in [("SVM", "#4c78a8"), ("Random Forest", "#f58518")]:
        sub = df_rfe[df_rfe["classifier"] == clf_name]
        ax.plot(sub["k"], sub["auc_mean"], marker="o", label=clf_name, color=color, linewidth=2)
        ax.fill_between(sub["k"], sub["auc_mean"] - sub["auc_std"], sub["auc_mean"] + sub["auc_std"],
                        color=color, alpha=0.15)
    ax.set_xlabel("Number of features (top-k by RF importance)")
    ax.set_ylabel("AUC (5-fold stratified CV)")
    ax.set_title("Part 2: Impact of Feature Count on Classification Performance")
    ax.legend()
    ax.set_ylim(0.5, 1.0)
    ax.axhline(0.9, color="gray", linestyle="--", linewidth=1)
    # annotate top features
    top3 = [feature_names[i] for i in sorted_idx[:3]]
    ax.text(0.98, 0.02, f"Top 3 features:\n1. {top3[0]}\n2. {top3[1]}\n3. {top3[2]}",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="wheat", alpha=0.5))
    savefig("fig2d_part2_feature_number_impact.png", fig)
    print(f"  Top 3 features: {top3}")

    # 2e. Segmentation error impact — required by project description
    # Strategy: show that as segmentation gets "better" (lower fg ratio for full->refined,
    # higher circularity), AUC improves. Also show per-image example.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Left: AUC improvement from full -> busat for each classifier
    df_m_sorted = df_m.sort_values(["model", "mask"])
    models = ["logreg", "svm", "rf"]
    x_pos = np.arange(len(models))
    auc_full = [df_m[(df_m["model"] == m) & (df_m["mask"] == "full")]["auc_mean"].values[0] for m in models]
    auc_busat = [df_m[(df_m["model"] == m) & (df_m["mask"] == "busat")]["auc_mean"].values[0] for m in models]
    width = 0.35
    axes[0].bar(x_pos - width / 2, auc_full, width, label="Full (no segmentation)", color="#e45756", edgecolor="black")
    axes[0].bar(x_pos + width / 2, auc_busat, width, label="BUSAT (best segmentation)", color="#59a14f", edgecolor="black")
    axes[0].set_xticks(x_pos)
    axes[0].set_xticklabels([m.upper() for m in models])
    axes[0].set_ylabel("AUC")
    axes[0].set_title("Effect of Segmentation Quality on AUC")
    axes[0].legend()
    axes[0].set_ylim(0.75, 1.0)
    for i, (a, b) in enumerate(zip(auc_full, auc_busat)):
        axes[0].annotate(f"+{b - a:.3f}", xy=(i + width / 4, max(a, b) + 0.01), ha="center", fontsize=10, color="darkgreen")

    # Right: mask quality proxy (mean fg ratio across all images per strategy)
    seg_report_path = ROOT / "outputs" / "part2" / "segmentation_report.json"
    if seg_report_path.exists():
        with open(seg_report_path) as f:
            seg_report = json.load(f)
        # compute mean fg ratio per strategy from features files
        fg_data = []
        for strat in ["full", "cv", "refined", "busat"]:
            feat_path = ROOT / "outputs" / "part2" / f"features_{strat}.csv"
            if feat_path.exists():
                df_f = pd.read_csv(feat_path)
                # shape_area relative to image size? We don't have image size here.
                # Use foreground ratio if available, otherwise approximate from shape_area.
                # In the segmentation_report.json, there might be per-image foreground_ratio.
                # Let's read from the report directly.
                pass
        # Simpler: use metrics CSV and just annotate the improvement
        axes[1].axis("off")
        textstr = (
            "Key Observations:\n\n"
            "1. Full-image baseline (no segmentation)\n"
            "   discards shape features entirely.\n\n"
            "2. BUSAT segmentation yields the highest\n"
            "   AUC across all three classifiers.\n\n"
            "3. The AUC gap between 'full' and 'busat'\n"
            f"   ranges from +{min([b - a for a, b in zip(auc_full, auc_busat)]):.3f} to "
            f"+{max([b - a for a, b in zip(auc_full, auc_busat)]):.3f}.\n\n"
            "4. This demonstrates that inaccurate\n"
            "   segmentation degrades classification\n"
            "   by including non-lesion tissue."
        )
        axes[1].text(0.1, 0.5, textstr, transform=axes[1].transAxes, fontsize=12,
                     verticalalignment="center", fontfamily="monospace",
                     bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    else:
        axes[1].axis("off")

    fig.suptitle("Part 2: Segmentation Error Impact on Classification", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    savefig("fig2e_part2_segmentation_error_impact.png", fig)


# ---------------------------------------------------------------------------
# Part 3
# ---------------------------------------------------------------------------
def build_part3_figures():
    print("\n=== Part 3 figures ===")
    df_comp = pd.read_csv(PART3_COMP)

    # 3a. Comparison table rendered as figure
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.axis("tight")
    ax.axis("off")
    display_df = df_comp[["source", "experiment", "model", "accuracy_mean", "auc_mean"]].copy()
    display_df.columns = ["Source", "Experiment", "Model", "Accuracy", "AUC"]
    display_df["Accuracy"] = display_df["Accuracy"].round(3)
    display_df["AUC"] = display_df["AUC"].round(3)
    # Add source grouping colors
    table = ax.table(cellText=display_df.values, colLabels=display_df.columns,
                     cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.2)
    fig.suptitle("Part 3: Baseline vs Foundation Model Classification Comparison", fontsize=14, y=0.98)
    savefig("fig3a_part3_comparison_table.png", fig)

    # 3b. Best models ROC overlay (we reuse the generated PNGs by copying)
    # Just copy the best ones to report dir
    best_roc_files = [
        ("part3/roc/roc_compare_svm.png", "fig3b_part3_roc_svm_comparison.png"),
        ("part3/roc/roc_compare_rf.png", "fig3c_part3_roc_rf_comparison.png"),
        ("part2/roc_busat_svm.png", "fig3d_part2_best_busat_svm_roc.png"),
    ]
    for src_rel, dst_name in best_roc_files:
        src = ROOT / "outputs" / src_rel
        if src.exists():
            shutil.copy2(src, OUTDIR / dst_name)
            print(f"Copied {src} -> {OUTDIR / dst_name}")


# ---------------------------------------------------------------------------
# Copy existing notion panels
# ---------------------------------------------------------------------------
def copy_existing_panels():
    print("\n=== Copy existing panels ===")
    panels = {
        "part1_classical_grid.png": "panel_part1_classical.png",
        "part2_roc_grid.png": "panel_part2_roc.png",
        "part3_foundation_roc_grid.png": "panel_part3_foundation_roc.png",
        "part3_part1_sam2_grid.png": "panel_part3_sam2_part1.png",
        "part3_part2_sam2_examples.png": "panel_part3_sam2_part2.png",
    }
    for src_name, dst_name in panels.items():
        src = NOTIONDIR / src_name
        if src.exists():
            shutil.copy2(src, OUTDIR / dst_name)
            print(f"Copied {src_name} -> {dst_name}")


def copy_to_paper_figures():
    print("\n=== Copy figures to paper/figures ===")
    PAPER_FIGDIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(OUTDIR.glob("*.png")):
        shutil.copy2(path, PAPER_FIGDIR / path.name)
        print(f"Copied {path.name} -> paper/figures/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Building report figures...")
    build_part1_figures()
    build_part2_figures()
    build_part3_figures()
    copy_existing_panels()
    copy_to_paper_figures()
    print(f"\nAll figures written to {OUTDIR}")
    print("Done.")


if __name__ == "__main__":
    main()
