from __future__ import annotations

from typing import Dict, Optional

from core.storage import load_json
from config import BASE_DIR, FRAME_SIZE

import os

FRAMES_PATH = os.path.join(BASE_DIR, "data", "frames.json")


def load_frames_catalog() -> Dict[int, dict]:
    raw = load_json(FRAMES_PATH, {})
    if not isinstance(raw, dict):
        raw = {}

    out: Dict[int, dict] = {}
    for k, v in raw.items():
        try:
            fid = int(k)
        except Exception:
            continue
        if not isinstance(v, dict):
            continue
        name  = str(v.get("name", f"Marco {fid}")).strip() or f"Marco {fid}"
        price = v.get("price", 0)
        try:
            price = int(price)
        except Exception:
            price = 0
        img  = str(v.get("img", "")).strip() or None
        shop = bool(v.get("shop", True))
        out[fid] = {"name": name, "price": max(0, price), "img": img, "shop": shop}

    return out


def get_frame_meta(fid: int) -> Optional[dict]:
    return load_frames_catalog().get(int(fid))
