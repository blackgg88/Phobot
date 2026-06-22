from __future__ import annotations

from typing import List

from PIL import Image, ImageDraw

from rendering.cards import render_single_card_image
from rendering.fonts import get_bold_font, draw_centered_text_with_outline


def build_trade_image(
    cards_db: dict,
    *,
    a_insts: List[dict],
    b_insts: List[dict],
    a_name: str,
    b_name: str,
) -> Image.Image:
    per_side_max = 8
    a_show = list(a_insts or [])[:per_side_max]
    b_show = list(b_insts or [])[:per_side_max]

    card_w, card_h = 210, 294
    cols, rows = 4, 2
    pad = 16
    top = 56
    mid_gap = 32

    side_w = cols * card_w + (cols + 1) * pad
    w = side_w * 2 + mid_gap
    h = top + rows * card_h + (rows + 1) * pad + 18

    canvas = Image.new("RGBA", (w, h), (22, 22, 22, 255))
    draw   = ImageDraw.Draw(canvas)

    title_font = get_bold_font(26)
    sub_font   = get_bold_font(18)

    draw.rectangle([side_w, 0, side_w + mid_gap, h], fill=(15, 15, 15, 255))
    draw.rectangle([side_w + mid_gap // 2 - 2, 10, side_w + mid_gap // 2 + 2, h - 10], fill=(60, 60, 60, 255))

    def header(x0: int, name: str, insts: List[dict]) -> None:
        total = sum(int(i.get("value", 0) or 0) for i in insts)
        draw_centered_text_with_outline(draw, name, x0 + side_w // 2, 10, title_font, (255, 255, 255, 255), stroke=2)
        draw_centered_text_with_outline(draw, f"{len(insts)} cartas • Total P{total}",
                                        x0 + side_w // 2, 34, sub_font, (220, 220, 220, 255), stroke=2)

    header(0, a_name, a_insts)
    header(side_w + mid_gap, b_name, b_insts)

    def paste_grid(x_base: int, insts: List[dict]) -> None:
        for i in range(cols * rows):
            r = i // cols
            c = i % cols
            x = x_base + pad + c * (card_w + pad)
            y = top + pad + r * (card_h + pad)

            if i >= len(insts):
                ph = Image.new("RGBA", (card_w, card_h), (30, 30, 30, 255))
                d  = ImageDraw.Draw(ph)
                d.rounded_rectangle([8, 8, card_w - 8, card_h - 8], radius=18, outline=(90, 90, 90, 255), width=3)
                f = get_bold_font(20)
                draw_centered_text_with_outline(d, "—", card_w // 2, card_h // 2 - 12, f, (180, 180, 180, 255), stroke=2)
                canvas.paste(ph, (x, y), ph)
                continue

            img  = render_single_card_image(cards_db, insts[i]).resize((card_w, card_h))
            canvas.paste(img, (x, y), img)

            code = str(insts[i].get("code", "")).lower()
            if code:
                f = get_bold_font(16)
                draw_centered_text_with_outline(draw, code, x + card_w // 2, y + card_h - 20, f, (255, 255, 255, 255), stroke=2)

    paste_grid(0, a_show)
    paste_grid(side_w + mid_gap, b_show)
    return canvas
