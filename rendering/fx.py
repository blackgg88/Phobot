from __future__ import annotations

import os
from typing import Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter
from config import BASE_DIR, CARD_SIZE, FRAME_SIZE, RARITY_STYLES
from rendering.fonts import get_bold_font

HOLO_GEN_THRESHOLD = 30


def safe_open_image(path: str, size: Tuple[int, int] = CARD_SIZE) -> Image.Image:
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", size, (35, 35, 35, 255))
        ImageDraw.Draw(img).text((12, 12), "Imagen\ninválida", fill=(255, 255, 255, 255))
        return img


def apply_rarity_fx(card_rgba: Image.Image, color_rgba: Tuple) -> Image.Image:
    if color_rgba is None:
        return card_rgba
    w, h = card_rgba.size
    r, g, b, _ = color_rgba
    alpha = card_rgba.split()[-1]
    blurred = alpha.filter(ImageFilter.GaussianBlur(10))
    halo = ImageChops.subtract(blurred, alpha)
    halo_layer = Image.new("RGBA", (w, h), (r, g, b, 0))
    halo_layer.putalpha(halo)
    out = Image.alpha_composite(halo_layer, card_rgba)
    draw = ImageDraw.Draw(out)
    border_w = 6
    for i in range(border_w):
        draw.rounded_rectangle([i, i, w - 1 - i, h - 1 - i], radius=max(1, 18 - i), outline=(r, g, b, 255))
    # recortar esquinas redondeadas
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=255)
    out.putalpha(mask)
    return out


def apply_frame_overlay(card_img: Image.Image, frame_meta: dict, holo: bool = False) -> Image.Image:
    if not frame_meta:
        return card_img
    rel = frame_meta.get("img")
    if not rel:
        return card_img

    full = os.path.join(BASE_DIR, "images", rel)
    card_rgba = card_img.convert("RGBA")
    if card_rgba.size != CARD_SIZE:
        try:
            card_rgba = card_rgba.resize(CARD_SIZE, Image.LANCZOS)
        except Exception:
            card_rgba = card_rgba.resize(CARD_SIZE)

    # si es holo, aplicar solo el shimmer iridiscente (sin borde) al card
    if holo:
        card_rgba = apply_holo_shimmer(card_rgba)
        if card_rgba.size != CARD_SIZE:
            card_rgba = card_rgba.resize(CARD_SIZE, Image.LANCZOS)

    frame = safe_open_image(full, size=FRAME_SIZE).convert("RGBA")
    if frame.size != FRAME_SIZE:
        try:
            frame = frame.resize(FRAME_SIZE, Image.LANCZOS)
        except Exception:
            frame = frame.resize(FRAME_SIZE)

    out = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
    ox = (FRAME_SIZE[0] - CARD_SIZE[0]) // 2
    oy = (FRAME_SIZE[1] - CARD_SIZE[1]) // 2
    out.paste(card_rgba, (ox, oy), card_rgba)
    return Image.alpha_composite(out, frame)


def apply_holo_shimmer(card_rgba: Image.Image) -> Image.Image:
    """Solo el overlay iridiscente diagonal, sin borde arcoíris ni glow."""
    w, h = card_rgba.size
    rainbow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rainbow)
    palette = [
        (200, 150, 255, 50), (140, 180, 255, 45), (130, 240, 220, 42),
        (190, 250, 155, 40), (255, 245, 145, 42), (255, 175, 210, 48),
        (215, 135, 255, 50),
    ]
    sw = (w + h) // len(palette) + 12
    for i, col in enumerate(palette):
        ox = i * sw - h
        poly = [(ox, 0), (ox + sw, 0), (ox + sw + h, h), (ox + h, h)]
        dr.polygon(poly, fill=col)
    rainbow = rainbow.filter(ImageFilter.GaussianBlur(20))
    return Image.alpha_composite(card_rgba.convert("RGBA"), rainbow)


def apply_frame_overlay_scaled(card_img: Image.Image, frame_meta: dict) -> Image.Image:
    """
    Igual que apply_frame_overlay pero escala el marco para que se ajuste
    exactamente al tamaño de la carta recibida (útil para cartas drop 580×900).
    El marco se escala manteniendo la misma relación de aspecto de superposición.
    """
    if not frame_meta:
        return card_img
    rel = frame_meta.get("img")
    if not rel:
        return card_img

    cw, ch = card_img.size
    full  = os.path.join(BASE_DIR, "images", rel)

    # Calcular el tamaño del marco escalado: misma proporción extra que FRAME vs CARD
    extra_x = FRAME_SIZE[0] - CARD_SIZE[0]   # px extra horizontal del marco original
    extra_y = FRAME_SIZE[1] - CARD_SIZE[1]   # px extra vertical
    scale   = max(cw / CARD_SIZE[0], ch / CARD_SIZE[1])
    fw = int(FRAME_SIZE[0] * scale)
    fh = int(FRAME_SIZE[1] * scale)

    frame = safe_open_image(full, size=(fw, fh)).convert("RGBA").resize((fw, fh), Image.LANCZOS)

    # Centrar la carta dentro del marco escalado
    out = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    ox  = (fw - cw) // 2
    oy  = (fh - ch) // 2
    card_rgba = card_img.convert("RGBA")
    out.paste(card_rgba, (ox, oy), card_rgba)
    result = Image.alpha_composite(out, frame)

    # Recortar al tamaño de la carta (el marco sobresale alrededor)
    cx0 = ox
    cy0 = oy
    return result.crop((cx0, cy0, cx0 + cw, cy0 + ch))


def rarity_panel_color(rarity: str) -> Tuple:
    base = RARITY_STYLES.get((rarity or "common").lower(), RARITY_STYLES["common"])
    r, g, b, _ = base
    return (r, g, b, 170)


def apply_holo_fx(card_rgba: Image.Image) -> Image.Image:
    """Efecto tornasol para cartas con generación ≤ 30."""
    w, h = card_rgba.size

    # ── Overlay diagonal tornasol ──────────────────────────
    rainbow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(rainbow)
    palette = [
        (200, 150, 255, 50),   # lavanda
        (140, 180, 255, 45),   # azul cielo
        (130, 240, 220, 42),   # aguamarina
        (190, 250, 155, 40),   # lima
        (255, 245, 145, 42),   # amarillo
        (255, 175, 210, 48),   # rosa
        (215, 135, 255, 50),   # lila
    ]
    sw = (w + h) // len(palette) + 12
    for i, col in enumerate(palette):
        ox = i * sw - h
        poly = [(ox, 0), (ox + sw, 0), (ox + sw + h, h), (ox + h, h)]
        dr.polygon(poly, fill=col)
    rainbow = rainbow.filter(ImageFilter.GaussianBlur(20))
    out = Image.alpha_composite(card_rgba, rainbow)

    # ── Marco tornasol multicapa ───────────────────────────
    draw = ImageDraw.Draw(out)
    border_palette = [
        (225, 120, 255),   # violeta
        (130, 115, 255),   # índigo
        (95,  180, 255),   # azul
        (95,  240, 225),   # cyan
        (155, 255, 180),   # verde menta
        (255, 255, 145),   # amarillo
        (255, 175, 115),   # naranja
        (255, 125, 200),   # rosa
        (255, 135, 255),   # magenta
    ]
    total = 8
    for i in range(total - 1, -1, -1):
        t   = i / (total - 1)
        idx = int(t * (len(border_palette) - 1))
        r2, g2, b2 = border_palette[idx]
        a = max(120, 255 - i * 16)
        draw.rounded_rectangle(
            [i, i, w - 1 - i, h - 1 - i],
            radius=max(1, 18 - i),
            outline=(r2, g2, b2, a),
        )

    # brillo blanco exterior
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=18,
                           outline=(255, 255, 255, 230), width=2)
    # halo blanco interior suave
    draw.rounded_rectangle([total, total, w - 1 - total, h - 1 - total],
                           radius=max(1, 11), outline=(255, 255, 255, 55))

    # recortar esquinas redondeadas para evitar overflow
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=18, fill=255)
    out.putalpha(mask)

    return out


def is_holo(inst: dict) -> bool:
    """True si la instancia de carta tiene generación ≤ HOLO_GEN_THRESHOLD."""
    gen = inst.get("gen")
    if gen is None:
        return False
    try:
        return int(gen) <= HOLO_GEN_THRESHOLD
    except (ValueError, TypeError):
        return False
