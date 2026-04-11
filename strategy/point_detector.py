import time

import MetaTrader5 as mt5

from config.settings import (
    POINT_BODY_RATIO,
    POINT_COOLDOWN,
    POINT_LOOKBACK,
    POINT_MA_PERIOD,
    POINT_MIN_DISTANCE,
    POINT_MIN_VOLATILITY,
    POINT_WICK_RATIO,
)

_last_signal_timestamp = {}


def _safe_div(numerator, denominator):
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def detect_buy_sell_point(symbol):
    required_bars = max(POINT_LOOKBACK, POINT_MA_PERIOD, 5)
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, required_bars)

    if rates is None or len(rates) < required_bars:
        return {"buy": False, "sell": False}

    lookback_rates = rates[-POINT_LOOKBACK:]
    ma_rates = rates[-POINT_MA_PERIOD:]
    recent_rates = rates[-5:]
    last = rates[-1]

    highest = max(candle["high"] for candle in lookback_rates)
    lowest = min(candle["low"] for candle in lookback_rates)

    open_ = last["open"]
    close = last["close"]
    high = last["high"]
    low = last["low"]

    body = abs(close - open_)
    candle_range = high - low

    if candle_range <= 0:
        return {"buy": False, "sell": False}

    # Body kecil: body < candle_range * POINT_BODY_RATIO
    small_body = body < (candle_range * POINT_BODY_RATIO)

    bearish = close < open_
    bullish = close > open_

    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low

    # Wick validation: wick > body * POINT_WICK_RATIO
    has_valid_upper_wick = upper_wick > (body * POINT_WICK_RATIO)
    has_valid_lower_wick = lower_wick > (body * POINT_WICK_RATIO)

    # Moving Average filter + overextension from MA.
    moving_average = sum(candle["close"] for candle in ma_rates) / float(len(ma_rates))
    sell_above_ma = close > moving_average
    buy_below_ma = close < moving_average

    sell_distance = high - moving_average
    buy_distance = moving_average - low
    sell_overextended = sell_distance > POINT_MIN_DISTANCE
    buy_overextended = buy_distance > POINT_MIN_DISTANCE

    # Volatility filter: range 5 candle terakhir > POINT_MIN_VOLATILITY
    recent_high = max(candle["high"] for candle in recent_rates)
    recent_low = min(candle["low"] for candle in recent_rates)
    recent_range = recent_high - recent_low
    volatility_ok = recent_range > POINT_MIN_VOLATILITY

    sell_point = (
        (high >= highest)
        and (bearish or small_body)
        and has_valid_upper_wick
        and sell_above_ma
        and sell_overextended
        and volatility_ok
    )
    buy_point = (
        (low <= lowest)
        and (bullish or small_body)
        and has_valid_lower_wick
        and buy_below_ma
        and buy_overextended
        and volatility_ok
    )

    # Improve signal accuracy by preventing conflicting dual signals.
    if buy_point and sell_point:
        sell_strength = _safe_div(upper_wick, max(body, candle_range * 0.001)) + _safe_div(
            sell_distance, POINT_MIN_DISTANCE
        )
        buy_strength = _safe_div(lower_wick, max(body, candle_range * 0.001)) + _safe_div(
            buy_distance, POINT_MIN_DISTANCE
        )

        if sell_strength > buy_strength:
            buy_point = False
        elif buy_strength > sell_strength:
            sell_point = False
        else:
            buy_point = False
            sell_point = False

    # Cooldown signal: block repeated signals in POINT_COOLDOWN window per symbol.
    if buy_point or sell_point:
        now = time.time()
        last_signal_time = _last_signal_timestamp.get(symbol, 0.0)
        if now - last_signal_time < POINT_COOLDOWN:
            return {"buy": False, "sell": False}
        _last_signal_timestamp[symbol] = now

    return {"buy": buy_point, "sell": sell_point}
