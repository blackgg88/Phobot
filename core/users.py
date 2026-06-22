from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional, Set, Tuple

from config import CODE_CHARS, CODE_LEN
from core.storage import get_paths, save_json


# ── Ensure / save ──────────────────────────────────────────

def ensure_user(users: dict, user_id: str) -> None:
    if user_id not in users:
        users[user_id] = {
            "cards": [],
            "last_pull": 0,
            "last_drop": 0,
            "last_drop_take": 0,
            "gold": 0,
            "last_daily": 0,
            "last_work": 0,
            "wishlist": [],
            "museum": [],
            "frames": [],
            "tokens": [],
            "packs": {"common": 0, "rare": 0, "epic": 0, "legendary": 0, "mythic": 0},
        }

    u = users[user_id]
    u.setdefault("cards", [])
    u.setdefault("last_pull", 0)
    u.setdefault("last_drop", 0)
    u.setdefault("last_drop_take", 0)
    u.setdefault("gold", 0)
    u.setdefault("last_daily", 0)
    u.setdefault("last_work", 0)
    u.setdefault("wishlist", [])
    u.setdefault("museum", [])
    u.setdefault("frames", [])
    u.setdefault("tokens", [])
    u.setdefault("packs", {})
    u.setdefault("cat_game", {})

    # wishlist
    wl = u.get("wishlist", [])
    u["wishlist"] = [s.strip() for s in wl if isinstance(s, str) and s.strip()]

    # frames
    fr = u.get("frames", [])
    clean_fr = []
    for x in fr:
        try:
            clean_fr.append(int(x))
        except Exception:
            pass
    u["frames"] = clean_fr

    # packs
    packs = u.get("packs", {})
    if not isinstance(packs, dict):
        packs = {}
    for k in ["common", "rare", "epic", "legendary", "mythic"]:
        try:
            packs[k] = max(0, int(packs.get(k, 0)))
        except Exception:
            packs[k] = 0
    u["packs"] = packs

    # museum
    ms = u.get("museum", [])
    if not isinstance(ms, list):
        ms = []
    ms2 = []
    for s in ms:
        if isinstance(s, str):
            code = s.strip().lower()
            if code and len(code) == CODE_LEN and all(ch in CODE_CHARS for ch in code):
                if code not in ms2:
                    ms2.append(code)
    u["museum"] = ms2[:10]


def save_users(users: dict) -> None:
    users_path, _, _ = get_paths()
    save_json(users_path, users)


# ── Query helpers ──────────────────────────────────────────

def user_owned_pairs(card_instances: List[dict]) -> Set[Tuple[str, str]]:
    s: Set[Tuple[str, str]] = set()
    for c in card_instances:
        if isinstance(c, dict):
            s.add((c.get("collection"), c.get("name")))
    return s


def counts_by_char(card_instances: List[dict]) -> Counter:
    cnt: Counter = Counter()
    for c in card_instances:
        if isinstance(c, dict):
            cnt[(c.get("collection"), c.get("name"))] += 1
    return cnt


# ── Duplicate removal ──────────────────────────────────────

def remove_one_extra_instance(cards_list: List[dict], collection: str, name: str) -> Optional[dict]:
    idxs = [i for i, c in enumerate(cards_list)
            if isinstance(c, dict) and c.get("collection") == collection and c.get("name") == name]
    if len(idxs) <= 1:
        return None

    worst_i = max(idxs, key=lambda i: _val(cards_list[i]))
    return cards_list.pop(worst_i)


def remove_all_extras_instances(cards_list: List[dict], collection: str, name: str) -> List[dict]:
    idxs = [i for i, c in enumerate(cards_list)
            if isinstance(c, dict) and c.get("collection") == collection and c.get("name") == name]
    if len(idxs) <= 1:
        return []

    pairs = sorted(((cards_list[i].get("value", 999999), i) for i in idxs), reverse=True, key=lambda x: x[0])
    to_remove = sorted([i for _, i in pairs[:-1]], reverse=True)
    removed = [cards_list.pop(i) for i in to_remove]
    return removed


def _val(card: dict) -> int:
    try:
        return int(card.get("value", 999999))
    except Exception:
        return 999999


# ── Wishlist ───────────────────────────────────────────────

def normalize_wish(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip()).lower()


# ── Misc helpers used by commands ──────────────────────────

def pick_target_member(ctx, member):
    return member if member is not None else ctx.author


def human_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"
