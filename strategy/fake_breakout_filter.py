import MetaTrader5 as mt5

from config.settings import (
    CANDLE_BODY_MIN,
    CANDLE_STRENGTH_THRESHOLD,
    FAKE_BREAKOUT_LOOKBACK_BARS,
    FAKE_BREAKOUT_TIMEFRAME,
)


def get_last_candle(symbol, timeframe=FAKE_BREAKOUT_TIMEFRAME):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, FAKE_BREAKOUT_LOOKBACK_BARS)

    if rates is None or len(rates) < FAKE_BREAKOUT_LOOKBACK_BARS:
        return None

    return rates[-1]


def is_strong_bullish(candle):
    body = abs(candle["close"] - candle["open"])
    range_ = candle["high"] - candle["low"]

    if range_ == 0:
        return False

    strength = body / range_

    return (
        candle["close"] > candle["open"]
        and strength > CANDLE_STRENGTH_THRESHOLD
        and body > CANDLE_BODY_MIN
    )


def is_strong_bearish(candle):
    body = abs(candle["close"] - candle["open"])
    range_ = candle["high"] - candle["low"]

    if range_ == 0:
        return False

    strength = body / range_

    return (
        candle["close"] < candle["open"]
        and strength > CANDLE_STRENGTH_THRESHOLD
        and body > CANDLE_BODY_MIN
    )
