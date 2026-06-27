from __future__ import annotations

import os
import random
from datetime import date, timedelta
from typing import Optional

from config import (
    BASE_DIR,
    BANNER_DURATION_DAYS, BANNER_GOLD_MIN, BANNER_GOLD_MAX,
    BANNER_PITY_HARD, BANNER_PITY_MINI,
    BANNER_PROB_GACHA, BANNER_PROB_4STAR,
)
from core.storage import load_json, save_json
from core.frames import load_frames_catalog
from core.museum_bgs import load_museum_bg_catalog

COMPENSATION_COLLECTION = "Gacha"
ROTATION_HISTORY_DEPTH  = 3   # cuántas rotaciones anteriores evitar al re-sortear


def _rotation_path() -> str:
    return os.path.join(BASE_DIR, "data", "banner_rotation.json")


def _load_rotation() -> dict:
    return load_json(_rotation_path(), {
        "current_start":   None,
        "current_banners": [],
        "history":         [],
    })


def _save_rotation(data: dict) -> None:
    save_json(_rotation_path(), data)


# ── Pool de cartas gacha disponibles para banners ────────────

def get_gacha_pool(cards_db: dict) -> list:
    """Todas las cartas de rareza 'gacha' excluyendo la colección Gacha."""
    pool = []
    for col, chars in cards_db.items():
        if col == COMPENSATION_COLLECTION:
            continue
        for name, meta in chars.items():
            if (meta.get("rarity") or "").lower() == "gacha":
                pool.append({"collection": col, "card": name, "img": meta.get("img", "")})
    return pool


def get_compensation_pool(cards_db: dict) -> list:
    """Cartas de la colección Gacha (compensación por tirada sin premio)."""
    return [
        {"collection": COMPENSATION_COLLECTION, "card": name, "img": meta.get("img", "")}
        for name, meta in (cards_db.get(COMPENSATION_COLLECTION) or {}).items()
    ]


# ── Rotación automática ───────────────────────────────────────

def _rotation_start_for_today() -> date:
    """Calcula el lunes más reciente para anclar la rotación a semanas."""
    today = date.today()
    return today - timedelta(days=today.weekday())   # lunes de esta semana


def _current_window_start() -> date:
    """Inicio de la ventana de 14 días activa en este momento."""
    monday = _rotation_start_for_today()
    # alineamos a bloques de 14 días desde una época fija (2026-06-22)
    epoch  = date(2026, 6, 22)
    days   = (monday - epoch).days
    block  = (days // BANNER_DURATION_DAYS) * BANNER_DURATION_DAYS
    return epoch + timedelta(days=block)


def _pick_new_banners(pool: list, history: list, n: int = 3) -> list:
    """Sortea n cartas del pool evitando las últimas ROTATION_HISTORY_DEPTH rotaciones."""
    excluded = {
        (b["collection"], b["card"])
        for rotation in history[-ROTATION_HISTORY_DEPTH:]
        for b in rotation
    }
    candidates = [b for b in pool if (b["collection"], b["card"]) not in excluded]
    # si el pool es muy pequeño, ignorar parte de la historia
    if len(candidates) < n:
        candidates = pool
    return random.sample(candidates, min(n, len(candidates)))


def _generate_next_pick(pool: list, history: list, current: list) -> list:
    """Sortea los próximos 3 banners excluyendo historial + actuales."""
    effective = history + ([current] if current else [])
    return _pick_new_banners(pool, effective)


def get_or_rotate_banners(cards_db: dict) -> list:
    """
    Devuelve los 3 banners activos. Si la rotación expiró, promueve los
    next_banners guardados (o sortea si no existen) y pre-genera los siguientes.
    """
    rot       = _load_rotation()
    win_start = _current_window_start()
    win_end   = win_start + timedelta(days=BANNER_DURATION_DAYS)

    stored_start = rot.get("current_start")
    needs_rotate = (stored_start != win_start.isoformat()) or not rot.get("current_banners")

    pool = get_gacha_pool(cards_db)

    if needs_rotate:
        if not pool:
            return []
        history = rot.get("history", [])

        # Usar next_banners pre-guardados; si no existen, sortear ahora
        saved_next = rot.get("next_banners") or []
        new_current = saved_next if saved_next else _pick_new_banners(pool, history)

        history = history + [new_current]

        # Pre-generar la SIGUIENTE rotación y guardarla ya
        new_next = _generate_next_pick(pool, history, new_current)

        rot["current_start"]   = win_start.isoformat()
        rot["current_banners"] = new_current
        rot["next_banners"]    = new_next
        rot["history"]         = history
        _save_rotation(rot)

    elif not rot.get("next_banners") and pool:
        # Bootstrap: primera vez, generar next_banners si faltan
        history = rot.get("history", [])
        current = rot.get("current_banners", [])
        rot["next_banners"] = _generate_next_pick(pool, history, current)
        _save_rotation(rot)

    banners = []
    for i, b in enumerate(rot["current_banners"], start=1):
        meta = (cards_db.get(b["collection"]) or {}).get(b["card"]) or {}
        banners.append({
            "id":         str(i),
            "name":       b["card"],
            "collection": b["collection"],
            "card":       b["card"],
            "img":        meta.get("img", b.get("img", "")),
            "_start":     win_start,
            "_end":       win_end,
        })
    return banners


def preview_next_banners(cards_db: dict) -> list:
    """Devuelve los 3 banners pre-guardados para la próxima rotación."""
    rot        = _load_rotation()
    win_start  = _current_window_start()
    next_start = win_start + timedelta(days=BANNER_DURATION_DAYS)
    next_end   = next_start + timedelta(days=BANNER_DURATION_DAYS)

    next_b = rot.get("next_banners") or []
    banners = []
    for i, b in enumerate(next_b, start=1):
        meta = (cards_db.get(b["collection"]) or {}).get(b["card"]) or {}
        banners.append({
            "id":         str(i),
            "name":       b["card"],
            "collection": b["collection"],
            "card":       b["card"],
            "img":        meta.get("img", b.get("img", "")),
            "_start":     next_start,
            "_end":       next_end,
        })
    return banners


def get_banner(banner_id: str, cards_db: dict) -> Optional[dict]:
    for b in get_or_rotate_banners(cards_db):
        if str(b["id"]) == str(banner_id):
            return b
    return None


# ── Pool de artículos 4★ ─────────────────────────────────────

def build_4star_pool() -> list:
    items = []
    for fid, meta in load_frames_catalog().items():
        items.append({"item_type": "frame", "id": str(fid), "name": meta.get("name", f"Marco {fid}")})
    for bid, meta in load_museum_bg_catalog().items():
        if meta.get("shop", False):
            items.append({"item_type": "museum_bg", "id": str(bid), "name": meta.get("name", f"Fondo {bid}")})
    return items


# ── Pity ─────────────────────────────────────────────────────

def get_pity(users: dict, uid: str) -> dict:
    return users[uid].setdefault("gacha_pity", {
        "pulls_since_gacha": 0,
        "pulls_since_4star": 0,
    })


# ── Tirada ────────────────────────────────────────────────────

def _single_roll(pity: dict, banner: dict, cards_db: dict) -> dict:
    pity["pulls_since_gacha"] += 1
    pity["pulls_since_4star"] += 1

    hard_pity = pity["pulls_since_gacha"] >= BANNER_PITY_HARD
    mini_pity = pity["pulls_since_4star"] >= BANNER_PITY_MINI

    roll = random.random()

    # Carta gacha featured ────────────────────────────────────
    if hard_pity or roll < BANNER_PROB_GACHA:
        col  = banner["collection"]
        name = banner["card"]
        pity["pulls_since_gacha"] = 0
        pity["pulls_since_4star"] = 0
        return {"type": "gacha_card", "collection": col, "card": name}

    # Artículo 4★ ─────────────────────────────────────────────
    if mini_pity or roll < BANNER_PROB_GACHA + BANNER_PROB_4STAR:
        pool = build_4star_pool()
        pity["pulls_since_4star"] = 0
        if pool:
            return {"type": "4star", **random.choice(pool)}

    # Compensación: carta de la colección Gacha ───────────────
    comp_pool = get_compensation_pool(cards_db)
    if comp_pool:
        picked = random.choice(comp_pool)
        return {"type": "compensation", **picked}

    # Fallback oro si no hay cartas de compensación definidas
    return {"type": "gold", "amount": random.randint(BANNER_GOLD_MIN, BANNER_GOLD_MAX)}


def do_pulls(users: dict, uid: str, banner: dict, cards_db: dict, count: int = 1) -> list:
    pity = get_pity(users, uid)
    return [_single_roll(pity, banner, cards_db) for _ in range(count)]


def apply_pull_results(users: dict, uid: str, results: list, cards_db: dict) -> None:
    from core.cards import create_card_instance_from_meta
    from core.museum_bgs import give_user_bg

    for r in results:
        t = r["type"]

        if t == "gold":
            users[uid]["gold"] = int(users[uid].get("gold", 0)) + r["amount"]

        elif t in ("gacha_card", "compensation"):
            col  = r["collection"]
            name = r.get("card") or r.get("name", "")
            inst = create_card_instance_from_meta(col, name, cards_db, users)
            inst["gen"] = random.randint(1, 9999)
            users[uid].setdefault("cards", []).append(inst)

        elif t == "4star":
            if r["item_type"] == "frame":
                users[uid].setdefault("frames", []).append(int(r["id"]))
            elif r["item_type"] == "museum_bg":
                give_user_bg(users, uid, r["id"])
