import MetaTrader5 as mt5
import time
from utils.logger import log
from utils.price_formatter import normalize_price
from config.settings import *


def apply_break_even(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    point = symbol_info.point
    digits = symbol_info.digits

    # 🔥 ANTI INVALID (TETAP)
    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.2
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl

    # ⏱️ umur posisi
    current_time = time.time()
    age = current_time - position.time

    # =========================
    # HITUNG PROFIT
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask
    else:
        return

    # =========================
    # 🔥 PRIORITAS: BE CEPAT (0.5)
    # =========================
    if profit >= 0.5:

        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open + 0.1
            if (tick.bid - new_sl) < min_distance:
                new_sl = tick.bid - min_distance

            if sl != 0.0 and sl >= new_sl:
                return

        else:
            new_sl = price_open - 0.1
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
            log(f"🟢 BE CEPAT | SL -> {new_sl:.3f}")

        return  # 🔥 stop di sini biar gak ke step BE

    # =========================
    # 🔥 BE BERTAHAP (TIME BASED)
    # =========================
    if profit < 0.1:
        return

    step_lock = None

    if 10 <= age <= 20:
        step_lock = 0.1
    elif 20 <= age <= 30:
        step_lock = 0.2
    elif 30 <= age <= 40:
        step_lock = 0.3
    elif 40 <= age <= 50:
        step_lock = 0.4
    else:
        return

    # =========================
    # APPLY STEP BE
    # =========================
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
        log(f"🟡 BE STEP | +{step_lock:.1f} | SL -> {new_sl:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"❌ BE error | Retcode: {result.retcode}")