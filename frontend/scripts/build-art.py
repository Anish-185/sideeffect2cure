"""Derives the site's artwork from the cyanotype reference sheet.

The reference sheet is a flat scan: blue ink on a pale ground. Every asset
here is the same operation — crop a panel, turn the paper into alpha so the
ink can float on any background, then tint the ink to one of the site's blues.
The digit-art textures reuse the same alpha as a luminance map, so the ASCII
band and the illustration it came from always describe the same shape.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "art"
SOURCE = Path("/home/anish/front/ChatGPT Image Sep 8, 2026, 08_14_45 PM.png")

# Panel crops on the 1536x1024 reference sheet, left->right, top->bottom.
PANELS: dict[str, tuple[int, int, int, int]] = {
    "inflorescence": (10, 20, 350, 520),
    "lotus": (380, 60, 800, 520),
    "leaf-sprig": (810, 20, 1140, 500),
    "pavilion": (1180, 20, 1536, 560),
    "range": (0, 560, 370, 1010),
    "column": (470, 500, 720, 1010),
    "drupe-branch": (800, 520, 1150, 1010),
    "ridges": (1250, 570, 1536, 1010),
}

INK = (18, 58, 214)  # --s2c-blue
DEEP = (7, 22, 92)  # --s2c-navy


def _percentile(grey: Image.Image, frac: float) -> int:
    hist = grey.histogram()
    target = sum(hist) * frac
    run = 0
    for value, count in enumerate(hist):
        run += count
        if run >= target:
            return value
    return 255


def _density_mask(alpha: Image.Image, width: int) -> Image.Image:
    """Keep dense ink, drop sparse ink.

    The reference sheet has small captions set across it in another
    organisation's wording. They survive the flat-field because they are
    genuinely darker than their surroundings, but they are thin and isolated,
    so their neighbourhood average stays far below that of the illustrations.
    Blurring the alpha turns that difference into a separable signal.
    """
    local = alpha.filter(ImageFilter.GaussianBlur(width / 55))
    return local.point(lambda v: 255 if v > 46 else int(255 * max(v - 22, 0) / 24)).filter(
        ImageFilter.GaussianBlur(width / 220)
    )


def cutout(panel: Image.Image, tint: tuple[int, int, int], gamma: float = 0.85) -> Image.Image:
    """Paper -> alpha, ink -> flat tint.

    The sheet's ground is not pure white and vignettes toward the edges, so
    absolute luminance cannot separate ink from paper — the dark corners of a
    vignette read the same as light ink. A heavy blur estimates the local
    ground and is subtracted first (flat-field), leaving only what is darker
    than its own surroundings; levels on that residual then drop the paper and
    the sheet's faint baked-in lettering along with it.
    """
    grey = panel.convert("L")
    ground = grey.filter(ImageFilter.GaussianBlur(max(panel.width, panel.height) / 12))
    ink = ImageChops.subtract(ground, grey)

    floor = _percentile(ink, 0.55)
    ceiling = max(ink.getextrema()[1], floor + 1)
    span = ceiling - floor
    alpha = ink.point(lambda v: int(255 * min(max((v - floor) / span, 0.0), 1.0) ** gamma))
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    alpha = ImageEnhance.Contrast(alpha).enhance(1.35)
    alpha = ImageChops.multiply(alpha, _density_mask(alpha, panel.width))

    out = Image.new("RGBA", panel.size, tint + (255,))
    out.putalpha(alpha)
    return out


def digit_art(panel: Image.Image, cols: int = 150) -> str:
    """Render a panel as the digit texture used in the full-bleed blue bands.

    Supermemory's bands read as numerals because density, not glyph identity,
    carries the image — so darker ink maps to visually heavier digits and the
    lightest cells fall out to a space.
    """
    ramp = " 1372458960"
    grey = panel.convert("L")
    lo, hi = grey.getextrema()
    span = max(hi - lo, 1)
    rows = max(1, int(cols * grey.height / grey.width * 0.5))
    grey = grey.resize((cols, rows))
    px = grey.load()

    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            ink = 1 - (px[x, y] - lo) / span
            line.append(ramp[min(int(ink * len(ramp)), len(ramp) - 1)])
        lines.append("".join(line).rstrip())
    return "\n".join(lines)


def main() -> int:
    if not SOURCE.exists():
        print(f"reference sheet missing: {SOURCE}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    sheet = Image.open(SOURCE).convert("RGB")

    for name, box in PANELS.items():
        panel = sheet.crop(box)
        cutout(panel, INK).save(OUT / f"{name}.png")
        cutout(panel, DEEP, gamma=1.15).save(OUT / f"{name}-deep.png")

    for name in ("lotus", "inflorescence", "ridges", "drupe-branch"):
        art = digit_art(sheet.crop(PANELS[name]))
        (OUT / f"{name}.txt").write_text(art + "\n", encoding="utf-8")

    print(f"wrote {len(list(OUT.iterdir()))} files to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
