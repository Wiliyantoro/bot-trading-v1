# ==============================
# SETTINGS CONFIG
# ==============================

SYMBOL = "XAUUSDm"

LOT = 0.01

MULTIPLIER = 1.2   # 🔥 sedikit lebih lebar entry

MAX_SPREAD = 0.5

MAGIC_NUMBER = 121241
SLIPPAGE = 10

# ==============================
# SL TP (ANTI NOISE)
# ==============================
SL_POINTS = 1500   # 🔥 jauh (anti spike)
TP_POINTS = 2500   # 🔥 RR lebih sehat

# ==============================
# BREAK EVEN
# ==============================
BE_TRIGGER = 800    # 🔥 tunggu profit dulu
BE_OFFSET = 100     # 🔥 aman dari noise

# ==============================
# TRAILING
# ==============================
TRAILING_START = 1200   # 🔥 mulai setelah profit cukup
TRAILING_STEP = 300     # 🔥 tidak terlalu rapat