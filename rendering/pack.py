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


def create_drop_image(dropped_cards: List[dict]) -> Image.Image:
    """Render drop cards: full-height photo with rarity gradient + text overlay at the bottom."""
    card_w, card_h = 300, 420
    gap     = 20
    total_w = card_w * len(dropped_cards) + gap * (len(dropped_cards) - 1)
    pack    = Image.new("RGBA", (total_w, card_h), (15, 15, 15, 255))

    for i, c in enumerate(dropped_cards):
        rarity       = (c.get("rarity", "common") or "common").lower()
        name         = str(c.get("name", "???")).upper()
        collection   = str(c.get("collection", "???")).upper()
        display_code = str(c.get("display_code", "G·???"))
        path         = c["img"]

        full = os.path.join(BASE_DIR, "images", path)
        card = safe_open_image(full, size=(card_w, card_h)).resize((card_w, card_h))
        card = apply_rarity_fx(card, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        # gradient overlay: strong at base, fades out before the midpoint
        r, g, b, _ = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])
        grad_h  = int(card_h * 0.45)   # covers bottom 45%, gone before midpoint
        overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for y in range(grad_h):
            # exponential curve: nearly transparent at top, very opaque at base
            t     = y / (grad_h - 1)          # 0 at top of gradient, 1 at bottom
            alpha = int(235 * (t ** 1.8))
            ov_draw.line(
                [(0, card_h - grad_h + y), (card_w - 1, card_h - grad_h + y)],
                fill=(r, g, b, alpha),
            )
        card = Image.alpha_composite(card, overlay)

        # text on top of gradient
        draw   = ImageDraw.Draw(card)
        center = card_w // 2
        max_tw = card_w - 20

        font_code   = get_bold_font(16)
        font_name   = fit_font_to_width(draw, name,       max_tw, 26, min_size=13)
        font_series = fit_font_to_width(draw, collection, max_tw, 18, min_size=11)

        # code badge: small dark pill in top-left anchored to the border
        code_bbox = draw.textbbox((0, 0), display_code, font=font_code)
        code_w    = code_bbox[2] - code_bbox[0]
        code_h    = code_bbox[3] - code_bbox[1]
        pad_x, pad_y = 8, 5
        badge_x1 = 6           # flush with the rarity border
        badge_y1 = 6
        badge_x2 = badge_x1 + code_w + pad_x * 2
        badge_y2 = badge_y1 + code_h + pad_y * 2
        draw.rounded_rectangle(
            [badge_x1, badge_y1, badge_x2, badge_y2],
            radius=6, fill=(10, 10, 10, 200),
        )
        draw.text((badge_x1 + pad_x, badge_y1 + pad_y - code_bbox[1]),
                  display_code, font=font_code, fill=(220, 220, 220, 255))

        draw_centered_text_with_outline(draw, name,       center, card_h - 80, font_name,   (255, 255, 255, 255), stroke=2)
        draw_centered_text_with_outline(draw, collection, center, card_h - 44, font_series, (215, 215, 215, 255), stroke=1)

        x = i * (card_w + gap)
        pack.paste(card, (x, 0), card)

    return pack
