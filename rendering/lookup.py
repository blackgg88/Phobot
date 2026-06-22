from __future__ import annotations

import os
from typing import List

from PIL import Image, ImageDraw

from config import BASE_DIR
from rendering.cards import render_single_card_image
from rendering.fonts import get_bold_font


def build_plu_image(cards_db: dict, *, collection: str, name: str, token_imgs: List[str]) -> Image.Image:
    meta   = (cards_db.get(collection) or {}).get(name, {})
    rarity = (meta.get("rarity") or "common").lower()

    base_inst = {"collection": collection, "name": name, "rarity": rarity, "value": None, "code": ""}
    original  = render_single_card_image(cards_db, base_inst).resize((270, 378))

    thumbs = []
    for img_rel in token_imgs:
        inst = {"collection": collection, "name": name, "rarity": rarity,
                "value": None, "code": "", "img": img_rel, "is_token": True}
        thumbs.append(render_single_card_image(cards_db, inst).resize((210, 294)))

    cols   = 3
    pad    = 18
    top    = 56

    rows   = max(1, (len(thumbs) + cols - 1) // cols)
    rw     = cols * 210 + (cols + 1) * pad
    rh     = rows * 294 + (rows + 1) * pad

    w = 270 + pad + rw + pad
    h = max(378 + top + pad, rh + top) + pad

    canvas = Image.new("RGBA", (w, h), (20, 20, 20, 255))
    d      = ImageDraw.Draw(canvas)
    f1     = get_bold_font(28)
    f2     = get_bold_font(20)

    d.text((pad, 12),          f"{name} — {collection}",             font=f1, fill=(245, 245, 245, 255))
    d.text((pad, 12 + 30),     "Imagen habitual",                     font=f2, fill=(200, 200, 200, 255))
    d.text((270 + pad * 2, 12 + 30), f"Tokens disponibles ({len(thumbs)})", font=f2, fill=(200, 200, 200, 255))

    canvas.paste(original, (pad, top), original)

    x0, y0 = 270 + pad * 2, top
    lab_font = get_bold_font(18)
    for i, im in enumerate(thumbs):
        r = i // cols
        c = i % cols
        x = x0 + pad + c * (210 + pad)
        y = y0 + pad + r * (294 + pad)
        canvas.paste(im, (x, y), im)
        d.rounded_rectangle([x + 8, y + 8, x + 52, y + 34], radius=10, fill=(0, 0, 0, 160))
        d.text((x + 16, y + 10), f"T{i+1}", font=lab_font, fill=(255, 255, 255, 255))

    return canvas
