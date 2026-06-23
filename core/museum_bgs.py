from __future__ import annotations

import os
from config import BASE_DIR
from core.storage import load_json, save_json


def _path() -> str:
    return os.path.join(BASE_DIR, "data", "museum_backgrounds.json")


def load_museum_bg_catalog() -> dict:
    return load_json(_path(), {})


def get_user_owned_bgs(users: dict, uid: str) -> list:
    return users.get(uid, {}).get("museum_bgs_owned", [])


def give_user_bg(users: dict, uid: str, bg_id: str) -> None:
    owned = users[uid].setdefault("museum_bgs_owned", [])
    if bg_id not in owned:
        owned.append(bg_id)
