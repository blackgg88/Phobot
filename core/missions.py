from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from core.clock import AR_TZ, today_ar

# ── Definiciones ────────────────────────────────────────────────────────────

MISSIONS = [
    {
        "id":    "msg_5",
        "label": "Enviar 5 mensajes",
        "key":   "msg",
        "goal":  5,
        "reward": 10,
    },
    {
        "id":    "voice_30m",
        "label": "Ingresar 30 minutos a llamada",
        "key":   "voice_seconds",
        "goal":  1800,   # 30 min en segundos
        "reward": 10,
    },
    {
        "id":    "drops_5",
        "label": "Tirar cartas 5 veces",
        "key":   "drops",
        "goal":  5,
        "reward": 10,
    },
    {
        "id":    "claims_5",
        "label": "Agarrar 5 cartas",
        "key":   "claims",
        "goal":  5,
        "reward": 10,
    },
    {
        "id":    "sells_3",
        "label": "Vender 3 cartas",
        "key":   "sells",
        "goal":  3,
        "reward": 10,
    },
]

MISSION_BY_ID = {m["id"]: m for m in MISSIONS}


# ── Gestión de datos ────────────────────────────────────────────────────────

def _fresh() -> dict:
    return {
        "date":          today_ar(),
        "msg":           0,
        "voice_seconds": 0,
        "drops":         0,
        "claims":        0,
        "sells":         0,
        "rewarded":      [],   # IDs de misiones ya pagadas hoy
    }


def ensure_missions(users: dict, uid: str) -> dict:
    """Devuelve el dict de misiones del usuario, reseteando si cambió el día."""
    data = users[uid].setdefault("missions", _fresh())
    if data.get("date") != today_ar():
        data = _fresh()
        users[uid]["missions"] = data
    return data


def progress(users: dict, uid: str, key: str, amount: int = 1) -> List[Tuple[str, int]]:
    """
    Incrementa `key` en `amount`. Retorna lista de (label, reward) de misiones
    recién completadas (para notificar/dar oro).
    """
    data    = ensure_missions(users, uid)
    data[key] = data.get(key, 0) + amount
    newly   = []

    for m in MISSIONS:
        if m["key"] != key:
            continue
        if m["id"] in data["rewarded"]:
            continue
        if data[key] >= m["goal"]:
            data["rewarded"].append(m["id"])
            newly.append((m["label"], m["reward"]))

    return newly


# ── Tiempo hasta reset ──────────────────────────────────────────────────────

def seconds_until_reset() -> int:
    """Segundos hasta las 00:00 hora Argentina."""
    now      = datetime.now(AR_TZ)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def format_reset_countdown() -> str:
    s   = seconds_until_reset()
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
