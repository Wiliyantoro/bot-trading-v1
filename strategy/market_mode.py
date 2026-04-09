import MetaTrader5 as mt5


def get_market_mode(symbol):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 20)

    if rates is None or len(rates) < 20:
        return "UNKNOWN"

    highs = [r['high'] for r in rates]
    lows = [r['low'] for r in rates]

    highest = max(highs)
    lowest = min(lows)

    range_size = highest - lowest

    # 🔥 rata-rata ukuran candle
    ranges = [(r['high'] - r['low']) for r in rates]
    avg_range = sum(ranges) / len(ranges)

    # =========================
    # MODE DETECTION
    # =========================
    if range_size < 1.2 and avg_range < 0.3:
        return "SIDEWAYS"

    elif range_size > 2.0:
        return "VOLATILE"

    else:
        return "NORMAL"