from __future__ import annotations

import os
from typing import List, Optional

from PIL import Image, ImageDraw

from config import BASE_DIR, DEFAULT_MUSEUM_BG, MUSEUM_BACKGROUNDS
from rendering.cards import render_single_card_image, resize_to_fit_rgba
from rendering.fonts import get_bold_font, draw_centered_text_with_outline

MUSEUM2_SLOTS = 11

# Layout escalonado: 4 + 3 + 4
_ROWS = [4, 3, 4]

def _slot_positions(card_w: int, card_h: int, pad: int, top_pad: int):
    """Devuelve lista de (x, y) para los 11 slots en layout escalonado."""
    positions = []
    gap = pad
    for row_idx, count in enumerate(_ROWS):
        y = top_pad + row_idx * (card_h + gap)
        if count == 4:
            # fila normal: 4 cartas alineadas a la izquierda
            total_w = count * card_w + (count - 1) * gap
            x_start = pad
        else:
            # fila de 3: centrada y desplazada (efecto escalonado)
            total_w = count * card_w + (count - 1) * gap
            # total canvas width: pad + 4*(card_w+gap) - gap + pad
            canvas_w = 2 * pad + 4 * card_w + 3 * gap
            x_start = (canvas_w - total_w) // 2
        for i in range(count):
            x = x_start + i * (card_w + gap)
            positions.append((x, y))
    return positions


def build_museum2_image(
    cards_db: dict,
    inst_list: List[Optional[dict]],
    bg_key: str = DEFAULT_MUSEUM_BG,
) -> Image.Image:
    card_w, card_h = 210, 290
    pad     = 22
    top_pad = 52   # espacio para el título

    bg_key = (bg_key or DEFAULT_MUSEUM_BG).strip().lower()

    canvas_w = 2 * pad + 4 * card_w + 3 * pad
    canvas_h = top_pad + 3 * card_h + 2 * pad + pad

    # fondo
    if bg_key.startswith("custom:"):
        bg_id = bg_key[7:]
        from core.museum_bgs import load_museum_bg_catalog
        meta = load_museum_bg_catalog().get(bg_id, {})
        img_rel = meta.get("img", "")
        full = os.path.join(BASE_DIR, "images", img_rel)
        try:
            bg_img = Image.open(full).convert("RGBA").resize((canvas_w, canvas_h), Image.LANCZOS)
            canvas = bg_img.copy()
        except Exception:
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (18, 18, 18, 255))
    else:
        bg = MUSEUM_BACKGROUNDS.get(bg_key, MUSEUM_BACKGROUNDS[DEFAULT_MUSEUM_BG])
        canvas = Image.new("RGBA", (canvas_w, canvas_h), bg)

    draw = ImageDraw.Draw(canvas)
    font = get_bold_font(32)
    draw_centered_text_with_outline(draw, "MUSEO II", canvas_w // 2, 8, font, (255, 255, 255, 255), stroke=2)

    inst_list = (inst_list or [])[:MUSEUM2_SLOTS]
    while len(inst_list) < MUSEUM2_SLOTS:
        inst_list.append(None)

    positions = _slot_positions(card_w, card_h, pad, top_pad)

    for i, (x, y) in enumerate(positions):
        inst = inst_list[i]
        if inst:
            img = resize_to_fit_rgba(render_single_card_image(cards_db, inst), (card_w, card_h))
            canvas.paste(img, (x, y), img)
        else:
            ph = Image.new("RGBA", (card_w, card_h), (35, 35, 35, 255))
            d  = ImageDraw.Draw(ph)
            d.rounded_rectangle([8, 8, card_w - 8, card_h - 8], radius=18, outline=(90, 90, 90, 255), width=4)
            f2 = get_bold_font(22)
            draw_centered_text_with_outline(d, "VACÍO", card_w // 2, card_h // 2 - 14, f2, (200, 200, 200, 255), stroke=2)
            canvas.paste(ph, (x, y), ph)

    return canvas
