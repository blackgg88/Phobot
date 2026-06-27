from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Set, Tuple

from config import (
    CODE_CHARS, CODE_LEN, RARITY_ORDER, VALUE_RANGES,
)
from core.users import normalize_wish


# ── Normalization ──────────────────────────────────────────

def normalize_cards(cards_db: dict) -> dict:
    normalized = {}
    for collection, chars in (cards_db or {}).items():
        if not isinstance(chars, dict):
            continue
        normalized[collection] = {}
        for name, data in chars.items():
            if isinstance(data, str):
                normalized[collection][name] = {"img": data, "rarity": "common", "chance": 1}
            elif isinstance(data, dict):
                normalized[collection][name] = {
                    "img": data.get("img"),
                    "rarity": (data.get("rarity", "common") or "common").lower(),
                    "chance": data.get("chance", 1),
                }
    return normalized


def rarity_from_cards_db(cards_db: dict, collection: str, name: str) -> str:
    meta = (cards_db.get(collection) or {}).get(name)
    if not meta:
        return "common"
    return ((meta.get("rarity") or "common")).lower()


def rarity_es(r: str) -> str:
    from config import RARITY_LABEL_ES
    return RARITY_LABEL_ES.get((r or "common").lower(), r)


def rarity_es_upper(r: str) -> str:
    return rarity_es(r).upper()


# ── Code generation ────────────────────────────────────────

def all_existing_codes(users: dict) -> Set[str]:
    s: Set[str] = set()
    for _uid, data in (users or {}).items():
        for c in (data.get("cards") or []):
            if isinstance(c, dict):
                code = (c.get("code") or "").strip().lower()
                if code:
                    s.add(code)
    return s


def gen_unique_code(existing: Set[str]) -> str:
    while True:
        code = "".join(random.choice(CODE_CHARS) for _ in range(CODE_LEN))
        if code not in existing:
            existing.add(code)
            return code


def gen_value_number(rarity: str) -> int:
    lo, hi = VALUE_RANGES.get((rarity or "common").lower(), (1, 4000))
    return random.randint(lo, hi)


# ── Card instance ──────────────────────────────────────────

def normalize_card_instance(c: dict, cards_db: dict, existing_codes: Set[str]) -> dict:
    collection = str(c.get("collection", "")).strip()
    name       = str(c.get("name", "")).strip()
    rarity     = (c.get("rarity") or rarity_from_cards_db(cards_db, collection, name) or "common").lower()

    code  = (c.get("code") or "").strip().lower()
    valid = code and len(code) == CODE_LEN and all(ch in CODE_CHARS for ch in code)

    if valid and code not in existing_codes:
        existing_codes.add(code)
    else:
        code = gen_unique_code(existing_codes)

    try:
        value = int(c.get("value", None))
    except (TypeError, ValueError):
        value = gen_value_number(rarity)

    frame_id = c.get("frame_id")
    try:
        frame_id = int(frame_id) if frame_id is not None else None
    except Exception:
        frame_id = None

    gen = c.get("gen")
    try:
        gen = int(gen) if gen is not None else None
    except (TypeError, ValueError):
        gen = None

    return {
        "collection": collection,
        "name":       name,
        "code":       code,
        "value":      value,
        "rarity":     rarity,
        "frame_id":   frame_id,
        "token_code": c.get("token_code") or None,
        "token_img":  c.get("token_img")  or None,
        "gen":        gen,
    }


def create_card_instance_from_meta(collection: str, name: str, cards_db: dict, users: dict) -> dict:
    existing = all_existing_codes(users)
    rarity = rarity_from_cards_db(cards_db, collection, name)
    inst = {"collection": collection, "name": name, "rarity": rarity}
    return normalize_card_instance(inst, cards_db, existing)


def find_instance_by_code(cards_list: list, code: str) -> Optional[dict]:
    code = str(code).strip().lower()
    for inst in cards_list:
        if isinstance(inst, dict) and str(inst.get("code", "")).strip().lower() == code:
            return inst
    return None


# ── Migration ──────────────────────────────────────────────

def migrate_users_cards(users: dict, cards_db: dict) -> bool:
    from core.users import ensure_user
    changed = False
    existing: Set[str] = set()

    for uid, data in (users or {}).items():
        ensure_user(users, uid)
        raw = data.get("cards", [])
        if not isinstance(raw, list):
            raw = []
            data["cards"] = raw
            changed = True

        new_cards = []
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                col, nm = item[0], item[1]
                rar = rarity_from_cards_db(cards_db, col, nm)
                inst = normalize_card_instance({"collection": col, "name": nm, "rarity": rar}, cards_db, existing)
                new_cards.append(inst)
                changed = True
            elif isinstance(item, dict):
                inst = normalize_card_instance(item, cards_db, existing)
                if _instance_changed(item, inst):
                    changed = True
                new_cards.append(inst)
            else:
                changed = True
        data["cards"] = new_cards

    return changed


def _instance_changed(before: dict, after: dict) -> bool:
    return (
        str(before.get("collection", "")).strip() != after["collection"]
        or str(before.get("name", "")).strip() != after["name"]
        or str(before.get("code", "")).strip().lower() != after["code"]
        or (str(before.get("rarity", "")).strip().lower() or "common") != after["rarity"]
    )


# ── Pool / picking ─────────────────────────────────────────

def build_active_pool(cards_db: dict, active_collections: list) -> Tuple[list, list]:
    pool = []
    weights = []
    for collection, chars in cards_db.items():
        if collection not in active_collections:
            continue
        for name, data in chars.items():
            if not data.get("img"):
                continue
            rarity = (data.get("rarity", "common") or "common").lower()
            if rarity == "gacha":
                continue   # las cartas gacha solo salen en banners
            chance = float(data.get("chance", 1))
            pool.append({
                "collection": collection,
                "name":       name,
                "img":        data["img"],
                "rarity":     rarity,
                "chance":     chance,
            })
            weights.append(chance)
    return pool, weights


def pick_unique(pool: list, weights: list, k: int) -> Optional[list]:
    if len(pool) < k:
        return None
    chosen = []
    used: Set[Tuple[str, str]] = set()
    tries = 0
    while len(chosen) < k and tries < 4000:
        tries += 1
        c = random.choices(pool, weights=weights, k=1)[0]
        key = (c["collection"], c["name"])
        if key in used:
            continue
        used.add(key)
        chosen.append(c)
    return chosen if len(chosen) == k else None


# ── Search ─────────────────────────────────────────────────

def find_card_matches(cards_db: dict, query: str) -> List[Tuple[str, str]]:
    nrm = normalize_wish(query)
    matches: List[Tuple[str, str]] = []
    for collection, chars in (cards_db or {}).items():
        if not isinstance(chars, dict):
            continue
        for name in chars.keys():
            if normalize_wish(name) == nrm:
                matches.append((str(name), str(collection)))
    matches.sort(key=lambda x: (x[0].lower(), x[1].lower()))
    return matches


async def choose_match_by_number(bot, ctx, matches: List[Tuple[str, str]], *, title: str = "Elegí uno") -> Optional[Tuple[str, str]]:
    import asyncio
    import discord
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    lines = [f"{i}. {name} - {col}" for i, (name, col) in enumerate(matches, start=1)]
    e = discord.Embed(title=title, description="\n".join(lines), color=0x3498db)
    e.set_footer(text="Respondé con 1, 2, 3... (timeout 30s)")
    await ctx.send(embed=e)

    def check(m):
        return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏱️ Se venció el tiempo.")
        return None

    raw = (msg.content or "").strip()
    if not raw.isdigit():
        await ctx.send("Eso no fue un número 😅")
        return None
    k = int(raw)
    if k < 1 or k > len(matches):
        await ctx.send("Ese número no existe en la lista 😅")
        return None
    return matches[k - 1]
