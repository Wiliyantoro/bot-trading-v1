import MetaTrader5 as mt5

from config.settings import (
    TREND_EXTRA_BARS,
    TREND_FAST_PERIOD,
    TREND_SIDEWAYS_DIFF_THRESHOLD,
    TREND_SLOW_PERIOD,
    TREND_TIMEFRAME,
)
from utils.logger import log


def get_trend(
    symbol,
    timeframe=TREND_TIMEFRAME,
    fast=TREND_FAST_PERIOD,
    slow=TREND_SLOW_PERIOD,
):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, slow + TREND_EXTRA_BARS)

    if rates is None or len(rates) < slow:
        return "UNKNOWN"

    closes = [r["close"] for r in rates]

    fast_ma = sum(closes[-fast:]) / fast
    slow_ma = sum(closes[-slow:]) / slow
    log(f"Fast MA: {fast_ma:.3f} | Slow MA: {slow_ma:.3f}")
    diff = abs(fast_ma - slow_ma)
    log(f"Diff MA: {diff:.3f}")

    if diff < TREND_SIDEWAYS_DIFF_THRESHOLD:
        return "SIDEWAYS"

    elif fast_ma > slow_ma:
        return "UPTREND"

    elif fast_ma < slow_ma:
        return "DOWNTREND"

    return "UNKNOWN"
