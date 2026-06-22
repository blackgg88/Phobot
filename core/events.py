from __future__ import annotations

from typing import List, Optional

from core.storage import get_paths, load_json, save_json


def load_events_config() -> dict:
    _, _, events_path = get_paths()
    ev = load_json(events_path, {})
    if not isinstance(ev, dict):
        ev = {}

    def _norm(x):
        if not isinstance(x, list):
            return None
        return [v.strip() for v in x if isinstance(v, str) and v.strip()] or None

    return {
        "active_collections":       _norm(ev.get("active_collections")),
        "disabled_collections":     _norm(ev.get("disabled_collections", [])) or [],
        "shop_active_collections":  _norm(ev.get("shop_active_collections")),
        "shop_disabled_collections":_norm(ev.get("shop_disabled_collections", [])) or [],
    }


def save_events_config(*, active_collections=None, disabled_collections=None,
                       shop_active_collections=None, shop_disabled_collections=None) -> None:
    _, _, events_path = get_paths()
    cur = load_events_config()
    if active_collections       is not None: cur["active_collections"]        = active_collections
    if disabled_collections     is not None: cur["disabled_collections"]      = disabled_collections
    if shop_active_collections  is not None: cur["shop_active_collections"]   = shop_active_collections
    if shop_disabled_collections is not None: cur["shop_disabled_collections"] = shop_disabled_collections
    save_json(events_path, cur)


def load_events(cards_db: dict) -> List[str]:
    cfg      = load_events_config()
    all_cols = list(cards_db.keys())
    active   = cfg.get("active_collections")
    disabled = set(cfg.get("disabled_collections") or [])

    base  = [c for c in active if c in cards_db] if active else all_cols[:]
    final = [c for c in base if c not in disabled]
    return final if final else all_cols


def load_shop_collections(cards_db: dict) -> List[str]:
    cfg      = load_events_config()
    all_cols = list(cards_db.keys())
    active   = cfg.get("shop_active_collections")
    disabled = set(cfg.get("shop_disabled_collections") or [])

    base  = [c for c in active if c in cards_db] if active else all_cols[:]
    final = [c for c in base if c not in disabled]
    return final if final else all_cols
