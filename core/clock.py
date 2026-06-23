from __future__ import annotations

from datetime import datetime, timezone, timedelta

# Argentina nunca aplica horario de verano — siempre UTC-3
AR_TZ = timezone(timedelta(hours=-3))


def now_ar() -> datetime:
    return datetime.now(AR_TZ)


def today_ar() -> str:
    """Fecha actual en Argentina como 'YYYY-MM-DD'."""
    return now_ar().strftime("%Y-%m-%d")


def week_key_ar() -> str:
    """Clave de semana ISO en Argentina: 'YYYY-W##'."""
    dt = now_ar()
    return f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"


def format_ar(fmt: str = "%d/%m/%Y %H:%M") -> str:
    return now_ar().strftime(fmt)
