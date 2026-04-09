import MetaTrader5 as mt5
from config.settings import *
from utils.logger import log
from utils.price_formatter import normalize_price


def get_positions(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return positions if positions else []


def has_position(symbol):
    return len(get_positions(symbol)) > 0


def get_position(symbol):
    positions = get_positions(symbol)
    return positions[0] if positions else None


def set_sl_tp(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    # ❗ JANGAN overwrite kalau sudah ada SL/TP
    if position.sl != 0.0 and position.tp != 0.0:
        return

    point = symbol_info.point
    stop_level = symbol_info.trade_stops_level * point

    price_open = position.price_open
    ticket = position.ticket

    sl = None
    tp = None

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        sl = price_open - (SL_POINTS * point)
        tp = price_open + (TP_POINTS * point)

        # validasi minimal jarak
        if (tick.bid - sl) < stop_level:
            sl = tick.bid - stop_level

        if (tp - tick.bid) < stop_level:
            tp = tick.bid + stop_level

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        sl = price_open + (SL_POINTS * point)
        tp = price_open - (TP_POINTS * point)

        if (sl - tick.ask) < stop_level:
            sl = tick.ask + stop_level

        if (tick.ask - tp) < stop_level:
            tp = tick.ask - stop_level

    else:
        return

    # ❗ SAFETY CHECK
    if sl is None or tp is None:
        return

    # ✅ NORMALIZE DI SINI (SETELAH HITUNG)
    sl = normalize_price(sl, symbol_info.digits)
    tp = normalize_price(tp, symbol_info.digits)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)
    log(f"🎯 Set SL/TP | SL: {sl:.3f} | TP: {tp:.3f} | Result: {result.retcode}")


def is_sl_tp_set(position):
    return position.sl != 0.0 and position.tp != 0.0


def close_opposite_pending(symbol, position_type):
    orders = mt5.orders_get(symbol=symbol)

    if not orders:
        return

    for order in orders:

        if order.symbol != symbol:
            continue
        # =========================
        # JIKA POSISI BUY
        # =========================
        if position_type == mt5.POSITION_TYPE_BUY:

            # hapus semua order SELL
            if order.type in [mt5.ORDER_TYPE_SELL_STOP, mt5.ORDER_TYPE_SELL_LIMIT]:
                result = mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )

                log(f"❌ Hapus SELL pending: {order.ticket} | Result: {result.retcode}")

        # =========================
        # JIKA POSISI SELL
        # =========================
        elif position_type == mt5.POSITION_TYPE_SELL:

            # hapus semua order BUY
            if order.type in [mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_BUY_LIMIT]:
                result = mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )

                log(f"❌ Hapus BUY pending: {order.ticket} | Result: {result.retcode}")
