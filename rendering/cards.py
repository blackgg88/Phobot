from __future__ import annotations

import os
from io import BytesIO
from typing import Tuple

import discord
from PIL import Image, ImageDraw

from config import BASE_DIR, CARD_SIZE, RARITY_STYLES
from core.frames import get_frame_meta
from rendering.fonts import get_bold_font, draw_centered_text_with_outline
from rendering.fx import apply_rarity_fx, apply_frame_overlay, apply_holo_fx, is_holo, safe_open_image


def pil_to_discord_file(img: Image.Image, filename: str) -> discord.File:
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return discord.File(fp=bio, filename=filename)


def draw_value_tag_on_card(card_img: Image.Image, value_text: str, rarity: str = "common") -> None:
    draw = ImageDraw.Draw(card_img)
    w, _h = card_img.size
    text  = str(value_text or "")
    font  = get_bold_font(22)
    pad_x, pad_y = 14, 7

    bbox  = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    box_w, box_h = tw + pad_x * 2, th + pad_y * 2

    x2, y1 = w - 10, 10
    x1, y2 = x2 - box_w, y1 + box_h
    notch = min(28, max(16, box_h - 2))

    base = RARITY_STYLES.get((rarity or "common").lower(), RARITY_STYLES["common"])
    r, g, b, _a = base
    fill  = (r, g, b, 220)
    poly  = [(x1, y1), (x2, y1), (x2, y2), (x1 + notch, y2)]
    shadow = [(px + 2, py + 2) for px, py in poly]

    draw.polygon(shadow, fill=(0, 0, 0, 110))
    draw.polygon(poly, fill=fill)
    draw.line(poly + [poly[0]], fill=(0, 0, 0, 220), width=3)

    eff_left = x1 + (notch // 2)
    text_x = eff_left + ((x2 - eff_left) - tw) // 2 - bbox[0]
    text_y = y1 + (box_h - th) // 2 - bbox[1]

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((text_x + dx, text_y + dy), text, font=font, fill=(0, 0, 0, 255))
    draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))


def _draw_gen_badge(card_img: Image.Image, text: str, holo: bool = False) -> None:
    """Badge G·N en la esquina inferior izquierda de la carta."""
    draw  = ImageDraw.Draw(card_img)
    font  = get_bold_font(18)
    pad_x, pad_y = 10, 6
    bbox  = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bw, bh = tw + pad_x * 2, th + pad_y * 2
    x0, y0 = 10, card_img.height - 10 - bh
    x1, y1 = x0 + bw, y0 + bh
    fill    = (40, 0, 60, 210)    if holo else (0, 0, 0, 180)
    outline = (200, 150, 255, 220) if holo else (255, 255, 255, 80)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=7, fill=fill, outline=outline, width=2 if holo else 1)
    text_col = (230, 180, 255, 255) if holo else (210, 210, 210, 255)
    draw.text((x0 + pad_x, y0 + pad_y - bbox[1]), text, font=font, fill=text_col)


def draw_token_label_on_card(card_img: Image.Image) -> None:
    w, h = card_img.size
    text = "Token"
    font = get_bold_font(24)
    pad_x, pad_y = 10, 8
    d = ImageDraw.Draw(card_img)

    try:
        tw, th = d.textsize(text, font=font)
    except AttributeError:
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    box_w, box_h = tw + pad_x * 2, th + pad_y * 2
    x1, y1 = w - 14, h - 14
    x0, y0 = x1 - box_w, y1 - box_h
    d.rounded_rectangle([x0, y0, x1, y1], radius=14,
                         fill=(0, 0, 0, 160), outline=(255, 255, 255, 120), width=2)
    d.text((x0 + pad_x, y0 + pad_y - 2), text, font=font, fill=(255, 255, 255, 255))


def render_single_card_image(cards_db: dict, inst: dict) -> Image.Image:
    collection = inst.get("collection")
    name       = inst.get("name")
    meta       = (cards_db.get(collection) or {}).get(name)

    if not meta or not meta.get("img"):
        img = Image.new("RGBA", (300, 420), (30, 30, 30, 255))
        ImageDraw.Draw(img).text((10, 10), "Carta inválida", fill=(255, 255, 255, 255))
        return img

    rarity  = (inst.get("rarity") or meta.get("rarity") or "common").lower()
    img_rel = inst.get("token_img") or inst.get("img") or meta["img"]
    full    = os.path.join(BASE_DIR, "images", str(img_rel))
    card    = safe_open_image(full, size=(300, 420)).resize((300, 420))

    frame_id = inst.get("frame_id")
    if frame_id is not None:
        fmeta = get_frame_meta(int(frame_id))
        if fmeta:
            return apply_frame_overlay(card, fmeta, holo=is_holo(inst))
        return card

    if is_holo(inst):
        card = apply_holo_fx(card)
    else:
        fx_color = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])
        card = apply_rarity_fx(card, fx_color)

    gen = inst.get("gen")
    if gen is not None:
        try:
            _draw_gen_badge(card, f"G·{gen}", holo=is_holo(inst))
        except Exception:
            pass

    return card


def resize_to_fit_rgba(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    tw, th = target_size
    im = img.convert("RGBA")
    try:
        im2 = im.copy()
        im2.thumbnail((tw, th), Image.LANCZOS)
    except Exception:
        im2 = im.copy()
        im2.thumbnail((tw, th))
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    x = (tw - im2.size[0]) // 2
    y = (th - im2.size[1]) // 2
    canvas.paste(im2, (x, y), im2)
    return canvas


def build_before_after_image(before_img: Image.Image, after_img: Image.Image) -> Image.Image:
    bw, bh = before_img.size
    aw, ah = after_img.size
    h = max(bh, ah) + 60
    w = bw + aw + 90
    canvas = Image.new("RGBA", (w, h), (15, 15, 15, 255))
    d = ImageDraw.Draw(canvas)
    arrow_font = get_bold_font(44)
    lab_font   = get_bold_font(22)
    d.text((20, 10), "Antes",    font=lab_font, fill=(240, 240, 240, 255))
    d.text((bw + 70, 10), "Después", font=lab_font, fill=(240, 240, 240, 255))
    y0 = 50
    canvas.paste(before_img, (20, y0), before_img)
    canvas.paste(after_img, (bw + 70, y0), after_img)
    d.text((bw + 35, y0 + bh // 2 - 25), "➡", font=arrow_font, fill=(255, 255, 255, 255))
    return canvas
