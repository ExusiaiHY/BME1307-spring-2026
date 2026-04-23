from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "notion"

BG = "#f7f7f5"
CARD_BG = "#ffffff"
BORDER = "#d9d9d6"
TEXT = "#222222"
SUBTEXT = "#666666"


@dataclass(frozen=True)
class PanelItem:
    label: str
    path: Path


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            ]
        )
    else:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Supplemental/Helvetica.ttc",
            ]
        )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fit_image(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGB", size, CARD_BG)
    fitted = ImageOps.contain(image.convert("RGB"), size)
    x = (size[0] - fitted.width) // 2
    y = (size[1] - fitted.height) // 2
    canvas.paste(fitted, (x, y))
    return canvas


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def build_grid(
    output_path: Path,
    items: Iterable[PanelItem],
    title: str,
    subtitle: str,
    cols: int,
    image_box: tuple[int, int],
) -> None:
    items = list(items)
    rows = (len(items) + cols - 1) // cols

    outer_pad = 28
    gap_x = 18
    gap_y = 22
    title_gap = 22
    caption_h = 42
    card_pad = 10
    title_font = load_font(28, bold=True)
    subtitle_font = load_font(16)
    caption_font = load_font(15)

    card_w = image_box[0] + card_pad * 2
    card_h = image_box[1] + caption_h + card_pad * 2
    width = outer_pad * 2 + cols * card_w + (cols - 1) * gap_x
    header_h = 76
    height = outer_pad * 2 + header_h + title_gap + rows * card_h + (rows - 1) * gap_y

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((outer_pad, outer_pad), title, fill=TEXT, font=title_font)
    draw.text((outer_pad, outer_pad + 38), subtitle, fill=SUBTEXT, font=subtitle_font)

    start_y = outer_pad + header_h + title_gap

    for idx, item in enumerate(items):
        row = idx // cols
        col = idx % cols
        x0 = outer_pad + col * (card_w + gap_x)
        y0 = start_y + row * (card_h + gap_y)
        x1 = x0 + card_w
        y1 = y0 + card_h
        draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=CARD_BG, outline=BORDER, width=2)

        image = Image.open(item.path)
        fitted = fit_image(image, image_box)
        canvas.paste(fitted, (x0 + card_pad, y0 + card_pad))

        caption_width = card_w - card_pad * 2
        lines = wrap_text(draw, item.label, caption_font, caption_width)
        caption_y = y0 + card_pad + image_box[1] + 8
        for line in lines[:2]:
            draw.text((x0 + card_pad, caption_y), line, fill=TEXT, font=caption_font)
            caption_y += 18

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)


def rel(path: str) -> Path:
    return PROJECT_ROOT / path


def main() -> None:
    build_grid(
        OUTPUT_DIR / "part1_classical_grid.png",
        [
            PanelItem("B1 gain 83 dB", rel("outputs/part1/overlays/p1_20260421_144838_398_overlay.png")),
            PanelItem("B2 gain 73 dB", rel("outputs/part1/overlays/p1_20260421_144929_380_overlay.png")),
            PanelItem("B3", rel("outputs/part1/overlays/p1_20260421_144951_958_overlay.png")),
            PanelItem("B4", rel("outputs/part1/overlays/p1_20260421_145121_293_overlay.png")),
            PanelItem("B5", rel("outputs/part1/overlays/p1_20260421_145210_894_overlay.png")),
            PanelItem("B6", rel("outputs/part1/overlays/p1_20260421_145300_800_overlay.png")),
            PanelItem("Color 1", rel("outputs/part1/overlays/p1_20260421_145450_004_overlay.png")),
            PanelItem("Color 2", rel("outputs/part1/overlays/p1_20260421_145539_147_overlay.png")),
        ],
        title="Part 1 Classical Segmentation",
        subtitle="8 overlays; all diameters fall inside the 4.3-7.7 mm literature range.",
        cols=4,
        image_box=(230, 288),
    )

    build_grid(
        OUTPUT_DIR / "part2_roc_grid.png",
        [
            PanelItem("Full + SVM", rel("outputs/part2/roc_full_svm.png")),
            PanelItem("Refined + SVM", rel("outputs/part2/roc_refined_svm.png")),
            PanelItem("BUSAT + SVM", rel("outputs/part2/roc_busat_svm.png")),
            PanelItem("BUSAT + RF", rel("outputs/part2/roc_busat_rf.png")),
        ],
        title="Part 2 Classification ROC",
        subtitle="Representative baseline curves; BUSAT stays strongest overall.",
        cols=2,
        image_box=(360, 360),
    )

    build_grid(
        OUTPUT_DIR / "part3_part1_sam2_grid.png",
        [
            PanelItem("Fallback fail 1", rel("outputs/part3/overlays/part1_sam2/p1_20260421_144838_398_overlay.png")),
            PanelItem("Fallback fail 2", rel("outputs/part3/overlays/part1_sam2/p1_20260421_144929_380_overlay.png")),
            PanelItem("Hough prompt 1", rel("outputs/part3/overlays/part1_sam2/p1_20260421_144951_958_overlay.png")),
            PanelItem("Hough prompt 2", rel("outputs/part3/overlays/part1_sam2/p1_20260421_145121_293_overlay.png")),
            PanelItem("Hough prompt 3", rel("outputs/part3/overlays/part1_sam2/p1_20260421_145210_894_overlay.png")),
            PanelItem("Hough prompt 4", rel("outputs/part3/overlays/part1_sam2/p1_20260421_145300_800_overlay.png")),
            PanelItem("Hough prompt 5", rel("outputs/part3/overlays/part1_sam2/p1_20260421_145450_004_overlay.png")),
            PanelItem("Hough prompt 6", rel("outputs/part3/overlays/part1_sam2/p1_20260421_145539_147_overlay.png")),
        ],
        title="Part 3 SAM2 on Part 1",
        subtitle="Two crop-center fallback failures; six Hough-prompt cases land in-range.",
        cols=4,
        image_box=(230, 288),
    )

    build_grid(
        OUTPUT_DIR / "part3_part2_sam2_examples.png",
        [
            PanelItem("Low IoU: id 5", rel("outputs/part3/overlays/part2_sam2/5_overlay.png")),
            PanelItem("Tiny mask fail: id 26", rel("outputs/part3/overlays/part2_sam2/26_overlay.png")),
            PanelItem("Low IoU: id 117", rel("outputs/part3/overlays/part2_sam2/117_overlay.png")),
            PanelItem("High IoU: id 18", rel("outputs/part3/overlays/part2_sam2/18_overlay.png")),
            PanelItem("High IoU: id 20", rel("outputs/part3/overlays/part2_sam2/20_overlay.png")),
            PanelItem("High IoU: id 82", rel("outputs/part3/overlays/part2_sam2/82_overlay.png")),
        ],
        title="Part 3 SAM2 on Part 2",
        subtitle="Representative low- and high-IoU examples from the 120-image run.",
        cols=3,
        image_box=(300, 300),
    )

    build_grid(
        OUTPUT_DIR / "part3_foundation_roc_grid.png",
        [
            PanelItem("BiomedCLIP + SVM", rel("outputs/part3/roc/roc_biomedclip_svm.png")),
            PanelItem("Compare: LogReg", rel("outputs/part3/roc/roc_compare_logreg.png")),
            PanelItem("Compare: SVM", rel("outputs/part3/roc/roc_compare_svm.png")),
            PanelItem("Compare: RF", rel("outputs/part3/roc/roc_compare_rf.png")),
        ],
        title="Part 3 Foundation-Model ROC",
        subtitle="Best FM result is BiomedCLIP + SVM; still slightly below BUSAT.",
        cols=2,
        image_box=(380, 345),
    )


if __name__ == "__main__":
    main()
