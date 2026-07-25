#!/usr/bin/env python3
"""Generate X-Agent extension icons (real PNG files).

Generates the icon sizes referenced by extension/manifest.json:
  - images/icon-16.png   (16x16)
  - images/icon-48.png   (48x48)
  - images/icon-128.png  (128x128)

Design: rounded-square tile with a stylized white "X" glyph.
Rendered at 4x supersampling and downscaled for clean anti-aliasing.

Usage (from repository root):
    ./venv/Scripts/python.exe extension/scripts/generate_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

EXTENSION_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = EXTENSION_ROOT / "images"

# Low-saturation warm slate palette (matches project visual policy).
BG_COLOR = (62, 84, 102, 255)       # slate blue-gray
BG_COLOR_DARK = (46, 64, 79, 255)   # darker shade for subtle vertical gradient
GLYPH_COLOR = (245, 241, 234, 255)  # warm off-white
ACCENT_COLOR = (222, 164, 92, 255)  # muted amber accent dot

SIZES = (16, 48, 128)
SUPERSAMPLE = 4


def rounded_rectangle_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def draw_icon(size: int) -> Image.Image:
    s = size * SUPERSAMPLE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Background: subtle vertical gradient inside a rounded-square mask.
    bg = Image.new("RGBA", (s, s))
    bg_draw = ImageDraw.Draw(bg)
    for y in range(s):
        t = y / max(s - 1, 1)
        color = tuple(
            round(BG_COLOR[i] + (BG_COLOR_DARK[i] - BG_COLOR[i]) * t)
            for i in range(3)
        ) + (255,)
        bg_draw.line([(0, y), (s, y)], fill=color)
    mask = rounded_rectangle_mask(s, radius=round(s * 0.22))
    img.paste(bg, (0, 0), mask)

    draw = ImageDraw.Draw(img)

    # Stylized "X" glyph: two diagonal strokes with rounded caps.
    stroke = max(round(s * 0.14), 2)
    margin = s * 0.28
    x0, y0 = margin, margin
    x1, y1 = s - margin, s - margin

    def stroke_line(p0, p1):
        draw.line([p0, p1], fill=GLYPH_COLOR, width=stroke)
        r = stroke / 2
        for px, py in (p0, p1):
            draw.ellipse((px - r, py - r, px + r, py + r), fill=GLYPH_COLOR)

    stroke_line((x0, y0), (x1, y1))
    stroke_line((x0, y1), (x1, y0))

    # Amber accent dot at the glyph center (the "agent" focal point).
    dot_r = max(stroke * 0.62, 1.5)
    cx = cy = s / 2
    draw.ellipse((cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r), fill=ACCENT_COLOR)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        icon = draw_icon(size)
        out = IMAGES_DIR / f"icon-{size}.png"
        icon.save(out, format="PNG", optimize=True)
        print(f"generated {out} ({size}x{size})")


if __name__ == "__main__":
    main()
