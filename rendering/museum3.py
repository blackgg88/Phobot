from __future__ import annotations

import os
from typing import List, Optional

from PIL import Image, ImageDraw

from config import BASE_DIR, DEFAULT_MUSEUM_BG, MUSEUM_BACKGROUNDS
from rendering.cards import render_single_card_image, resize_to_fit_rgba
from rendering.fonts import get_bold_font, draw_centered_text_with_outline

MUSEUM3_SLOTS = 12

# Layout en forma de marco/cuadro:
#  [1]  [2]  [3]  [4]
#  [5]            [6]
#  [7]            [8]
#  [9] [10] [11] [12]

_CARD_W  = 155
_CARD_H  = 215
_GAP     = 18
_PAD     = 24
_TOP_PAD = 54   # espacio para el título


def _slot_positions():
    cw, ch, g, pad, top = _CARD_W, _CARD_H, _GAP, _PAD, _TOP_PAD
    positions = []

    def row_x(col): return pad + col * (cw + g)
    def row_y(row): return top + pad + row * (ch + g)

    # Fila 0 — 4 cartas
    for col in range(4):
        positions.append((row_x(col), row_y(0)))   # slots 1-4

    # Filas 1 y 2 — solo columnas 0 y 3
    for row in (1, 2):
        positions.append((row_x(0), row_y(row)))   # slots 5, 7
        positions.append((row_x(3), row_y(row)))   # slots 6, 8

    # Fila 3 — 4 cartas
    for col in range(4):
        positions.append((row_x(col), row_y(3)))   # slots 9-12

    return positions


def _canvas_size():
    cw, ch, g, pad, top = _CARD_W, _CARD_H, _GAP, _PAD, _TOP_PAD
    w = 2 * pad + 4 * cw + 3 * g
    h = top + pad + 4 * ch + 3 * g + pad
    return w, h


def build_museum3_image(
    cards_db: dict,
    inst_list: List[Optional[dict]],
    bg_key: str = DEFAULT_MUSEUM_BG,
) -> Image.Image:
    cw, ch = _CARD_W, _CARD_H
    canvas_w, canvas_h = _canvas_size()
    bg_key = (bg_key or DEFAULT_MUSEUM_BG).strip().lower()

    # fondo
    if bg_key.startswith("custom:"):
        bg_id = bg_key[7:]
        from core.museum_bgs import load_museum_bg_catalog
        meta    = load_museum_bg_catalog().get(bg_id, {})
        img_rel = meta.get("img", "")
        full    = os.path.join(BASE_DIR, "images", img_rel)
        try:
            bg_img = Image.open(full).convert("RGBA").resize((canvas_w, canvas_h), Image.LANCZOS)
            canvas = bg_img.copy()
        except Exception:
            canvas = Image.new("RGBA", (canvas_w, canvas_h), (18, 18, 18, 255))
    else:
        bg     = MUSEUM_BACKGROUNDS.get(bg_key, MUSEUM_BACKGROUNDS[DEFAULT_MUSEUM_BG])
        canvas = Image.new("RGBA", (canvas_w, canvas_h), bg)

    draw = ImageDraw.Draw(canvas)

    # decoración del centro vacío: marco interior sutil
    cx0 = _PAD + _CARD_W + _GAP
    cy0 = _TOP_PAD + _PAD + _CARD_H + _GAP
    cx1 = cx0 + 2 * _CARD_W + _GAP
    cy1 = cy0 + 2 * _CARD_H + _GAP
    draw.rounded_rectangle([cx0, cy0, cx1, cy1], radius=22,
                            outline=(255, 255, 255, 35), width=3)

    # título
    font = get_bold_font(32)
    draw_centered_text_with_outline(draw, "MUSEO III", canvas_w // 2, 10, font,
                                    (255, 255, 255, 255), stroke=2)

    inst_list = (inst_list or [])[:MUSEUM3_SLOTS]
    while len(inst_list) < MUSEUM3_SLOTS:
        inst_list.append(None)

    positions = _slot_positions()
    for i, (x, y) in enumerate(positions):
        inst = inst_list[i]
        if inst:
            img = resize_to_fit_rgba(render_single_card_image(cards_db, inst), (cw, ch))
            canvas.paste(img, (x, y), img)
        else:
            ph = Image.new("RGBA", (cw, ch), (35, 35, 35, 255))
            d  = ImageDraw.Draw(ph)
            d.rounded_rectangle([6, 6, cw - 6, ch - 6], radius=16,
                                 outline=(90, 90, 90, 255), width=3)
            f2 = get_bold_font(20)
            draw_centered_text_with_outline(d, "VACÍO", cw // 2, ch // 2 - 12,
                                            f2, (200, 200, 200, 255), stroke=2)
            canvas.paste(ph, (x, y), ph)

    return canvas
