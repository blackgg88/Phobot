from __future__ import annotations

from typing import List, Dict

# ── Definiciones ───────────────────────────────────────────

ACHIEVEMENTS: List[Dict] = [
    # 💬 Mensajes
    {
        "id":    "msg_100",
        "title": "Parlanchín",
        "desc":  "Enviar 100 mensajes",
        "cat":   "💬 Mensajes",
    },
    {
        "id":    "msg_500",
        "title": "Hablador",
        "desc":  "Enviar 500 mensajes",
        "cat":   "💬 Mensajes",
    },
    {
        "id":    "msg_10000",
        "title": "Incansable",
        "desc":  "Enviar 10.000 mensajes",
        "cat":   "💬 Mensajes",
    },
    {
        "id":    "streak_7",
        "title": "Rutinario",
        "desc":  "Escribir durante 7 días seguidos",
        "cat":   "💬 Mensajes",
    },
    {
        "id":    "streak_30",
        "title": "Dedicado",
        "desc":  "Escribir durante 30 días seguidos",
        "cat":   "💬 Mensajes",
    },
    {
        "id":    "reactions_100",
        "title": "Querido",
        "desc":  "Recibir 100 reacciones de usuarios",
        "cat":   "💬 Mensajes",
    },
    # 🎙️ Llamadas
    {
        "id":    "voice_first",
        "title": "Bienvenido al canal",
        "desc":  "Entrar a una llamada por primera vez",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_1h",
        "title": "Sociable",
        "desc":  "Estar 1 hora en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_10h",
        "title": "Compañero",
        "desc":  "Estar 10 horas en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_50h",
        "title": "Veterano",
        "desc":  "Estar 50 horas en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_100h",
        "title": "Incondicional",
        "desc":  "Estar 100 horas en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_500h",
        "title": "De la casa",
        "desc":  "Estar 500 horas en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_1000h",
        "title": "Leyenda",
        "desc":  "Estar 1000 horas en llamada",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "screen_share",
        "title": "Director",
        "desc":  "Compartir pantalla por primera vez",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_5people",
        "title": "Fiestero",
        "desc":  "Participar en una llamada con 5 o más personas",
        "cat":   "🎙️ Llamadas",
    },
    {
        "id":    "voice_week_24h",
        "title": "Maratonista",
        "desc":  "Acumular 24 horas de llamada en una semana",
        "cat":   "🎙️ Llamadas",
    },
    # ✨ Especiales
    {
        "id":    "msg_0333",
        "title": "Noctámbulo",
        "desc":  "Enviar un mensaje exactamente a las 03:33 (hora Argentina)",
        "cat":   "✨ Especiales",
    },
    {
        "id":    "msg_1000chars",
        "title": "Literato",
        "desc":  "Escribir un mensaje de más de 1.000 caracteres",
        "cat":   "✨ Especiales",
    },
]

ACH_BY_ID: Dict[str, Dict] = {a["id"]: a for a in ACHIEVEMENTS}
CATEGORIES: List[str] = list(dict.fromkeys(a["cat"] for a in ACHIEVEMENTS))


# ── Stats globales (no por servidor) ───────────────────────

def ensure_user_stats(users: dict, uid: str) -> dict:
    """
    Inicializa y devuelve las stats GLOBALES del usuario.
    Si había datos en guilds los migra y los une.
    """
    user = users[uid]

    # Inicializar claves globales si no existen
    user.setdefault("achievements",       [])
    user.setdefault("msg_count",          0)
    user.setdefault("last_msg_date",      "")
    user.setdefault("streak",             0)
    user.setdefault("reactions_received", 0)
    user.setdefault("voice_seconds",      0)
    user.setdefault("voice_week",         {})
    user.setdefault("screen_shared",      False)
    user.setdefault("max_voice_with",     0)

    # Migración única desde estructura por servidor (si existe)
    if user.get("guilds") and not user.get("_ach_migrated"):
        for gid, gdata in user["guilds"].items():
            if not isinstance(gdata, dict):
                continue
            # Unir logros
            for aid in gdata.get("achievements", []):
                if aid not in user["achievements"]:
                    user["achievements"].append(aid)
            # Acumular stats (tomar máximos/sumas)
            user["msg_count"]          = max(user["msg_count"],          gdata.get("msg_count", 0))
            user["streak"]             = max(user["streak"],             gdata.get("streak", 0))
            user["reactions_received"] = max(user["reactions_received"], gdata.get("reactions_received", 0))
            user["voice_seconds"]     += gdata.get("voice_seconds", 0)
            user["max_voice_with"]     = max(user["max_voice_with"],     gdata.get("max_voice_with", 0))
            if gdata.get("screen_shared"):
                user["screen_shared"] = True
            for wk, secs in gdata.get("voice_week", {}).items():
                user["voice_week"][wk] = user["voice_week"].get(wk, 0) + secs
            # Tomar la fecha de último mensaje más reciente
            gd = gdata.get("last_msg_date", "")
            if gd > user.get("last_msg_date", ""):
                user["last_msg_date"] = gd
        user["_ach_migrated"] = True

    return user


# Alias para compatibilidad con código que todavía llame a ensure_guild_stats
def ensure_guild_stats(users: dict, uid: str, guild_id: str) -> dict:
    return ensure_user_stats(users, uid)


# ── Chequeo de logros ───────────────────────────────────────

def check_and_award(stats: dict) -> List[str]:
    """
    Recibe el dict del usuario (stats globales).
    Devuelve lista de IDs de logros recién desbloqueados.
    """
    unlocked = stats["achievements"]
    newly    = []

    def award(aid: str):
        if aid not in unlocked:
            unlocked.append(aid)
            newly.append(aid)

    mc  = stats["msg_count"]
    sk  = stats["streak"]
    rxn = stats["reactions_received"]
    vs  = stats["voice_seconds"]
    vw  = stats.get("voice_week", {})
    max_week_s = max(vw.values(), default=0)

    if mc  >= 100:       award("msg_100")
    if mc  >= 500:       award("msg_500")
    if mc  >= 10_000:    award("msg_10000")
    if sk  >= 7:         award("streak_7")
    if sk  >= 30:        award("streak_30")
    if rxn >= 100:       award("reactions_100")

    if vs > 0:                               award("voice_first")
    if vs >= 3_600:                          award("voice_1h")
    if vs >= 36_000:                         award("voice_10h")
    if vs >= 180_000:                        award("voice_50h")
    if vs >= 360_000:                        award("voice_100h")
    if vs >= 1_800_000:                      award("voice_500h")
    if vs >= 3_600_000:                      award("voice_1000h")
    if stats.get("screen_shared"):           award("screen_share")
    if stats.get("max_voice_with", 0) >= 5:  award("voice_5people")
    if max_week_s >= 86_400:                 award("voice_week_24h")

    return newly
