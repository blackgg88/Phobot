from __future__ import annotations

from io import BytesIO
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

from core.achievements import ACH_BY_ID
from rendering.fonts import (
    get_bold_font, draw_centered_text_with_outline, fit_font_to_width,
)
from core.levels import xp_progress
from rendering.cards import render_single_card_image
from rendering.fx import safe_open_image

# ── Paleta base ────────────────────────────────────────────
WHITE = (255, 255, 255, 255)
GRAY  = (160, 160, 160, 255)

THEMES = {
    "negro":   {"bg": (15,  15,  15),  "panel": (32,  32,  32),  "panel2": (22,  22,  22)},
    "rosa":    {"bg": (30,  10,  22),  "panel": (70,  28,  52),  "panel2": (48,  15,  36)},
    "verde":   {"bg": (10,  28,  16),  "panel": (20,  58,  34),  "panel2": (12,  38,  22)},
    "celeste": {"bg": (8,   22,  40),  "panel": (18,  52,  84),  "panel2": (10,  32,  60)},
    "lila":    {"bg": (22,  12,  38),  "panel": (52,  28,  82),  "panel2": (32,  16,  56)},
    "naranja": {"bg": (38,  18,   5),  "panel": (78,  44,  12),  "panel2": (55,  28,   8)},
}

def _theme(key: str):
    t = THEMES.get(key, THEMES["negro"])
    bg     = (*t["bg"],     255)
    panel  = (*t["panel"],  255)
    panel2 = (*t["panel2"], 255)
    return bg, panel, panel2

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


def _panel(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, radius=12, fill=(32, 32, 32, 255)):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def _render_card_slot(
    cards_db: dict, card: Optional[dict], slot_w: int, slot_h: int,
    bg_color=(22, 22, 22, 255), corner_radius: int = 10,
) -> Image.Image:
    slot = Image.new("RGBA", (slot_w, slot_h), bg_color)
    if not card or not card.get("img"):
        # máscara redondeada al slot vacío también
        mask = Image.new("L", (slot_w, slot_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, slot_w - 1, slot_h - 1], radius=corner_radius, fill=255)
        slot.putalpha(mask)
        return slot

    # renderizar con todos los efectos (holo, marco, rareza) — igual que !pver
    try:
        card_img = render_single_card_image(cards_db, card).resize((slot_w, slot_h), Image.LANCZOS)
    except Exception:
        return slot

    # máscara redondeada para que las esquinas no sobresalgan
    mask = Image.new("L", (slot_w, slot_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, slot_w - 1, slot_h - 1], radius=corner_radius, fill=255)
    card_img.putalpha(mask)

    slot.paste(card_img, (0, 0), card_img)
    return slot


# ── Render principal ───────────────────────────────────────

def render_profile_image(
    *,
    cards_db: dict,
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
    xp: int = 0,
    theme: str = "negro",
) -> Image.Image:
    BG, PANEL, PANEL2 = _theme(theme)
    W, H = 950, 800
    img  = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    def panel(x1, y1, x2, y2, radius=12, fill=None):
        _panel(draw, x1, y1, x2, y2, radius=radius, fill=fill if fill is not None else PANEL)

    # ── Avatar (1) ─────────────────────────────────────
    av = 210
    ax, ay = 22, 22
    panel(ax - 5, ay - 5, ax + av + 5, ay + av + 5,
          radius=av // 2 + 5)
    avatar = make_circle_avatar(avatar_bytes, av)
    img.paste(avatar, (ax, ay), avatar)

    # ── Nombre (2) ─────────────────────────────────────
    panel(252, 22, 676, 98)
    fn = fit_font_to_width(draw, display_name, 400, 36, min_size=16)
    draw_centered_text_with_outline(draw, display_name, (252 + 676) // 2, 38, fn, WHITE, stroke=1)

    # ── Cumpleaños (3) ─────────────────────────────────
    panel(252, 113, 460, 173)
    fl = get_bold_font(13)
    fv = get_bold_font(26)
    draw.text((265, 117), "CUMPLEAÑOS", font=fl, fill=GRAY)
    draw_centered_text_with_outline(draw, birthday or "—", (252 + 460) // 2, 138, fv, WHITE, stroke=1)

    # ── Edad (4) ───────────────────────────────────────
    panel(474, 113, 676, 173)
    draw.text((487, 117), "EDAD", font=fl, fill=GRAY)
    draw_centered_text_with_outline(draw, age or "—", (474 + 676) // 2, 138, fv, WHITE, stroke=1)

    # ── Logros (5) ─────────────────────────────────────
    panel(692, 22, 930, 245)
    acx  = (692 + 930) // 2
    fl2  = get_bold_font(15)
    fb   = get_bold_font(62)
    fs2  = get_bold_font(18)
    draw_centered_text_with_outline(draw, "LOGROS", acx, 32, fl2, GRAY, stroke=0)
    draw_centered_text_with_outline(draw, str(achievements_done), acx, 80, fb, WHITE, stroke=2)
    draw_centered_text_with_outline(draw, f"de {achievements_total}", acx, 180, fs2, GRAY, stroke=0)

    # ── Barra de XP / nivel ────────────────────────────
    xp_level, xp_cur, xp_needed = xp_progress(xp)
    bar_x1, bar_y1, bar_x2, bar_y2 = 252, 185, 676, 245
    panel(bar_x1, bar_y1, bar_x2, bar_y2, radius=12)

    fl3      = get_bold_font(13)
    bar_pad  = 16
    bar_h    = 18
    bar_iy   = bar_y2 - bar_pad - bar_h
    bar_ix1  = bar_x1 + bar_pad
    bar_ix2  = bar_x2 - bar_pad
    bar_iw   = bar_ix2 - bar_ix1

    # etiqueta nivel izquierda y XP derecha
    draw.text((bar_x1 + bar_pad, bar_y1 + 10), f"NIVEL {xp_level}", font=fl3, fill=GRAY)
    xp_label = f"{xp_cur} / {xp_needed} XP"
    bbox = draw.textbbox((0, 0), xp_label, font=fl3)
    draw.text((bar_ix2 - (bbox[2] - bbox[0]), bar_y1 + 10), xp_label, font=fl3, fill=GRAY)

    # fondo de la barra
    draw.rounded_rectangle([bar_ix1, bar_iy, bar_ix2, bar_iy + bar_h], radius=bar_h // 2, fill=(50, 50, 50, 255))
    # relleno verde proporcional
    fill_w = int(bar_iw * min(xp_cur / max(xp_needed, 1), 1.0))
    if fill_w > 0:
        draw.rounded_rectangle(
            [bar_ix1, bar_iy, bar_ix1 + fill_w, bar_iy + bar_h],
            radius=bar_h // 2,
            fill=(60, 200, 80, 255),
        )

    # ── Títulos destacados (6) — 2 filas × 2 columnas ──
    title_rects = [
        (20, 260, 462, 308),
        (477, 260, 930, 308),
        (20, 323, 462, 371),
        (477, 323, 930, 371),
    ]
    ft = get_bold_font(20)
    for i, (tx1, ty1, tx2, ty2) in enumerate(title_rects):
        panel(tx1, ty1, tx2, ty2, radius=10, fill=PANEL2)
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
        panel(cx, cy, cx + cw, cy + ch, radius=10, fill=PANEL2)
        card = featured_cards[i] if i < len(featured_cards) else None
        slot = _render_card_slot(cards_db, card, cw, ch, bg_color=PANEL2, corner_radius=10)
        img.paste(slot, (cx, cy), slot)

    # ── Franja inferior: estación bajo carta 1, fecha bajo carta 2, hora bajo carta 3 ──
    by = cy_start + ch + 14
    sname, scolor = SEASON_INFO.get(season_key, ("?", WHITE))
    semoji = SEASON_EMOJI.get(season_key, "")

    fs3 = get_bold_font(17)
    fs4 = get_bold_font(14)

    cx1 = cx_start + cw // 2
    cx2 = cx_start + cw + cgap + cw // 2
    cx3 = cx_start + 2 * (cw + cgap) + cw // 2

    draw_centered_text_with_outline(draw, f"{semoji} {sname}", cx1, by, fs3, scolor, stroke=1)
    draw_centered_text_with_outline(draw, date_str,            cx2, by, fs4, GRAY,   stroke=0)
    draw_centered_text_with_outline(draw, time_str,            cx3, by, fs4, GRAY,   stroke=0)

    return img
