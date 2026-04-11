import MetaTrader5 as mt5

from config.settings import BASIC_BE_LOCK, BASIC_BE_TRIGGER
from utils.logger import log
from utils.price_formatter import normalize_price


def apply_basic_be(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    digits = symbol_info.digits

    price_open = position.price_open
    sl = position.sl

    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open

        if profit < BASIC_BE_TRIGGER:
            return

        new_sl = price_open + BASIC_BE_LOCK

        if sl != 0.0 and sl >= new_sl:
            return

    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask

        if profit < BASIC_BE_TRIGGER:
            return

        new_sl = price_open - BASIC_BE_LOCK

        if sl != 0.0 and sl <= new_sl:
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

    mt5.order_send(request)

    log(f"BASIC BE | SL -> {new_sl:.3f}")
