import time

import MetaTrader5 as mt5

from config.settings import (
    BE_BUFFER_MULTIPLIER,
    BE_MIN_PROFIT,
    BE_OFFSET,
    BE_STEP_1_END,
    BE_STEP_1_LOCK,
    BE_STEP_1_START,
    BE_STEP_2_END,
    BE_STEP_2_LOCK,
    BE_STEP_2_START,
    BE_STEP_3_END,
    BE_STEP_3_LOCK,
    BE_STEP_3_START,
    BE_STEP_4_END,
    BE_STEP_4_LOCK,
    BE_STEP_4_START,
    BE_TRIGGER,
)
from utils.logger import log
from utils.price_formatter import normalize_price


def apply_break_even(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    point = symbol_info.point
    digits = symbol_info.digits

    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * BE_BUFFER_MULTIPLIER
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl

    current_time = time.time()
    age = current_time - position.time

    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask
    else:
        return

    if profit >= BE_TRIGGER:
        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open + BE_OFFSET
            if (tick.bid - new_sl) < min_distance:
                new_sl = tick.bid - min_distance

            if sl != 0.0 and sl >= new_sl:
                return

        else:
            new_sl = price_open - BE_OFFSET
            if (new_sl - tick.ask) < min_distance:
                new_sl = tick.ask + min_distance

            if sl != 0.0 and sl <= new_sl:
                return

        new_sl = normalize_price(new_sl, digits)

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
        }

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log(f"BE CEPAT | SL -> {new_sl:.3f}")

        return

    if profit < BE_MIN_PROFIT:
        return

    step_lock = None

    if BE_STEP_1_START <= age <= BE_STEP_1_END:
        step_lock = BE_STEP_1_LOCK
    elif BE_STEP_2_START <= age <= BE_STEP_2_END:
        step_lock = BE_STEP_2_LOCK
    elif BE_STEP_3_START <= age <= BE_STEP_3_END:
        step_lock = BE_STEP_3_LOCK
    elif BE_STEP_4_START <= age <= BE_STEP_4_END:
        step_lock = BE_STEP_4_LOCK
    else:
        return

    if position.type == mt5.POSITION_TYPE_BUY:
        new_sl = price_open + step_lock

        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        if sl != 0.0 and sl >= new_sl:
            return

    else:
        new_sl = price_open - step_lock

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if sl != 0.0 and sl <= new_sl:
            return

    new_sl = normalize_price(new_sl, digits)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": position.tp,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"BE STEP | +{step_lock:.1f} | SL -> {new_sl:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"BE error | Retcode: {result.retcode}")
