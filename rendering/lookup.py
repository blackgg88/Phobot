from __future__ import annotations

import os
from typing import List

from PIL import Image, ImageDraw

from config import BASE_DIR, RARITY_STYLES
from rendering.cards import render_single_card_image
from rendering.fonts import get_bold_font, draw_centered_text_with_outline, fit_font_to_width

BG      = (18, 18, 18, 255)
PANEL   = (30, 30, 30, 255)
WHITE   = (255, 255, 255, 255)
GRAY    = (160, 160, 160, 255)
GRAY2   = (100, 100, 100, 255)

CARD_W, CARD_H   = 280, 392   # carta original
THUMB_W, THUMB_H = 190, 266   # tokens
PAD  = 20
COLS = 3


def build_plu_image(
    cards_db: dict, *, collection: str, name: str, token_imgs: List[str]
) -> Image.Image:
    meta   = (cards_db.get(collection) or {}).get(name, {})
    rarity = (meta.get("rarity") or "common").lower()
    rcolor = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])
    r, g, b, _ = rcolor

    # ── Renderizar carta original ────────────────────────
    base_inst = {"collection": collection, "name": name, "rarity": rarity,
                 "value": None, "code": ""}
    original = render_single_card_image(cards_db, base_inst).resize(
        (CARD_W, CARD_H), Image.LANCZOS
    )

    # ── Renderizar tokens ────────────────────────────────
    thumbs = []
    for img_rel in token_imgs:
        inst = {"collection": collection, "name": name, "rarity": rarity,
                "value": None, "code": "", "img": img_rel, "is_token": True}
        thumbs.append(
            render_single_card_image(cards_db, inst).resize(
                (THUMB_W, THUMB_H), Image.LANCZOS
            )
        )

    # ── Calcular dimensiones del canvas ─────────────────
    header_h = 80

    # columna izquierda: carta original
    LABEL_H = 28   # espacio para el texto "CARTA ORIGINAL" sobre la carta
    left_w  = CARD_W + PAD * 2
    left_h  = header_h + LABEL_H + CARD_H + PAD

    # columna derecha: tokens en grilla
    token_rows = max(1, (len(thumbs) + COLS - 1) // COLS)
    right_inner_w = COLS * THUMB_W + (COLS - 1) * PAD
    right_w = right_inner_w + PAD * 2
    right_h = header_h + LABEL_H + token_rows * THUMB_H + (token_rows - 1) * PAD + PAD

    total_w = left_w + right_w
    total_h = max(left_h, right_h)

    canvas = Image.new("RGBA", (total_w, total_h), BG)
    d      = ImageDraw.Draw(canvas)

    # ── Línea de color de rareza arriba ─────────────────
    d.rectangle([0, 0, total_w, 4], fill=(r, g, b, 255))

    # ── Header: nombre y colección ───────────────────────
    f_name = fit_font_to_width(d, name.upper(),       total_w - PAD * 2, 32, min_size=16)
    f_coll = fit_font_to_width(d, collection.upper(), total_w - PAD * 2, 18, min_size=12)
    d.text((PAD, 10), name.upper(),        font=f_name, fill=WHITE)
    d.text((PAD, 10 + 36), collection.upper(), font=f_coll, fill=(r, g, b, 220))

    # separador horizontal bajo el header
    d.rectangle([0, header_h - 4, total_w, header_h], fill=PANEL)

    # ── Carta original (izquierda) ───────────────────────
    label_font = get_bold_font(15)
    d.text((PAD, header_h + 6), "CARTA ORIGINAL", font=label_font, fill=GRAY2)
    canvas.paste(original, (PAD, header_h + 28), original)

    # ── Tokens (derecha) ─────────────────────────────────
    rx = left_w
    tok_label = f"TOKENS  ({len(thumbs)})"
    d.text((rx + PAD, header_h + 6), tok_label, font=label_font, fill=GRAY2)

    if thumbs:
        num_font = get_bold_font(16)
        for i, thumb in enumerate(thumbs):
            row = i // COLS
            col = i % COLS
            tx  = rx + PAD + col * (THUMB_W + PAD)
            ty  = header_h + 28 + row * (THUMB_H + PAD)
            canvas.paste(thumb, (tx, ty), thumb)
            # número del token
            d.rounded_rectangle([tx + 6, ty + 6, tx + 42, ty + 30],
                                 radius=8, fill=(0, 0, 0, 180))
            d.text((tx + 12, ty + 8), f"T{i + 1}", font=num_font, fill=WHITE)
    else:
        f_empty = get_bold_font(17)
        mid_x = rx + right_w // 2
        mid_y = header_h + 28 + THUMB_H // 2
        draw_centered_text_with_outline(
            d, "Sin tokens", mid_x, mid_y, f_empty, GRAY2, stroke=0
        )

    # línea divisoria vertical
    d.rectangle([left_w - 2, header_h, left_w, total_h], fill=PANEL)

    return canvas
