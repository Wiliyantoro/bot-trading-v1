import MetaTrader5 as mt5

from config.settings import (
    MARKET_MODE_LOOKBACK_BARS,
    MARKET_MODE_SIDEWAYS_AVG_RANGE_MAX,
    MARKET_MODE_SIDEWAYS_RANGE_MAX,
    MARKET_MODE_TIMEFRAME,
    MARKET_MODE_VOLATILE_RANGE_MIN,
)


def get_market_mode(symbol):
    rates = mt5.copy_rates_from_pos(symbol, MARKET_MODE_TIMEFRAME, 0, MARKET_MODE_LOOKBACK_BARS)

    if rates is None or len(rates) < MARKET_MODE_LOOKBACK_BARS:
        return "UNKNOWN"

    highs = [r["high"] for r in rates]
    lows = [r["low"] for r in rates]

    highest = max(highs)
    lowest = min(lows)

    range_size = highest - lowest

    ranges = [(r["high"] - r["low"]) for r in rates]
    avg_range = sum(ranges) / len(ranges)

    if range_size < MARKET_MODE_SIDEWAYS_RANGE_MAX and avg_range < MARKET_MODE_SIDEWAYS_AVG_RANGE_MAX:
        return "SIDEWAYS"

    elif range_size > MARKET_MODE_VOLATILE_RANGE_MIN:
        return "VOLATILE"

    else:
        return "NORMAL"
