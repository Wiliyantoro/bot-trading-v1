import MetaTrader5 as mt5
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

    # 🔥 ANTI INVALID (KODE KAMU - TETAP)
    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.2
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl

    # =========================
    # 🔥 SETTING BARU (PRICE BASED)
    # =========================
    BE_TRIGGER_PRICE = 0.5   # profit 0.5 langsung BE
    BE_LOCK_PRICE = 0.1      # lock profit 0.1

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open

        # belum cukup profit
        if profit < BE_TRIGGER_PRICE:
            return

        new_sl = price_open + BE_LOCK_PRICE

        # 🔥 tetap jaga min distance (kode kamu)
        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        # 🔥 jangan turunin SL
        if sl != 0.0 and sl >= new_sl:
            return

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask

        if profit < BE_TRIGGER_PRICE:
            return

        new_sl = price_open - BE_LOCK_PRICE

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if sl != 0.0 and sl <= new_sl:
            return

    else:
        return

    # =========================
    # NORMALIZE
    # =========================
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

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"❌ BE error | Retcode: {result.retcode}")