import os
import re
from pathlib import Path

import MetaTrader5 as mt5
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _require_env(name):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        raise ValueError(f"Missing required environment variable: {name}")
    return value.strip()


def _env_str(name):
    return _require_env(name)


def _env_int(name):
    return int(_require_env(name))


def _env_float(name):
    return float(_require_env(name))


def _env_int_default(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value.strip())


def _env_float_default(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value.strip())


def _env_bool(name):
    value = _require_env(name).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value for {name}: {value}")


def _env_list(name):
    value = _require_env(name)
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise ValueError(f"Environment variable {name} must contain at least one value")
    return items


TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M2": mt5.TIMEFRAME_M2,
    "M3": mt5.TIMEFRAME_M3,
    "M4": mt5.TIMEFRAME_M4,
    "M5": mt5.TIMEFRAME_M5,
    "M6": mt5.TIMEFRAME_M6,
    "M10": mt5.TIMEFRAME_M10,
    "M12": mt5.TIMEFRAME_M12,
    "M15": mt5.TIMEFRAME_M15,
    "M20": mt5.TIMEFRAME_M20,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H2": mt5.TIMEFRAME_H2,
    "H3": mt5.TIMEFRAME_H3,
    "H4": mt5.TIMEFRAME_H4,
    "H6": mt5.TIMEFRAME_H6,
    "H8": mt5.TIMEFRAME_H8,
    "H12": mt5.TIMEFRAME_H12,
    "D1": mt5.TIMEFRAME_D1,
    "W1": mt5.TIMEFRAME_W1,
    "MN1": mt5.TIMEFRAME_MN1,
}


def _env_timeframe(name):
    key = _require_env(name).upper()
    if key not in TIMEFRAME_MAP:
        raise ValueError(f"Invalid timeframe '{key}' for {name}")
    return TIMEFRAME_MAP[key]


def _symbol_prefix(symbol):
    prefix = re.sub(r"[^A-Za-z0-9]", "", symbol).upper()
    if not prefix:
        raise ValueError(f"Invalid symbol format: {symbol}")
    return prefix


# ==============================
# TRADING CONFIG
# ==============================
SYMBOLS = _env_list("SYMBOLS")


def _build_symbol_config():
    config = {}

    for symbol in SYMBOLS:
        prefix = _symbol_prefix(symbol)
        config[symbol] = {
            "LOT": _env_float(f"{prefix}_LOT"),
            "MULTIPLIER": _env_float(f"{prefix}_MULTIPLIER"),
            "MAX_SPREAD": _env_float(f"{prefix}_MAX_SPREAD"),
            "SL_POINTS": _env_int(f"{prefix}_SL_POINTS"),
            "TP_POINTS": _env_int(f"{prefix}_TP_POINTS"),
            "TRAILING_START": _env_int(f"{prefix}_TRAILING_START"),
            "TRAILING_STEP": _env_int(f"{prefix}_TRAILING_STEP"),
        }

    return config


SYMBOL_CONFIG = _build_symbol_config()


def get_symbol_config(symbol):
    if symbol not in SYMBOL_CONFIG:
        raise ValueError(f"Symbol '{symbol}' belum ada di SYMBOL_CONFIG")
    return SYMBOL_CONFIG[symbol]


# Backward compatibility defaults.
SYMBOL = SYMBOLS[0]
_default = get_symbol_config(SYMBOL)

LOT = _default["LOT"]
MULTIPLIER = _default["MULTIPLIER"]
MAX_SPREAD = _default["MAX_SPREAD"]
SL_POINTS = _default["SL_POINTS"]
TP_POINTS = _default["TP_POINTS"]
TRAILING_START = _default["TRAILING_START"]
TRAILING_STEP = _default["TRAILING_STEP"]

MIN_ENTRY_DISTANCE = _env_float("MIN_ENTRY_DISTANCE")

MAGIC_NUMBER = _env_int("MAGIC_NUMBER")
SLIPPAGE = _env_int("SLIPPAGE")

TRADING_MODE = _env_str("TRADING_MODE").upper()
if TRADING_MODE not in {"AUTO", "MANUAL"}:
    raise ValueError("TRADING_MODE must be AUTO or MANUAL")

STRATEGY_MODE = os.getenv("STRATEGY_MODE", "AUTO").strip().upper()
if STRATEGY_MODE not in {"AUTO", "BREAKOUT", "REVERSAL", "SWITCH", "POINT", "SMART_POINT"}:
    raise ValueError(
        "STRATEGY_MODE must be AUTO, BREAKOUT, REVERSAL, SWITCH, POINT, or SMART_POINT"
    )

SWITCH_DISTANCE = _env_float("SWITCH_DISTANCE")
SWITCH_FOLLOW_MULTIPLIER = _env_float("SWITCH_FOLLOW_MULTIPLIER")
SWITCH_MAX_DISTANCE = _env_float("SWITCH_MAX_DISTANCE")
POINT_LOOKBACK = _env_int("POINT_LOOKBACK")
POINT_WICK_RATIO = _env_float("POINT_WICK_RATIO")
POINT_BODY_THRESHOLD = _env_float("POINT_BODY_THRESHOLD")
POINT_BODY_RATIO = POINT_BODY_THRESHOLD
POINT_MA_PERIOD = _env_int_default("POINT_MA_PERIOD", 20)
POINT_MIN_DISTANCE = _env_float_default("POINT_MIN_DISTANCE", 0.4)
POINT_MIN_VOLATILITY = _env_float_default("POINT_MIN_VOLATILITY", 1.0)
POINT_COOLDOWN = _env_int_default("POINT_COOLDOWN", 25)

COOLDOWN_SECONDS = _env_int("COOLDOWN_SECONDS")

# ==============================
# LOOP / SYSTEM TIMING
# ==============================
SLEEP_NO_TICK = _env_float("SLEEP_NO_TICK")
SLEEP_NO_SYMBOL = _env_float("SLEEP_NO_SYMBOL")
SLEEP_EMPTY_POSITIONS = _env_float("SLEEP_EMPTY_POSITIONS")
SLEEP_NEW_POSITION = _env_float("SLEEP_NEW_POSITION")
SLEEP_AFTER_POSITION_CYCLE = _env_float("SLEEP_AFTER_POSITION_CYCLE")
SLEEP_MANUAL_MODE = _env_float("SLEEP_MANUAL_MODE")
SLEEP_COOLDOWN = _env_float("SLEEP_COOLDOWN")
SLEEP_SPREAD_BLOCK = _env_float("SLEEP_SPREAD_BLOCK")
SLEEP_PENDING_BLOCK = _env_float("SLEEP_PENDING_BLOCK")
SLEEP_LOOP_END = _env_float("SLEEP_LOOP_END")

# ==============================
# FEATURE TOGGLES
# ==============================
ENABLE_DYNAMIC_SL = _env_bool("ENABLE_DYNAMIC_SL")
ENABLE_DYNAMIC_BE = _env_bool("ENABLE_DYNAMIC_BE")
ENABLE_BASIC_BE = _env_bool("ENABLE_BASIC_BE")

# ==============================
# ORDER / POSITION SAFETY
# ==============================
ORDER_VALIDATE_BUFFER_MULTIPLIER = _env_float("ORDER_VALIDATE_BUFFER_MULTIPLIER")
POSITION_SLTP_BUFFER_MULTIPLIER = _env_float("POSITION_SLTP_BUFFER_MULTIPLIER")
POSITION_CHANGE_TOLERANCE_POINT = _env_float("POSITION_CHANGE_TOLERANCE_POINT")

FAST_CUT_WINDOW_1_START = _env_int("FAST_CUT_WINDOW_1_START")
FAST_CUT_WINDOW_1_END = _env_int("FAST_CUT_WINDOW_1_END")
FAST_CUT_LEVEL_1_OFFSET = _env_float("FAST_CUT_LEVEL_1_OFFSET")

FAST_CUT_WINDOW_2_START = _env_int("FAST_CUT_WINDOW_2_START")
FAST_CUT_WINDOW_2_END = _env_int("FAST_CUT_WINDOW_2_END")
FAST_CUT_LEVEL_2_OFFSET = _env_float("FAST_CUT_LEVEL_2_OFFSET")

# ==============================
# BREAK EVEN
# ==============================
BE_TRIGGER = _env_float("BE_TRIGGER")
BE_OFFSET = _env_float("BE_OFFSET")
BE_MIN_PROFIT = _env_float("BE_MIN_PROFIT")
BE_BUFFER_MULTIPLIER = _env_float("BE_BUFFER_MULTIPLIER")

BE_STEP_1_START = _env_int("BE_STEP_1_START")
BE_STEP_1_END = _env_int("BE_STEP_1_END")
BE_STEP_1_LOCK = _env_float("BE_STEP_1_LOCK")

BE_STEP_2_START = _env_int("BE_STEP_2_START")
BE_STEP_2_END = _env_int("BE_STEP_2_END")
BE_STEP_2_LOCK = _env_float("BE_STEP_2_LOCK")

BE_STEP_3_START = _env_int("BE_STEP_3_START")
BE_STEP_3_END = _env_int("BE_STEP_3_END")
BE_STEP_3_LOCK = _env_float("BE_STEP_3_LOCK")

BE_STEP_4_START = _env_int("BE_STEP_4_START")
BE_STEP_4_END = _env_int("BE_STEP_4_END")
BE_STEP_4_LOCK = _env_float("BE_STEP_4_LOCK")

BASIC_BE_TRIGGER = _env_float("BASIC_BE_TRIGGER")
BASIC_BE_LOCK = _env_float("BASIC_BE_LOCK")

# ==============================
# TRAILING
# ==============================
TP_BASE_INTERVAL = _env_float("TP_BASE_INTERVAL")
TP_INTERVAL_FAST = _env_float("TP_INTERVAL_FAST")
TP_INTERVAL_FASTER = _env_float("TP_INTERVAL_FASTER")

TRAILING_BUFFER_MULTIPLIER = _env_float("TRAILING_BUFFER_MULTIPLIER")
TRAILING_DYNAMIC_STEP_SPREAD_MULTIPLIER = _env_float("TRAILING_DYNAMIC_STEP_SPREAD_MULTIPLIER")
TRAILING_TP_MULTIPLIER_BASE = _env_float("TRAILING_TP_MULTIPLIER_BASE")
TRAILING_TP_MULTIPLIER_BOOSTED = _env_float("TRAILING_TP_MULTIPLIER_BOOSTED")
TRAILING_TP_BOOST_TRIGGER_MULTIPLIER = _env_float("TRAILING_TP_BOOST_TRIGGER_MULTIPLIER")
TRAILING_TP_FAST_INTERVAL_TRIGGER_MULTIPLIER = _env_float(
    "TRAILING_TP_FAST_INTERVAL_TRIGGER_MULTIPLIER"
)
TRAILING_TP_FASTER_INTERVAL_TRIGGER_MULTIPLIER = _env_float(
    "TRAILING_TP_FASTER_INTERVAL_TRIGGER_MULTIPLIER"
)
TRAILING_VOLATILE_SPREAD_THRESHOLD = _env_float("TRAILING_VOLATILE_SPREAD_THRESHOLD")
TRAILING_VOLATILE_TP_WIDEN_MULTIPLIER = _env_float("TRAILING_VOLATILE_TP_WIDEN_MULTIPLIER")
TRAILING_TP_DISTANCE_SPREAD_MULTIPLIER = _env_float("TRAILING_TP_DISTANCE_SPREAD_MULTIPLIER")
TRAILING_CHANGE_TOLERANCE_POINT = _env_float("TRAILING_CHANGE_TOLERANCE_POINT")

# ==============================
# STRATEGY
# ==============================
MARKET_MODE_TIMEFRAME = _env_timeframe("MARKET_MODE_TIMEFRAME")
MARKET_MODE_LOOKBACK_BARS = _env_int("MARKET_MODE_LOOKBACK_BARS")
MARKET_MODE_SIDEWAYS_RANGE_MAX = _env_float("MARKET_MODE_SIDEWAYS_RANGE_MAX")
MARKET_MODE_SIDEWAYS_AVG_RANGE_MAX = _env_float("MARKET_MODE_SIDEWAYS_AVG_RANGE_MAX")
MARKET_MODE_VOLATILE_RANGE_MIN = _env_float("MARKET_MODE_VOLATILE_RANGE_MIN")

TREND_TIMEFRAME = _env_timeframe("TREND_TIMEFRAME")
TREND_FAST_PERIOD = _env_int("TREND_FAST_PERIOD")
TREND_SLOW_PERIOD = _env_int("TREND_SLOW_PERIOD")
TREND_EXTRA_BARS = _env_int("TREND_EXTRA_BARS")
TREND_SIDEWAYS_DIFF_THRESHOLD = _env_float("TREND_SIDEWAYS_DIFF_THRESHOLD")

FAKE_BREAKOUT_TIMEFRAME = _env_timeframe("FAKE_BREAKOUT_TIMEFRAME")
FAKE_BREAKOUT_LOOKBACK_BARS = _env_int("FAKE_BREAKOUT_LOOKBACK_BARS")
CANDLE_STRENGTH_THRESHOLD = _env_float("CANDLE_STRENGTH_THRESHOLD")
CANDLE_BODY_MIN = _env_float("CANDLE_BODY_MIN")
