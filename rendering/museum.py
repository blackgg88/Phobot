from __future__ import annotations

from typing import List, Optional

from PIL import Image, ImageDraw

from config import DEFAULT_MUSEUM_BG, MUSEUM_BACKGROUNDS
from rendering.cards import render_single_card_image, resize_to_fit_rgba
from rendering.fonts import get_bold_font, draw_centered_text_with_outline


def build_museum_image(
    cards_db: dict,
    inst_list: List[Optional[dict]],
    bg_key: str = DEFAULT_MUSEUM_BG,
) -> Image.Image:
    cols, rows = 5, 2
    card_w, card_h = 260, 350
    pad = 22
    top_pad = 20

    bg_key = (bg_key or DEFAULT_MUSEUM_BG).strip().lower()
    bg = MUSEUM_BACKGROUNDS.get(bg_key, MUSEUM_BACKGROUNDS[DEFAULT_MUSEUM_BG])

    width  = cols * card_w + (cols + 1) * pad
    height = rows * card_h + (rows + 1) * pad + top_pad

    canvas = Image.new("RGBA", (width, height), bg)
    draw   = ImageDraw.Draw(canvas)
    font   = get_bold_font(32)
    draw_centered_text_with_outline(draw, "MUSEO", width // 2, 6, font, (255, 255, 255, 255), stroke=2)

    inst_list = (inst_list or [])[:10]
    while len(inst_list) < 10:
        inst_list.append(None)

    for i in range(10):
        r = i // cols
        c = i % cols
        x = pad + c * (card_w + pad)
        y = top_pad + pad + r * (card_h + pad)

        inst = inst_list[i]
        if inst:
            img = resize_to_fit_rgba(render_single_card_image(cards_db, inst), (card_w, card_h))
            canvas.paste(img, (x, y), img)
        else:
            ph = Image.new("RGBA", (card_w, card_h), (35, 35, 35, 255))
            d  = ImageDraw.Draw(ph)
            d.rounded_rectangle([8, 8, card_w - 8, card_h - 8], radius=20, outline=(90, 90, 90, 255), width=4)
            f2 = get_bold_font(26)
            draw_centered_text_with_outline(d, "VACÍO", card_w // 2, card_h // 2 - 18, f2, (200, 200, 200, 255), stroke=2)
            canvas.paste(ph, (x, y), ph)

    return canvas
