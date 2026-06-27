import os
import string

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Cooldowns ──────────────────────────────────────────────
COOLDOWN          = 0              # pgacha:  pruebas (restaurar a 8 * 60 * 60)
DAILY_COOLDOWN    = 24 * 60 * 60  # pdaily: 24 h
WORK_COOLDOWN     = 30 * 60       # pwork:  30 m
DROP_COOLDOWN     = 8 * 60        # pdrop:   8 min
DROP_TAKE_COOLDOWN = 4 * 60       # agarrar drop: 4 min
DROP_PRIORITY_SECONDS = 3         # prioridad del dropeador

# ── Economía ───────────────────────────────────────────────
DAILY_REWARD = 20
WORK_MIN     = 1
WORK_MAX     = 10
BUY_ONE_COST = 300

SELL_VALUES = {
    "common":    5,
    "rare":     10,
    "epic":     15,
    "legendary":25,
    "mythic":   50,
    "gacha":   100,
}

# ── Casino ─────────────────────────────────────────────────
CASINO_MIN_BET = 1
CASINO_MAX_BET = 10

# ── Rarezas ────────────────────────────────────────────────
RARITY_ORDER = ["common", "rare", "epic", "legendary", "mythic", "gacha"]

RARITY_STYLES = {
    "common":    (120, 120, 120, 255),
    "rare":      (80,  160, 255, 255),
    "epic":      (138,  43, 226, 255),
    "legendary": (255, 215,   0, 255),
    "mythic":    (255,   0,   0, 255),
    "gacha":     (255, 120, 220, 255),
}

RARITY_LABEL_ES = {
    "common":    "Común",
    "rare":      "Rara",
    "epic":      "Épica",
    "legendary": "Legendaria",
    "mythic":    "Evento",
    "gacha":     "Gacha",
}

VALUE_RANGES = {
    "common":    (1, 4000),
    "rare":      (1, 3000),
    "epic":      (1, 2000),
    "legendary": (1, 1000),
    "mythic":    (1,  250),
}

# ── Banner gacha ────────────────────────────────────────────
BANNER_PULL_COST     = 160
BANNER_PULL10_COST   = 1600
BANNER_PITY_HARD     = 90
BANNER_PITY_MINI     = 10
BANNER_PROB_GACHA    = 0.012   # 1.2% por tirada
BANNER_PROB_4STAR    = 0.05    # 5% por tirada
BANNER_GOLD_MIN      = 5
BANNER_GOLD_MAX      = 30
BANNER_DURATION_DAYS = 14

# ── Códigos únicos ─────────────────────────────────────────
CODE_CHARS = string.ascii_lowercase + string.digits
CODE_LEN   = 6

# ── Tokens ─────────────────────────────────────────────────
TOKEN_DROP_CHANCE = 0.03   # 3 % por drop
TOKEN_PREFIX      = "!"
TOKEN_CODE_LEN    = 6      # incluye '!' + 5 chars
TOKEN_CODE_CHARS  = string.ascii_lowercase + string.digits

# ── Imágenes ───────────────────────────────────────────────
CARD_SIZE  = (300, 420)
FRAME_SIZE = (350, 470)

# ── Museo ──────────────────────────────────────────────────
MUSEUM_BACKGROUNDS = {
    "negro":       (18,  18,  18,  255),
    "gris":        (28,  28,  28,  255),
    "pastel_azul": (190, 210, 230, 255),
    "pastel_rosa": (235, 200, 210, 255),
    "pastel_verde":(200, 225, 210, 255),
    "arena":       (225, 215, 195, 255),
    "lavanda":     (210, 205, 230, 255),
}
DEFAULT_MUSEUM_BG = "negro"

# ── Bot ────────────────────────────────────────────────────
OWNER_ID = 1048304294492905576

# ⚠️  Mové el token a una variable de entorno en producción.
def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        print(val)
        raise RuntimeError(
            f"Variable de entorno '{name}' no definida. "
            "Agregala al archivo .env o al entorno del sistema."
        )
    return val

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv opcional; el env puede estar seteado a nivel sistema

BOT_TOKEN = _require_env("DISCORD_TOKEN")

