from __future__ import annotations

import os
from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from config import BASE_DIR, RARITY_STYLES
from core.achievements import ACH_BY_ID
from rendering.fonts import (
    get_bold_font, draw_centered_text_with_outline, fit_font_to_width,
)
from rendering.fx import safe_open_image, apply_rarity_fx

# ── Paleta ─────────────────────────────────────────────────
BG     = (15,  15,  15,  255)
PANEL  = (32,  32,  32,  255)
PANEL2 = (22,  22,  22,  255)
WHITE  = (255, 255, 255, 255)
GRAY   = (160, 160, 160, 255)

SEASON_INFO = {
    "verano":    ("VERANO",    (255, 200,  50, 255)),
    "otono":     ("OTONO",     (210, 110,  30, 255)),
    "invierno":  ("INVIERNO",  ( 90, 160, 255, 255)),
    "primavera": ("PRIMAVERA", (220, 130, 180, 255)),
}
SEASON_EMOJI = {
    "verano":    "☀",
    "otono":     "🍂",
    "invierno":  "❄",
    "primavera": "🌸",
}


# ── Helpers ────────────────────────────────────────────────

def get_season_ar(month: int, day: int) -> str:
    if (month == 12 and day >= 21) or month in (1, 2) or (month == 3 and day <= 20):
        return "verano"
    if (month == 3 and day >= 21) or month in (4, 5) or (month == 6 and day <= 20):
        return "otono"
    if (month == 6 and day >= 21) or month in (7, 8) or (month == 9 and day <= 20):
        return "invierno"
    return "primavera"


def make_circle_avatar(img_bytes: Optional[bytes], size: int = 210) -> Image.Image:
    if img_bytes:
        try:
            src = Image.open(BytesIO(img_bytes)).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            src = Image.new("RGBA", (size, size), (70, 70, 70, 255))
    else:
        src = Image.new("RGBA", (size, size), (70, 70, 70, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(src, mask=mask)
    return out


def _panel(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, radius=12, fill=PANEL):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def _render_card_slot(
    card: Optional[dict], slot_w: int, slot_h: int
) -> Image.Image:
    slot = Image.new("RGBA", (slot_w, slot_h), PANEL2)
    if not card or not card.get("img"):
        return slot

    rarity = (card.get("rarity") or "common").lower()
    path   = card["img"]
    full   = os.path.join(BASE_DIR, "images", path)

    try:
        card_img = safe_open_image(full, size=(slot_w, slot_h)).resize((slot_w, slot_h))
    except Exception:
        return slot

    card_img = apply_rarity_fx(card_img, RARITY_STYLES.get(rarity, RARITY_STYLES["common"]))

    # degradé inferior
    r, g, b, _ = RARITY_STYLES.get(rarity, RARITY_STYLES["common"])
    gh      = int(slot_h * 0.40)
    overlay = Image.new("RGBA", (slot_w, slot_h), (0, 0, 0, 0))
    od      = ImageDraw.Draw(overlay)
    for y in range(gh):
        t     = y / max(gh - 1, 1)
        alpha = int(215 * (t ** 1.8))
        od.line([(0, slot_h - gh + y), (slot_w - 1, slot_h - gh + y)], fill=(r, g, b, alpha))
    card_img = Image.alpha_composite(card_img, overlay)

    cd  = ImageDraw.Draw(card_img)
    cx  = slot_w // 2
    mw  = slot_w - 16
    name  = str(card.get("name", "")).upper()
    coll  = str(card.get("collection", "")).upper()
    fn = fit_font_to_width(cd, name, mw, 20, min_size=10)
    fs = fit_font_to_width(cd, coll, mw, 14, min_size=9)
    draw_centered_text_with_outline(cd, name, cx, slot_h - 62, fn, WHITE, stroke=2)
    draw_centered_text_with_outline(cd, coll, cx, slot_h - 34, fs, GRAY,  stroke=1)

    slot.paste(card_img, (0, 0), card_img)
    return slot


# ── Render principal ───────────────────────────────────────

def render_profile_image(
    *,
    avatar_bytes: Optional[bytes],
    display_name: str,
    birthday: str,
    age: str,
    achievements_done: int,
    achievements_total: int,
    featured_titles: List[str],
    featured_cards: List[Optional[dict]],
    season_key: str,
    date_str: str,
    time_str: str,
) -> Image.Image:
    W, H = 950, 800
    img  = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Avatar (1) ─────────────────────────────────────
    av = 210
    ax, ay = 22, 22
    _panel(draw, ax - 5, ay - 5, ax + av + 5, ay + av + 5,
           radius=av // 2 + 5, fill=PANEL)
    avatar = make_circle_avatar(avatar_bytes, av)
    img.paste(avatar, (ax, ay), avatar)

    # ── Nombre (2) ─────────────────────────────────────
    _panel(draw, 252, 22, 676, 98)
    fn = fit_font_to_width(draw, display_name, 400, 36, min_size=16)
    draw_centered_text_with_outline(draw, display_name, (252 + 676) // 2, 38, fn, WHITE, stroke=1)

    # ── Cumpleaños (3) ─────────────────────────────────
    _panel(draw, 252, 113, 460, 173)
    fl = get_bold_font(13)
    fv = get_bold_font(26)
    draw.text((265, 117), "CUMPLEANOS", font=fl, fill=GRAY)
    draw_centered_text_with_outline(draw, birthday or "—", (252 + 460) // 2, 138, fv, WHITE, stroke=1)

    # ── Edad (4) ───────────────────────────────────────
    _panel(draw, 474, 113, 676, 173)
    draw.text((487, 117), "EDAD", font=fl, fill=GRAY)
    draw_centered_text_with_outline(draw, age or "—", (474 + 676) // 2, 138, fv, WHITE, stroke=1)

    # ── Logros (5) ─────────────────────────────────────
    _panel(draw, 692, 22, 930, 245)
    fb  = get_bold_font(68)
    fs2 = get_bold_font(14)
    acx = (692 + 930) // 2
    draw_centered_text_with_outline(draw, str(achievements_done), acx, 55, fb, WHITE, stroke=2)
    for line_i, line in enumerate(["de", f"{achievements_total}", "logros"]):
        draw.text((705, 172 + line_i * 22), line, font=fs2, fill=GRAY)

    # ── Títulos destacados (6) — 2 filas × 2 columnas ──
    title_rects = [
        (20, 260, 462, 308),
        (477, 260, 930, 308),
        (20, 323, 462, 371),
        (477, 323, 930, 371),
    ]
    ft = get_bold_font(20)
    for i, (tx1, ty1, tx2, ty2) in enumerate(title_rects):
        _panel(draw, tx1, ty1, tx2, ty2, radius=10, fill=PANEL2)
        if i < len(featured_titles):
            ach = ACH_BY_ID.get(featured_titles[i])
            if ach:
                label = ach["title"].upper()
                fw    = fit_font_to_width(draw, label, tx2 - tx1 - 30, 20, min_size=12)
                draw_centered_text_with_outline(
                    draw, label, (tx1 + tx2) // 2, ty1 + 14, fw, WHITE, stroke=1
                )

    # ── Cartas (7) — 3 slots ───────────────────────────
    cw, ch   = 260, 364
    cgap     = 20
    cx_start = (W - (cw * 3 + cgap * 2)) // 2
    cy_start = 388

    for i in range(3):
        cx = cx_start + i * (cw + cgap)
        cy = cy_start
        _panel(draw, cx, cy, cx + cw, cy + ch, radius=10, fill=PANEL2)
        card = featured_cards[i] if i < len(featured_cards) else None
        slot = _render_card_slot(card, cw, ch)
        img.paste(slot, (cx, cy), slot)

    # ── Franja inferior: estación (8), fecha (9), hora (10) ──
    by = cy_start + ch + 14
    sname, scolor = SEASON_INFO.get(season_key, ("?", WHITE))
    semoji = SEASON_EMOJI.get(season_key, "")

    fs3 = get_bold_font(17)
    fs4 = get_bold_font(14)

    # estación centrada bajo carta 2
    s2cx = cx_start + cw + cgap + cw // 2
    draw_centered_text_with_outline(
        draw, f"{semoji} {sname}", s2cx, by, fs3, scolor, stroke=1
    )

    # fecha y hora bajo carta 3
    s3cx = cx_start + 2 * (cw + cgap) + cw // 2
    draw_centered_text_with_outline(draw, date_str, s3cx, by,      fs4, GRAY, stroke=0)
    draw_centered_text_with_outline(draw, time_str, s3cx, by + 22, fs4, GRAY, stroke=0)

    return img
