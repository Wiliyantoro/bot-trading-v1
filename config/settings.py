# ==============================
# SETTINGS CONFIG
# ==============================

SYMBOL = "XAUUSDm"

LOT = 0.01

MULTIPLIER = 1.0

MAX_SPREAD = 0.5  # ✅ SEKARANG pakai harga, bukan points

MAGIC_NUMBER = 121241

SLIPPAGE = 10
# ✅ NEW (SL TP FIXED)
SL_POINTS = 800
TP_POINTS = 1200

# ==============================
# BREAK EVEN
# ==============================
BE_TRIGGER = 300  # points
BE_OFFSET = 20  # buffer biar gak ke-close cepat

# ==============================
# TRAILING
# ==============================
TRAILING_START = 400
TRAILING_STEP = 100
