import os
import json
from config import BASE_DIR


def get_paths():
    base = os.path.join(BASE_DIR, "data")
    return (
        os.path.join(base, "users.json"),
        os.path.join(base, "cards.json"),
        os.path.join(base, "events.json"),
    )


def get_tokens_path() -> str:
    return os.path.join(BASE_DIR, "data", "tokens.json")


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
