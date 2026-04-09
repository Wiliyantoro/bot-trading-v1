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

    price_open = position.price_open
    sl = position.sl

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit_points = (tick.bid - price_open) / point

        if profit_points < BE_TRIGGER:
            return

        new_sl = price_open + (BE_OFFSET * point)

        # jangan turunin SL
        if sl >= new_sl:
            return

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit_points = (price_open - tick.ask) / point

        if profit_points < BE_TRIGGER:
            return

        new_sl = price_open - (BE_OFFSET * point)

        if sl <= new_sl and sl != 0.0:
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
    log(f"🟢 BE aktif | SL -> {new_sl:.3f} | Result: {result.retcode}")
