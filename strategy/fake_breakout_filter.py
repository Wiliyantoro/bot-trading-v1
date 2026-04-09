import MetaTrader5 as mt5


def get_last_candle(symbol, timeframe=mt5.TIMEFRAME_M1):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 2)

    if rates is None or len(rates) < 2:
        return None

    return rates[-1]


def is_strong_bullish(candle):
    body = abs(candle["close"] - candle["open"])
    range_ = candle["high"] - candle["low"]

    if range_ == 0:
        return False

    strength = body / range_

    return candle["close"] > candle["open"] and strength > 0.6 and body > 0.2


def is_strong_bearish(candle):
    body = abs(candle["close"] - candle["open"])
    range_ = candle["high"] - candle["low"]

    if range_ == 0:
        return False

    strength = body / range_

    return candle["close"] < candle["open"] and strength > 0.6 and body > 0.2
