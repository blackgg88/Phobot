from __future__ import annotations

import math
import random
import time

XP_COOLDOWN = 60  # segundos entre ganancias de XP


def xp_to_reach_level(level: int) -> int:
    """XP total acumulado para llegar al nivel `level` (nivel 1 = 0 XP)."""
    if level <= 1:
        return 0
    return (level - 1) * level // 2 * 100


def level_from_xp(xp: int) -> int:
    """Nivel actual dado el XP total."""
    if xp <= 0:
        return 1
    # nivel N requiere N*(N-1)/2 * 100 XP → resolver la cuadrática
    n = int((1 + math.sqrt(1 + 8 * xp / 100)) / 2)
    while xp_to_reach_level(n + 1) <= xp:
        n += 1
    return max(1, n)


def xp_progress(xp: int):
    """Retorna (level, xp_en_nivel_actual, xp_para_siguiente_nivel)."""
    level     = level_from_xp(xp)
    start_xp  = xp_to_reach_level(level)
    end_xp    = xp_to_reach_level(level + 1)
    current   = xp - start_xp
    needed    = end_xp - start_xp
    return level, current, needed


def try_add_xp(users: dict, uid: str) -> tuple[int, bool]:
    """
    Intenta dar XP al usuario (5-10 al azar), respetando el cooldown.
    Retorna (xp_ganado, subio_de_nivel).
    """
    now       = time.time()
    user      = users[uid]
    last_gain = user.get("last_xp_gain", 0)
    if (now - last_gain) < XP_COOLDOWN:
        return 0, False

    gain      = random.randint(5, 10)
    old_xp    = int(user.get("xp", 0))
    new_xp    = old_xp + gain
    old_level = level_from_xp(old_xp)
    new_level = level_from_xp(new_xp)

    user["xp"]           = new_xp
    user["last_xp_gain"] = now

    return gain, new_level > old_level
