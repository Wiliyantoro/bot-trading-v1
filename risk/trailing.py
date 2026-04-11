import time

import MetaTrader5 as mt5

from config.settings import (
    TP_BASE_INTERVAL,
    TP_INTERVAL_FAST,
    TP_INTERVAL_FASTER,
    TRAILING_BUFFER_MULTIPLIER,
    TRAILING_CHANGE_TOLERANCE_POINT,
    TRAILING_DYNAMIC_STEP_SPREAD_MULTIPLIER,
    TRAILING_START,
    TRAILING_STEP,
    TRAILING_TP_BOOST_TRIGGER_MULTIPLIER,
    TRAILING_TP_DISTANCE_SPREAD_MULTIPLIER,
    TRAILING_TP_FAST_INTERVAL_TRIGGER_MULTIPLIER,
    TRAILING_TP_FASTER_INTERVAL_TRIGGER_MULTIPLIER,
    TRAILING_TP_MULTIPLIER_BASE,
    TRAILING_TP_MULTIPLIER_BOOSTED,
    TRAILING_VOLATILE_SPREAD_THRESHOLD,
    TRAILING_VOLATILE_TP_WIDEN_MULTIPLIER,
)
from utils.logger import log
from utils.price_formatter import normalize_price

# =========================
# GLOBAL TRACKER TP
# =========================
last_tp_update = {}


def apply_trailing(position, config=None):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    trailing_start = TRAILING_START
    trailing_step = TRAILING_STEP

    if config is not None:
        trailing_start = config.get("TRAILING_START", TRAILING_START)
        trailing_step = config.get("TRAILING_STEP", TRAILING_STEP)

    point = symbol_info.point
    digits = symbol_info.digits

    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * TRAILING_BUFFER_MULTIPLIER
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl
    tp = position.tp

    new_sl = None
    new_tp = tp

    current_time = time.time()
    ticket = position.ticket

    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
        profit_points = profit / point

        if profit_points < trailing_start:
            return

        dynamic_step = max(trailing_step, spread * TRAILING_DYNAMIC_STEP_SPREAD_MULTIPLIER)
        new_sl = tick.bid - (dynamic_step * point)

        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        if sl != 0.0 and new_sl <= sl:
            new_sl = sl

        if new_sl <= price_open:
            new_sl = sl if sl != 0.0 else new_sl

        if profit > 0:
            tp_multiplier = TRAILING_TP_MULTIPLIER_BASE

            if profit_points > trailing_start * TRAILING_TP_BOOST_TRIGGER_MULTIPLIER:
                tp_multiplier = TRAILING_TP_MULTIPLIER_BOOSTED

            if spread > TRAILING_VOLATILE_SPREAD_THRESHOLD:
                tp_multiplier *= TRAILING_VOLATILE_TP_WIDEN_MULTIPLIER

            tp_distance = max(
                profit * tp_multiplier,
                spread * TRAILING_TP_DISTANCE_SPREAD_MULTIPLIER,
            )
            new_tp = tick.bid + tp_distance

            if (new_tp - tick.bid) < min_distance:
                new_tp = tick.bid + min_distance

            if tp != 0.0 and new_tp <= tp:
                new_tp = tp

    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask
        profit_points = profit / point

        if profit_points < trailing_start:
            return

        dynamic_step = max(trailing_step, spread * TRAILING_DYNAMIC_STEP_SPREAD_MULTIPLIER)
        new_sl = tick.ask + (dynamic_step * point)

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if sl != 0.0 and new_sl >= sl:
            new_sl = sl

        if new_sl >= price_open:
            new_sl = sl if sl != 0.0 else new_sl

        if profit > 0:
            tp_multiplier = TRAILING_TP_MULTIPLIER_BASE

            if profit_points > trailing_start * TRAILING_TP_BOOST_TRIGGER_MULTIPLIER:
                tp_multiplier = TRAILING_TP_MULTIPLIER_BOOSTED

            if spread > TRAILING_VOLATILE_SPREAD_THRESHOLD:
                tp_multiplier *= TRAILING_VOLATILE_TP_WIDEN_MULTIPLIER

            tp_distance = max(
                profit * tp_multiplier,
                spread * TRAILING_TP_DISTANCE_SPREAD_MULTIPLIER,
            )
            new_tp = tick.ask - tp_distance

            if (tick.ask - new_tp) < min_distance:
                new_tp = tick.ask - min_distance

            if tp != 0.0 and new_tp >= tp:
                new_tp = tp

    else:
        return

    new_sl = normalize_price(new_sl, digits)

    if new_tp != 0.0:
        new_tp = normalize_price(new_tp, digits)

    last_time = last_tp_update.get(ticket, 0)

    tp_interval = TP_BASE_INTERVAL

    if profit_points > trailing_start * TRAILING_TP_FAST_INTERVAL_TRIGGER_MULTIPLIER:
        tp_interval = TP_INTERVAL_FAST

    if profit_points > trailing_start * TRAILING_TP_FASTER_INTERVAL_TRIGGER_MULTIPLIER:
        tp_interval = TP_INTERVAL_FASTER

    tolerance = point * TRAILING_CHANGE_TOLERANCE_POINT
    tp_changed = tp == 0.0 or abs(new_tp - tp) > tolerance

    if tp_changed:
        if current_time - last_time < tp_interval:
            new_tp = tp
        else:
            last_tp_update[ticket] = current_time

    sl_same = sl != 0.0 and abs(new_sl - sl) < tolerance
    tp_same = tp != 0.0 and abs(new_tp - tp) < tolerance

    if sl_same and tp_same:
        return

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": new_tp,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"Adaptive Trail | SL: {new_sl:.3f} | TP: {new_tp:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"Trailing error | Retcode: {result.retcode}")
