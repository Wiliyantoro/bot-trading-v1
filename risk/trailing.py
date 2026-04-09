import MetaTrader5 as mt5
from utils.logger import log
from utils.price_formatter import normalize_price
from config.settings import *


def apply_trailing(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    point = symbol_info.point
    digits = symbol_info.digits

    # 🔥 ANTI INVALID (WAJIB)
    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.2
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit_points = (tick.bid - price_open) / point

        # belum cukup profit
        if profit_points < TRAILING_START:
            return

        # 🔥 dynamic trailing (lebih smooth)
        dynamic_step = max(TRAILING_STEP, spread * 2)

        new_sl = tick.bid - (dynamic_step * point)

        # 🔥 jaga jarak aman dari harga
        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        # 🔥 jangan mundur
        if sl != 0.0 and new_sl <= sl:
            return

        # 🔥 jangan terlalu dekat ke open (hindari BE ke-trigger ulang)
        if new_sl <= price_open:
            return

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit_points = (price_open - tick.ask) / point

        if profit_points < TRAILING_START:
            return

        dynamic_step = max(TRAILING_STEP, spread * 2)

        new_sl = tick.ask + (dynamic_step * point)

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if sl != 0.0 and new_sl >= sl:
            return

        if new_sl >= price_open:
            return

    else:
        return

    new_sl = normalize_price(new_sl, digits)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": position.tp,
    }

    result = mt5.order_send(request)

    log(f"🔵 Trailing aktif | SL -> {new_sl:.3f} | Retcode: {result.retcode}")