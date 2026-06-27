from __future__ import annotations

import os
from datetime import date, datetime
from typing import List

from PIL import Image, ImageDraw, ImageEnhance

from config import BASE_DIR
from rendering.fonts import get_bold_font, draw_centered_text_with_outline, fit_font_to_width
from rendering.fx import safe_open_image

WHITE = (255, 255, 255, 255)
GRAY  = (160, 160, 160, 255)
PINK  = (255, 120, 220, 255)
GOLD  = (255, 215,   0, 255)
BG    = (15,  15,  15,  255)
PANEL = (30,  30,  30,  255)
ACCENT= (45,  45,  45,  255)


def _time_until_str(target: date) -> str:
    """Devuelve string legible del tiempo hasta `target` (p.ej. '9 días', '3h 42m')."""
    now  = datetime.now()
    then = datetime.combine(target, datetime.min.time())
    delta = then - now
    secs  = int(delta.total_seconds())
    if secs <= 0:
        return "0 minutos"
    days  = secs // 86400
    hours = (secs % 86400) // 3600
    mins  = (secs % 3600) // 60
    if days >= 2:
        return f"{days} días"
    if days == 1:
        return f"1 día"
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins} minutos"


def _load_card_img(img_rel: str, w: int, h: int) -> Image.Image:
    full = os.path.join(BASE_DIR, "images", img_rel)
    try:
        return safe_open_image(full, size=(w, h)).resize((w, h), Image.LANCZOS)
    except Exception:
        return Image.new("RGBA", (w, h), (50, 50, 50, 255))


def _draw_panel_gradient(img: Image.Image, x1: int, y1: int, x2: int, y2: int, radius: int = 16) -> None:
    """Panel con degradé sutil de arriba (más claro) a abajo (más oscuro), tono morado-rosado."""
    panel_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    h = y2 - y1
    for row in range(h):
        t     = row / max(h - 1, 1)
        r     = int(48  + (28  - 48)  * t)
        g     = int(28  + (18  - 28)  * t)
        b     = int(55  + (35  - 55)  * t)
        ImageDraw.Draw(panel_layer).line([(x1, y1 + row), (x2, y1 + row)], fill=(r, g, b, 255))
    # aplicar máscara redondeada al panel
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=255)
    panel_layer.putalpha(mask)
    img.alpha_composite(panel_layer)
    # borde sutil
    ImageDraw.Draw(img).rounded_rectangle([x1, y1, x2, y2], radius=radius, outline=(*PINK[:3], 60), width=1)


def render_banners_image(banners: list, cards_db: dict, next_mode: bool = False) -> Image.Image:
    """Renderiza la pantalla de banners activos."""
    n           = max(len(banners), 1)
    W           = 950
    ROW_H       = 300
    PAD         = 20
    TITLE_H     = 54
    ROW_Y_START = PAD + TITLE_H
    H           = ROW_Y_START + n * ROW_H + (n - 1) * PAD + PAD

    img  = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # título
    title_txt = "PROXIMOS BANNERS" if next_mode else "BANNERS ACTIVOS"
    ft = get_bold_font(28)
    draw_centered_text_with_outline(draw, title_txt, W // 2, PAD + 4, ft, PINK, stroke=2)

    if not banners:
        fm = get_bold_font(20)
        draw_centered_text_with_outline(draw, "No hay banners activos.", W // 2, H // 2, fm, GRAY, stroke=0)
        return img

    CARD_W = 160
    CARD_H = 224

    for i, banner in enumerate(banners):
        row_y = ROW_Y_START + i * (ROW_H + PAD)

        # panel con degradé morado-rosado
        _draw_panel_gradient(img, PAD, row_y, W - PAD, row_y + ROW_H)
        draw = ImageDraw.Draw(img)

        # imagen de la carta
        col     = banner.get("collection", "")
        name    = banner.get("card", "")
        meta    = (cards_db.get(col) or {}).get(name) or {}
        img_rel = meta.get("img", "")
        card_img = _load_card_img(img_rel, CARD_W, CARD_H) if img_rel else Image.new("RGBA", (CARD_W, CARD_H), ACCENT)

        cmask = Image.new("L", (CARD_W, CARD_H), 0)
        ImageDraw.Draw(cmask).rounded_rectangle([0, 0, CARD_W - 1, CARD_H - 1], radius=14, fill=255)
        card_img.putalpha(cmask)

        cx = PAD + 24
        cy = row_y + (ROW_H - CARD_H) // 2
        img.paste(card_img, (cx, cy), card_img)

        # brillo rosa en borde de la carta
        glow = Image.new("RGBA", (CARD_W + 6, CARD_H + 6), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle(
            [0, 0, CARD_W + 5, CARD_H + 5], radius=16, outline=(*PINK[:3], 130), width=3
        )
        img.alpha_composite(glow, (cx - 3, cy - 3))
        draw = ImageDraw.Draw(img)

        # textos a la derecha
        tx = cx + CARD_W + 30
        ty = row_y + 28

        fid = get_bold_font(13)
        draw.text((tx, ty), f"BANNER #{banner['id']}", font=fid, fill=(200, 160, 220, 255))

        fn = fit_font_to_width(draw, name.upper(), W - tx - PAD - 20, 38, min_size=20)
        draw_centered_text_with_outline(draw, name.upper(), tx + (W - tx - PAD) // 2, ty + 22, fn, WHITE, stroke=2)

        lx1 = tx
        lx2 = W - PAD - 24
        ly  = ty + 72
        draw.line([(lx1, ly), (lx2, ly)], fill=(*PINK[:3], 180), width=2)

        fc = get_bold_font(18)
        draw_centered_text_with_outline(draw, col.upper(), tx + (W - tx - PAD) // 2, ly + 14, fc, PINK, stroke=1)

        fg = get_bold_font(13)
        tag_txt = "✦ RAREZA GACHA"
        tbbox = draw.textbbox((0, 0), tag_txt, font=fg)
        tw, th = tbbox[2] - tbbox[0], tbbox[3] - tbbox[1]
        tag_x  = tx
        tag_y  = ly + 46
        draw.rounded_rectangle([tag_x - 6, tag_y - 4, tag_x + tw + 6, tag_y + th + 4], radius=8, fill=(80, 0, 65, 220))
        draw.text((tag_x, tag_y), tag_txt, font=fg, fill=PINK)

        # tiempo restante / llegada
        ft2 = get_bold_font(15)
        if next_mode:
            target   = banner.get("_start", date.today())
            span_str = _time_until_str(target)
            time_txt = f"Llega en {span_str}"
        else:
            target   = banner.get("_end", date.today())
            span_str = _time_until_str(target)
            time_txt = f"{span_str} restante{'s' if not span_str.endswith('m') else ''}"
        draw_centered_text_with_outline(
            draw, time_txt, tx + (W - tx - PAD) // 2, row_y + ROW_H - 28, ft2, GOLD, stroke=1
        )

        fp   = get_bold_font(13)
        ptxt = "Prob. carta: 1.200%  •  Pity: 90 tiradas  •  160 monedas/tirada"
        draw.text((tx, row_y + ROW_H - 52), ptxt, font=fp, fill=(170, 140, 185, 255))

    return img


def render_pull_result(results: list, cards_db: dict, username: str) -> Image.Image:
    """Renderiza los resultados de 1 o 10 tiradas en una imagen."""
    n    = len(results)
    W    = 950
    ITEM_H = 80
    PAD  = 16
    H    = PAD + 50 + n * (ITEM_H + 8) + PAD

    img  = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    ft = get_bold_font(22)
    draw_centered_text_with_outline(draw, f"Tiradas de {username}", W // 2, PAD + 6, ft, WHITE, stroke=1)

    for i, r in enumerate(results):
        iy = PAD + 50 + i * (ITEM_H + 8)
        t  = r["type"]

        if t == "gacha_card":
            fill   = (60, 0, 50, 255)
            border = PINK
            card_name = r.get("card") or r.get("name", "?")
            label  = f"✦ CARTA GACHA — {card_name}  ({r['collection']})"
            col    = PINK
        elif t == "4star":
            fill   = (40, 35, 0, 255)
            border = GOLD
            tipo   = "Marco" if r["item_type"] == "frame" else "Fondo"
            label  = f"★ {tipo}: {r['name']}"
            col    = GOLD
        elif t == "compensation":
            fill   = (20, 20, 35, 255)
            border = (80, 80, 120, 255)
            label  = f"✦ {r.get('card') or r.get('name', '?')}  (Gacha)"
            col    = (180, 180, 220, 255)
        else:
            fill   = (25, 25, 25, 255)
            border = (70, 70, 70, 255)
            label  = f"💰  +{r.get('amount', 0)} oro"
            col    = GRAY

        draw.rounded_rectangle([PAD, iy, W - PAD, iy + ITEM_H], radius=10, fill=fill, outline=border, width=2)

        # número de tirada
        fn = get_bold_font(14)
        draw.text((PAD + 12, iy + (ITEM_H - 16) // 2), f"#{i + 1}", font=fn, fill=GRAY)

        # descripción
        fl = get_bold_font(18)
        fl = fit_font_to_width(draw, label, W - PAD * 2 - 60, 18, min_size=13)
        draw.text((PAD + 50, iy + (ITEM_H - 20) // 2), label, font=fl, fill=col)

    return img
