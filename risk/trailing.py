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

    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.5  # 🔥 diperbesar biar aman
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl
    tp = position.tp

    new_sl = None
    new_tp = None

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
        profit_points = profit / point

        if profit_points < TRAILING_START:
            return

        # 🔥 SL lebih dekat (lock cepat)
        trailing_distance = profit * 0.0002  # 0.02%
        new_sl = tick.bid - trailing_distance

        # 🔥 TP lebih jauh (anti spike)
        tp_distance = profit * 0.0008  # 0.08% (NAIKKAN)
        new_tp = tick.bid + tp_distance

        # safety
        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        if (new_tp - tick.bid) < min_distance:
            new_tp = tick.bid + min_distance

        # anti turun SL
        if sl != 0.0 and new_sl <= sl:
            return

        if new_sl <= price_open:
            return

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = price_open - tick.ask
        profit_points = profit / point

        if profit_points < TRAILING_START:
            return

        trailing_distance = profit * 0.0002
        new_sl = tick.ask + trailing_distance

        tp_distance = profit * 0.0008  # 🔥 lebih lebar
        new_tp = tick.ask - tp_distance

        if (new_sl - tick.ask) < min_distance:
            new_sl = tick.ask + min_distance

        if (tick.ask - new_tp) < min_distance:
            new_tp = tick.ask - min_distance

        if sl != 0.0 and new_sl >= sl:
            return

        if new_sl >= price_open:
            return

    else:
        return

    new_sl = normalize_price(new_sl, digits)
    new_tp = normalize_price(new_tp, digits)

    # =========================
    # ANTI SPAM
    # =========================
    if sl != 0.0 and abs(new_sl - sl) < (point * 0.5):
        if tp != 0.0 and abs(new_tp - tp) < (point * 0.5):
            return

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": new_tp,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"🚀 Trail+TP Wide | SL: {new_sl:.3f} | TP: {new_tp:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"❌ Trailing error | Retcode: {result.retcode}")