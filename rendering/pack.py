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


def _rounded_card(card: Image.Image, radius: int = 18) -> Image.Image:
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=radius, fill=255)
    out = card.copy().convert("RGBA")
    out.putalpha(mask)
    return out


def _crop_fill(path: str, card_w: int, card_h: int) -> Image.Image:
    src = safe_open_image(path, size=(card_w, card_h))
    sw, sh = src.size
    scale = max(card_w / sw, card_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    src = src.resize((nw, nh), Image.LANCZOS)
    cx, cy = (nw - card_w) // 2, (nh - card_h) // 2
    return src.crop((cx, cy, cx + card_w, cy + card_h)).convert("RGBA")


def create_pack_image(pulled_cards: List[dict]) -> Image.Image:
    card_w, card_h = 300, 420
    padding = 35
    corner_r = 18
    max_text_w = card_w - 28

    total_w = card_w * len(pulled_cards) + padding * (len(pulled_cards) - 1)
    total_h = card_h

    pack = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 255))
    bg_draw = ImageDraw.Draw(pack)
    for y in range(total_h):
        t = y / (total_h - 1)
        v = int(12 + 28 * t)
        bg_draw.line([(0, y), (total_w - 1, y)], fill=(v, v, v + 8, 255))

    draw = ImageDraw.Draw(pack)

    for i, c in enumerate(pulled_cards):
        rarity     = (c.get("rarity", "common") or "common").lower()
        name       = str(c.get("name", "???")).upper()
        collection = str(c.get("collection", "???")).upper()
        path       = c["img"]

        full = os.path.join(BASE_DIR, "images", path)
        card = _crop_fill(full, card_w, card_h)
        card = apply_rarity_fx(card, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        r, g, b, _ = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])
        grad_h = int(card_h * 0.45)
        overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for y in range(grad_h):
            t = y / (grad_h - 1)
            alpha = int(235 * (t ** 1.8))
            ov_draw.line([(0, card_h - grad_h + y), (card_w - 1, card_h - grad_h + y)], fill=(r, g, b, alpha))
        card = Image.alpha_composite(card, overlay)

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

        card_draw = ImageDraw.Draw(card)
        center = card_w // 2
        font_name   = fit_font_to_width(card_draw, name, max_text_w, 26, min_size=13)
        font_series = fit_font_to_width(card_draw, collection, max_text_w, 18, min_size=11)
        font_rarity = fit_font_to_width(card_draw, rarity_es_upper(rarity), max_text_w, 16, min_size=10)

        draw_centered_text_with_outline(card_draw, name,                    center, card_h - 90, font_name,   (255, 255, 255, 255), stroke=2)
        draw_centered_text_with_outline(card_draw, collection,              center, card_h - 58, font_series, (215, 215, 215, 255), stroke=1)
        draw_centered_text_with_outline(card_draw, rarity_es_upper(rarity), center, card_h - 32, font_rarity,
                                        (0, 0, 0, 255), outline=(255, 255, 255, 255), stroke=2)

        card = _rounded_card(card, radius=corner_r)
        x = i * (card_w + padding)
        pack.paste(card, (x, 0), card)

    return pack


def create_single_drop_card(c: dict) -> Image.Image:
    return create_drop_image([c])


def create_drop_image(dropped_cards: List[dict]) -> Image.Image:
    card_w, card_h = 580, 900
    gap    = 36
    margin = 16
    total_w = card_w * len(dropped_cards) + gap * (len(dropped_cards) - 1)

    pack = Image.new("RGBA", (total_w, card_h), (0, 0, 0, 255))
    bg_draw = ImageDraw.Draw(pack)
    for y in range(card_h):
        t = y / (card_h - 1)
        v = int(10 + 20 * t)
        bg_draw.line([(0, y), (total_w - 1, y)], fill=(v, v, v + 6, 255))

    for i, c in enumerate(dropped_cards):
        rarity       = (c.get("rarity", "common") or "common").lower()
        name         = str(c.get("name", "???")).upper()
        collection   = str(c.get("collection", "???")).upper()
        display_code = str(c.get("display_code", "G·???"))
        path         = c["img"]

        r, g, b, _ = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])

        full = os.path.join(BASE_DIR, "images", path)
        card = _crop_fill(full, card_w, card_h)
        card = apply_rarity_fx(card, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        draw   = ImageDraw.Draw(card)
        max_tw = card_w - margin - 12

        font_code   = get_bold_font(33)
        font_name   = fit_font_to_width(draw, name,       max_tw, 46, min_size=24)
        font_series = fit_font_to_width(draw, collection, max_tw, 30, min_size=20)

        # layout: name · series · code pill (top to bottom)
        name_y   = card_h - 178
        series_y = card_h - 118
        code_y   = card_h - 66

        # paint-brush gradient: irregular top edge via per-column sine offsets
        import math, random as _rnd
        grad_base  = name_y - 28   # baseline where gradient starts
        brush_amp  = 12            # max vertical variation (brushstroke roughness)
        overlay = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        for x in range(card_w):
            # combine two sines at different frequencies for organic look
            wave = (math.sin(x * 0.07) * 0.6 + math.sin(x * 0.19 + 1.3) * 0.4)
            col_start = grad_base + int(wave * brush_amp)
            col_h     = card_h - col_start
            if col_h <= 0:
                continue
            for dy in range(col_h):
                t     = dy / (col_h - 1) if col_h > 1 else 1
                alpha = int(255 * (t ** 0.42))
                ov_draw.point((x, col_start + dy), fill=(r, g, b, alpha))
        card = Image.alpha_composite(card, overlay)
        draw = ImageDraw.Draw(card)

        # name: white with rarity glow
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx == 0 and dy == 0:
                    continue
                draw.text((margin + dx, name_y + dy), name, font=font_name, fill=(r, g, b, 140))
        draw.text((margin, name_y), name, font=font_name, fill=(255, 255, 255, 255))

        # series: light gray
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                if dx == 0 and dy == 0:
                    continue
                draw.text((margin + dx, series_y + dy), collection, font=font_series, fill=(0, 0, 0, 160))
        draw.text((margin, series_y), collection, font=font_series, fill=(200, 200, 200, 255))

        # code: pill badge
        code_bbox = draw.textbbox((0, 0), display_code, font=font_code)
        cw = code_bbox[2] - code_bbox[0]
        ch = code_bbox[3] - code_bbox[1]
        px, py = 18, 16
        bx1 = margin
        bx2 = bx1 + cw + px * 2
        by2 = code_y + ch + py * 2
        draw.rounded_rectangle([bx1, code_y, bx2, by2], radius=8,
                                fill=(0, 0, 0, 180), outline=(255, 255, 255, 80), width=1)
        draw.text((bx1 + px, code_y + py - code_bbox[1]), display_code,
                  font=font_code, fill=(220, 220, 220, 255))

        card = _rounded_card(card, radius=18)
        x = i * (card_w + gap)
        pack.paste(card, (x, 0), card)

    return pack
