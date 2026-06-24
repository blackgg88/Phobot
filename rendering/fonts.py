from __future__ import annotations

import os
from PIL import ImageDraw, ImageFont
from config import BASE_DIR


def get_bold_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        os.path.join(BASE_DIR, "fonts", "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "arialbd.ttf",
    ]
    for p in candidates:
        if p.startswith("/") or p.startswith(BASE_DIR):
            if not os.path.isfile(p):
                continue
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    # último recurso: avisar en consola para que sea fácil de detectar
    import warnings
    warnings.warn(
        f"[Phobot] No se encontró ninguna fuente TTF. "
        f"Poné DejaVuSans-Bold.ttf en {os.path.join(BASE_DIR, 'fonts')}",
        stacklevel=2,
    )
    return ImageFont.load_default()


def draw_centered_text_with_outline(
    draw: ImageDraw.ImageDraw,
    text: str,
    x_center: int,
    y: int,
    font,
    fill,
    outline=(0, 0, 0, 255),
    stroke: int = 2,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    x = x_center - (w // 2)
    for dx in range(-stroke, stroke + 1):
        for dy in range(-stroke, stroke + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def fit_font_to_width(draw: ImageDraw.ImageDraw, text: str, max_width: int,
                      start_size: int, min_size: int = 12) -> ImageFont.FreeTypeFont:
    text = str(text or "")
    size = start_size
    while size > min_size:
        font = get_bold_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 1
    return get_bold_font(min_size)
