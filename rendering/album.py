from __future__ import annotations

import os
from math import ceil
from typing import Set, Tuple

from PIL import Image, ImageDraw, ImageEnhance

from config import BASE_DIR, RARITY_STYLES
from core.cards import rarity_es_upper
from rendering.fonts import get_bold_font, draw_centered_text_with_outline
from rendering.fx import apply_rarity_fx, apply_holo_fx, safe_open_image, rarity_panel_color


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
    holo_set: Set[Tuple[str, str]] = None,
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

        is_holo_card = owned and holo_set and (collection_name, name) in holo_set

        img = safe_open_image(os.path.join(BASE_DIR, "images", path) if path else "", size=(card_w, card_h))
        img = img.resize((card_w, card_h))

        if is_holo_card:
            img = apply_holo_fx(img)
        else:
            img = apply_rarity_fx(img, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

        if not owned:
            img = img.convert("L").convert("RGBA")
            img = ImageEnhance.Brightness(img).enhance(0.35)
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 160))
            img = Image.alpha_composite(img, overlay)

        album.paste(img, (x, y), img)

        px0, py0 = x + 10, y + card_h + 10
        px1, py1 = x + card_w - 10, y + card_h + label_h - 10

        if is_holo_card:
            # panel tornasol: gradiente diagonal arcoíris
            panel_img = Image.new("RGBA", (px1 - px0, py1 - py0), (0, 0, 0, 0))
            pd = ImageDraw.Draw(panel_img)
            pw, ph = panel_img.size
            holo_colors = [
                (180, 100, 255), (120, 140, 255), (90, 210, 230),
                (160, 255, 180), (255, 240, 120), (255, 160, 200), (200, 110, 255),
            ]
            stripe_w = max(1, (pw + ph) // len(holo_colors) + 4)
            for si, col in enumerate(holo_colors):
                ox = si * stripe_w - ph
                poly = [(ox, 0), (ox + stripe_w, 0), (ox + stripe_w + ph, ph), (ox + ph, ph)]
                pd.polygon(poly, fill=(*col, 200))
            from PIL import ImageFilter as _IF
            panel_img = panel_img.filter(_IF.GaussianBlur(6))
            # borde tornasol
            pd2 = ImageDraw.Draw(panel_img)
            pd2.rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10, outline=(255, 220, 255, 255), width=2)
            # máscara redondeada
            pmask = Image.new("L", (pw, ph), 0)
            ImageDraw.Draw(pmask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=10, fill=255)
            panel_img.putalpha(pmask)
            album.paste(panel_img, (px0, py0), panel_img)
            fill_name = (255, 230, 255, 255)
            fill_rar  = (220, 160, 255, 255)
        else:
            panel = rarity_panel_color(rarity) if owned else (60, 60, 60, 170)
            draw.rounded_rectangle([px0, py0, px1, py1], radius=14, fill=panel)
            fill_name = (255, 255, 255, 255) if owned else (160, 160, 160, 255)
            fill_rar  = (0,   0,   0, 255)   if owned else (190, 190, 190, 255)

        center = x + card_w // 2
        draw_centered_text_with_outline(draw, str(name),               center, y + card_h + 16, font_name,   fill_name, stroke=2)
        draw_centered_text_with_outline(draw, rarity_es_upper(rarity), center, y + card_h + 56, font_rarity, fill_rar,
                                        outline=(255, 255, 255, 255) if not is_holo_card else (80, 0, 120, 255), stroke=2)

    return album, total_pages
