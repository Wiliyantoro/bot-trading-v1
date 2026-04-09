import MetaTrader5 as mt5
import time
from utils.logger import log
from utils.price_formatter import normalize_price
from config.settings import *

# =========================
# 🔥 GLOBAL TRACKER TP
# =========================
last_tp_update = {}
TP_BASE_INTERVAL = 1.0  # default


def apply_trailing(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    point = symbol_info.point
    digits = symbol_info.digits

    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.2
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl
    tp = position.tp

    new_sl = None
    new_tp = tp

    current_time = time.time()
    ticket = position.ticket

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
        profit_points = profit / point

        if profit_points < TRAILING_START:
            return

        # =========================
        # 🔥 TRAILING SL (ASLI)
        # =========================
        dynamic_step = max(TRAILING_STEP, spread * 2)
        new_sl = tick.bid - (dynamic_step * point)

        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        if sl != 0.0 and new_sl <= sl:
            new_sl = sl

        if new_sl <= price_open:
            new_sl = sl if sl != 0.0 else new_sl

        # =========================
        # 🔥 TP ADAPTIVE
        # =========================
        if profit > 0:

            # 🔥 semakin besar profit → TP makin jauh
            tp_multiplier = 0.0015

            if profit_points > TRAILING_START * 2:
                tp_multiplier = 0.0025  # profit besar → TP lebih jauh

            if spread > 0.4:
                tp_multiplier *= 1.5  # volatile → TP diperlebar

            tp_distance = max(profit * tp_multiplier, spread * 5)
            new_tp = tick.bid + tp_distance

            if (new_tp - tick.bid) < min_distance:
                new_tp = tick.bid + min_distance

            # TP tidak turun
            if tp != 0.0 and new_tp <= tp:
                new_tp = tp

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask
        profit_points = profit / point

        if profit_points < TRAILING_START:
            return

        dynamic_step = max(TRAILING_STEP, spread * 2)
        new_sl = tick.ask + (dynamic_step * point)

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if sl != 0.0 and new_sl >= sl:
            new_sl = sl

        if new_sl >= price_open:
            new_sl = sl if sl != 0.0 else new_sl

        # =========================
        # 🔥 TP ADAPTIVE
        # =========================
        if profit > 0:

            tp_multiplier = 0.0015

            if profit_points > TRAILING_START * 2:
                tp_multiplier = 0.0025

            if spread > 0.4:
                tp_multiplier *= 1.5

            tp_distance = max(profit * tp_multiplier, spread * 5)
            new_tp = tick.ask - tp_distance

            if (tick.ask - new_tp) < min_distance:
                new_tp = tick.ask - min_distance

            if tp != 0.0 and new_tp >= tp:
                new_tp = tp

    else:
        return

    # =========================
    # NORMALIZE
    # =========================
    new_sl = normalize_price(new_sl, digits)

    if new_tp != 0.0:
        new_tp = normalize_price(new_tp, digits)

    # =========================
    # 🔥 TP COOLDOWN ADAPTIVE
    # =========================
    last_time = last_tp_update.get(ticket, 0)

    # 🔥 semakin profit besar → update lebih cepat
    tp_interval = TP_BASE_INTERVAL

    if profit_points > TRAILING_START * 2:
        tp_interval = 0.5

    if profit_points > TRAILING_START * 3:
        tp_interval = 0.2

    tp_changed = (tp == 0.0 or abs(new_tp - tp) > (point * 0.5))

    if tp_changed:
        if current_time - last_time < tp_interval:
            new_tp = tp
        else:
            last_tp_update[ticket] = current_time

    # =========================
    # 🔥 ANTI SPAM FINAL
    # =========================
    sl_same = (sl != 0.0 and abs(new_sl - sl) < (point * 0.5))
    tp_same = (tp != 0.0 and abs(new_tp - tp) < (point * 0.5))

    if sl_same and tp_same:
        return

    # =========================
    # EXECUTE
    # =========================
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": new_tp,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"🚀 Adaptive Trail | SL: {new_sl:.3f} | TP: {new_tp:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"❌ Trailing error | Retcode: {result.retcode}")