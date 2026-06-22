from __future__ import annotations

import os
from typing import List

from PIL import Image, ImageDraw

from config import BASE_DIR, RARITY_STYLES
from core.cards import rarity_es_upper
from rendering.fonts import (
    get_bold_font, draw_centered_text_with_outline, fit_font_to_width,
)
from rendering.fx import apply_rarity_fx, safe_open_image, rarity_panel_color
from rendering.cards import draw_value_tag_on_card, draw_token_label_on_card


def create_pack_image(pulled_cards: List[dict]) -> Image.Image:
    card_w, card_h = 300, 420
    padding = 35
    label_h = 128
    max_text_w = card_w - 28

    total_w = card_w * len(pulled_cards) + padding * (len(pulled_cards) - 1)
    total_h = card_h + label_h
    pack    = Image.new("RGBA", (total_w, total_h), (15, 15, 15, 255))
    draw    = ImageDraw.Draw(pack)

    for i, c in enumerate(pulled_cards):
        rarity     = (c.get("rarity", "common") or "common").lower()
        name       = str(c.get("name", "???"))
        collection = str(c.get("collection", "???"))
        path       = c["img"]

        full = os.path.join(BASE_DIR, "images", path)
        card = safe_open_image(full, size=(card_w, card_h)).resize((card_w, card_h))
        card = apply_rarity_fx(card, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        if c.get("is_token"):
            try:
                draw_token_label_on_card(card)
            except Exception:
                pass
        elif "value" in c and c["value"] is not None:
            try:
                draw_value_tag_on_card(card, f"P{int(c['value'])}", rarity)
            except Exception:
                pass

        x = i * (card_w + padding)
        pack.paste(card, (x, 0), card)

        panel_color = rarity_panel_color(rarity)
        draw.rounded_rectangle(
            [x + 6, card_h + 8, x + card_w - 6, card_h + label_h - 8],
            radius=16, fill=panel_color,
        )

        center = x + card_w // 2
        font_name   = fit_font_to_width(draw, name, max_text_w, 28, min_size=14)
        font_series = fit_font_to_width(draw, collection, max_text_w, 22, min_size=12)
        font_rarity = fit_font_to_width(draw, rarity_es_upper(rarity), max_text_w, 22, min_size=12)

        draw_centered_text_with_outline(draw, name,                center, card_h + 16,  font_name,   (255, 255, 255, 255), stroke=2)
        draw_centered_text_with_outline(draw, collection,          center, card_h + 52,  font_series, (240, 240, 240, 255), stroke=2)
        draw_centered_text_with_outline(draw, rarity_es_upper(rarity), center, card_h + 88, font_rarity,
                                        (0, 0, 0, 255), outline=(255, 255, 255, 255), stroke=2)

    return pack
