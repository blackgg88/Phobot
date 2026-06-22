from __future__ import annotations

import random
from typing import List, Optional, Set, Tuple

from config import TOKEN_CODE_CHARS, TOKEN_CODE_LEN, TOKEN_PREFIX
from core.storage import get_tokens_path, load_json


def is_token_code(code: str) -> bool:
    code = (code or "").strip().lower()
    if len(code) != TOKEN_CODE_LEN:
        return False
    if not code.startswith(TOKEN_PREFIX):
        return False
    tail = code[1:]
    return len(tail) == 5 and all(ch in TOKEN_CODE_CHARS for ch in tail)


def normalize_token_code(code: str) -> str:
    return (code or "").strip().lower()


def all_existing_token_codes(users: dict) -> Set[str]:
    s: Set[str] = set()
    for _uid, data in (users or {}).items():
        if not isinstance(data, dict):
            continue
        for t in (data.get("tokens") or []):
            if isinstance(t, dict):
                c = normalize_token_code(t.get("code") or t.get("tcode") or "")
            else:
                c = normalize_token_code(str(t))
            if is_token_code(c):
                s.add(c)
    return s


def gen_unique_token_code(existing: Set[str]) -> str:
    while True:
        tail = "".join(random.choice(TOKEN_CODE_CHARS) for _ in range(5))
        c = TOKEN_PREFIX + tail
        if c not in existing:
            existing.add(c)
            return c


def load_tokens_db() -> dict:
    try:
        data = load_json(get_tokens_path(), {})
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def flatten_tokens_db(tokens_db: dict) -> List[Tuple[str, str, str]]:
    out: List[Tuple[str, str, str]] = []
    for collection, chars in (tokens_db or {}).items():
        if not isinstance(chars, dict):
            continue
        for name, imgs in chars.items():
            if isinstance(imgs, list):
                for img in imgs:
                    if isinstance(img, str) and img.strip():
                        out.append((str(collection), str(name), img.strip()))
    return out


def token_variants_for(cards_db: dict, tokens_db: dict, *, collection: str, name: str) -> List[str]:
    from core.users import normalize_wish
    col = next((k for k in (tokens_db or {}) if str(k).lower() == str(collection).lower()), None)
    if col is None:
        return []
    chars = tokens_db[col]
    if not isinstance(chars, dict):
        return []
    nrm = normalize_wish(name)
    tgt = next((nm for nm in chars if normalize_wish(nm) == nrm), None)
    if tgt is None:
        return []
    imgs = chars[tgt]
    return [str(x).strip() for x in (imgs or []) if isinstance(x, str) and str(x).strip()]


def find_token_by_code(tokens: list, code: str) -> Optional[dict]:
    code = normalize_token_code(code)
    if not is_token_code(code):
        return None
    for t in (tokens or []):
        if isinstance(t, dict) and normalize_token_code(t.get("code") or t.get("tcode") or "") == code:
            return t
    return None


def sorted_tokens(tokens: List[dict], mode: str) -> List[dict]:
    mode = (mode or "ultimos").lower().strip()
    toks = [t for t in (tokens or []) if isinstance(t, dict) and is_token_code(t.get("code") or t.get("tcode") or "")]

    def ts(t):
        try:
            return float(t.get("ts", 0) or 0)
        except Exception:
            return 0.0

    if mode in ("serie", "series"):
        toks.sort(key=lambda t: (str(t.get("collection", "")).lower(), str(t.get("name", "")).lower(), -ts(t)))
    elif mode in ("az", "a-z", "alfabetico", "alfabético"):
        toks.sort(key=lambda t: (str(t.get("name", "")).lower(), str(t.get("collection", "")).lower(), -ts(t)))
    elif mode in ("primeros", "oldest", "asc"):
        toks.sort(key=lambda t: (ts(t), str(t.get("name", "")).lower()))
    else:
        toks.sort(key=lambda t: (-ts(t), str(t.get("name", "")).lower()))
    return toks
