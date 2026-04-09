import MetaTrader5 as mt5
from utils.logger import log


def get_trend(symbol, timeframe=mt5.TIMEFRAME_M1, fast=10, slow=30):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, slow + 10)

    if rates is None or len(rates) < slow:
        return "UNKNOWN"

    closes = [r["close"] for r in rates]

    fast_ma = sum(closes[-fast:]) / fast
    slow_ma = sum(closes[-slow:]) / slow
    log(f"📈 Fast MA: {fast_ma:.3f} | Slow MA: {slow_ma:.3f}")
    diff = abs(fast_ma - slow_ma)
    log(f"📊 Diff MA: {diff:.3f}")

    # threshold kecil → sideways
    if diff < 0.2:
        return "SIDEWAYS"

    elif fast_ma > slow_ma:
        return "UPTREND"

    elif fast_ma < slow_ma:
        return "DOWNTREND"

    return "UNKNOWN"
