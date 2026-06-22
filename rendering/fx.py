from __future__ import annotations

import os
from typing import Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from config import BASE_DIR, CARD_SIZE, FRAME_SIZE, RARITY_STYLES
from rendering.fonts import get_bold_font


def safe_open_image(path: str, size: Tuple[int, int] = CARD_SIZE) -> Image.Image:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", size, (35, 35, 35, 255))
        ImageDraw.Draw(img).text((12, 12), "Imagen\ninválida", fill=(255, 255, 255, 255))
        return img


def apply_rarity_fx(card_rgba: Image.Image, color_rgba: Tuple) -> Image.Image:
    if color_rgba is None:
        return card_rgba
    w, h = card_rgba.size
    r, g, b, _ = color_rgba
    alpha = card_rgba.split()[-1]
    blurred = alpha.filter(ImageFilter.GaussianBlur(10))
    halo = ImageChops.subtract(blurred, alpha)
    halo_layer = Image.new("RGBA", (w, h), (r, g, b, 0))
    halo_layer.putalpha(halo)
    out = Image.alpha_composite(halo_layer, card_rgba)
    draw = ImageDraw.Draw(out)
    border_w = 6
    for i in range(border_w):
        draw.rectangle([i, i, w - 1 - i, h - 1 - i], outline=(r, g, b, 255))
    return out


def apply_frame_overlay(card_img: Image.Image, frame_meta: dict) -> Image.Image:
    if not frame_meta:
        return card_img
    rel = frame_meta.get("img")
    if not rel:
        return card_img

    full = os.path.join(BASE_DIR, "images", rel)
    card_rgba = card_img.convert("RGBA")
    if card_rgba.size != CARD_SIZE:
        try:
            card_rgba = card_rgba.resize(CARD_SIZE, Image.LANCZOS)
        except Exception:
            card_rgba = card_rgba.resize(CARD_SIZE)

    frame = safe_open_image(full, size=FRAME_SIZE).convert("RGBA")
    if frame.size != FRAME_SIZE:
        try:
            frame = frame.resize(FRAME_SIZE, Image.LANCZOS)
        except Exception:
            frame = frame.resize(FRAME_SIZE)

    out = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    ox = (FRAME_SIZE[0] - CARD_SIZE[0]) // 2
    oy = (FRAME_SIZE[1] - CARD_SIZE[1]) // 2
    out.paste(card_rgba, (ox, oy), card_rgba)
    return Image.alpha_composite(out, frame)


def rarity_panel_color(rarity: str) -> Tuple:
    base = RARITY_STYLES.get((rarity or "common").lower(), RARITY_STYLES["common"])
    r, g, b, _ = base
    return (r, g, b, 170)
