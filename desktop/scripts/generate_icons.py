# -*- coding: utf-8 -*-
"""生成 X-Agent 桌面端 Tauri 图标集（占位但真实有效的图标文件）。

产出 desktop/icons/ 下：
  - 32x32.png / 128x128.png / 128x128@2x.png : Tauri bundle 图标
  - icon.png                                 : 系统托盘图标
  - icon.ico                                 : Windows 安装包/窗口图标（多尺寸）
  - icon.icns                                : macOS bundle 图标（手工拼装，内嵌 PNG）

用法: python desktop/scripts/generate_icons.py
依赖: Pillow（托管 Python 运行时自带）
"""

from __future__ import annotations

import io
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = Path(__file__).resolve().parents[1] / "icons"

# 低饱和暖深底 + 高对比 "X" 字样（符合项目视觉基调，避免高饱和渐变）
BG_COLOR = (43, 39, 36, 255)        # 暖灰黑
FG_COLOR = (240, 230, 216, 255)     # 暖白
ACCENT_COLOR = (196, 130, 84, 255)  # 低饱和赭橙


def rounded_rect_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    radius = int(size * radius_ratio)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make_icon(size: int) -> Image.Image:
    """生成单个尺寸的应用图标：圆角深底 + 居中字母 X。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 圆角底
    base = Image.new("RGBA", (size, size), BG_COLOR)
    mask = rounded_rect_mask(size)
    img.paste(base, (0, 0), mask)

    # 字母 X：优先 TrueType 字体，找不到则回退内置位图字体放大
    glyph = "X"
    font_size = int(size * 0.62)
    font = None
    for candidate in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            font = ImageFont.truetype(candidate, font_size)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), glyph, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pos = ((size - text_w) / 2 - bbox[0], (size - text_h) / 2 - bbox[1])
    draw.text(pos, glyph, font=font, fill=FG_COLOR)

    # 右下小圆点作为点缀
    dot_r = max(2, int(size * 0.045))
    dot_x = int(size * 0.72)
    dot_y = int(size * 0.72)
    draw.ellipse([dot_x, dot_y, dot_x + dot_r * 2, dot_y + dot_r * 2], fill=ACCENT_COLOR)
    return img


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_icns(entries: dict[bytes, bytes]) -> bytes:
    """把若干 PNG 字节按 icns 容器格式拼装（类型码 -> PNG 数据）。"""
    body = b""
    for type_code, png_data in entries.items():
        body += type_code + struct.pack(">I", len(png_data) + 8) + png_data
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    icon_32 = make_icon(32)
    icon_128 = make_icon(128)
    icon_256 = make_icon(256)

    # PNG 图标（bundle + 托盘）
    icon_32.save(ICONS_DIR / "32x32.png")
    icon_128.save(ICONS_DIR / "128x128.png")
    icon_256.save(ICONS_DIR / "128x128@2x.png")
    icon_256.save(ICONS_DIR / "icon.png")  # systemTray.iconPath

    # Windows ICO（多尺寸合一）
    icon_256.save(
        ICONS_DIR / "icon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    # macOS ICNS（手工拼装，ic07=128x128 PNG, ic08=256x256 PNG, ic11=32x32@2x, ic12=64x64@2x）
    icns = build_icns({
        b"ic07": to_png_bytes(icon_128),
        b"ic08": to_png_bytes(icon_256),
        b"ic11": to_png_bytes(icon_32),
        b"ic12": to_png_bytes(make_icon(64)),
    })
    (ICONS_DIR / "icon.icns").write_bytes(icns)

    for f in sorted(ICONS_DIR.iterdir()):
        print(f"  {f.name}: {f.stat().st_size} bytes")
    print("Icons generated at", ICONS_DIR)


if __name__ == "__main__":
    main()
