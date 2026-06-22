from __future__ import annotations

import os
from math import ceil
from typing import Set, Tuple

from PIL import Image, ImageDraw, ImageEnhance

from config import BASE_DIR, RARITY_STYLES
from core.cards import rarity_es_upper
from rendering.fonts import get_bold_font, draw_centered_text_with_outline
from rendering.fx import apply_rarity_fx, safe_open_image, rarity_panel_color


def collection_progress(collection_name: str, owned_set: Set[Tuple[str, str]], cards_db: dict) -> Tuple[int, int, int]:
    total = len(cards_db[collection_name])
    owned_unique = sum(1 for (c, _) in owned_set if c == collection_name)
    percent = int(round((owned_unique / total) * 100)) if total > 0 else 0
    return owned_unique, total, percent


def build_collection_page_image(
    collection_name: str,
    owned_set: Set[Tuple[str, str]],
    cards_db: dict,
    page: int,
    per_page: int = 12,
) -> Tuple[Image.Image, int]:
    collection_cards = list(cards_db[collection_name].items())
    total_cards  = len(collection_cards)
    total_pages  = max(1, ceil(total_cards / per_page))
    page         = max(0, min(page, total_pages - 1))
    chunk        = collection_cards[page * per_page : (page + 1) * per_page]

    card_w, card_h = 300, 420
    label_h = 110
    cell_h  = card_h + label_h
    columns, rows = 4, 3

    album = Image.new("RGBA", (columns * card_w, rows * cell_h), (20, 20, 20, 255))
    draw  = ImageDraw.Draw(album)
    font_name   = get_bold_font(24)
    font_rarity = get_bold_font(20)

    for i, (name, data) in enumerate(chunk):
        x = (i % columns) * card_w
        y = (i // columns) * cell_h
        owned  = (collection_name, name) in owned_set
        path   = (data or {}).get("img")
        rarity = ((data or {}).get("rarity", "common") or "common").lower()

        img = safe_open_image(os.path.join(BASE_DIR, "images", path) if path else "", size=(card_w, card_h))
        img = img.resize((card_w, card_h))
        img = apply_rarity_fx(img, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        if not owned:
            img = img.convert("L").convert("RGBA")
            img = ImageEnhance.Brightness(img).enhance(0.35)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 160))
            img = Image.alpha_composite(img, overlay)

        album.paste(img, (x, y), img)

        panel = rarity_panel_color(rarity) if owned else (60, 60, 60, 170)
        draw.rounded_rectangle(
            [x + 10, y + card_h + 10, x + card_w - 10, y + card_h + label_h - 10],
            radius=14, fill=panel,
        )
        center   = x + card_w // 2
        fill_name = (255, 255, 255, 255) if owned else (160, 160, 160, 255)
        fill_rar  = (0,   0,   0, 255)   if owned else (190, 190, 190, 255)
        draw_centered_text_with_outline(draw, str(name),             center, y + card_h + 16, font_name,   fill_name, stroke=2)
        draw_centered_text_with_outline(draw, rarity_es_upper(rarity), center, y + card_h + 56, font_rarity, fill_rar,
                                        outline=(255, 255, 255, 255), stroke=2)

    return album, total_pages
