import MetaTrader5 as mt5
from config.settings import *
from utils.logger import log
from utils.price_formatter import normalize_price


# =========================
# POSITION HELPERS
# =========================
def get_positions(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return positions if positions else []


def has_position(symbol):
    return len(get_positions(symbol)) > 0


def get_position(symbol):
    positions = get_positions(symbol)
    return positions[0] if positions else None


# =========================
# DETEKSI MANUAL TRADE
# =========================
def is_manual_position(position):
    # manual biasanya magic = 0 atau beda dari bot
    return position.magic != MAGIC_NUMBER


# =========================
# SET SL / TP (ANTI NOISE + HYBRID MODE)
# =========================
def set_sl_tp(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    # ❗ JANGAN overwrite kalau sudah ada
    if position.sl != 0.0 and position.tp != 0.0:
        return

    point = symbol_info.point
    stop_level = symbol_info.trade_stops_level * point

    spread = tick.ask - tick.bid
    buffer = spread * 1.5

    min_distance = stop_level + buffer

    price_open = position.price_open
    ticket = position.ticket

    sl = None
    tp = None

    is_manual = is_manual_position(position)

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        sl = price_open - (SL_POINTS * point)

        # 🔥 TP hanya untuk BOT
        if not is_manual:
            tp = price_open + (TP_POINTS * point)
        else:
            tp = 0.0

        # validasi SL
        if (tick.bid - sl) < min_distance:
            sl = tick.bid - min_distance

        # validasi TP hanya jika bot
        if not is_manual:
            if (tp - tick.bid) < min_distance:
                tp = tick.bid + min_distance

    # =========================
    # SELL
    # =========================
    elif position.type == mt5.POSITION_TYPE_SELL:
        sl = price_open + (SL_POINTS * point)

        if not is_manual:
            tp = price_open - (TP_POINTS * point)
        else:
            tp = 0.0

        if (sl - tick.ask) < min_distance:
            sl = tick.ask + min_distance

        if not is_manual:
            if (tick.ask - tp) < min_distance:
                tp = tick.ask - min_distance

    else:
        return

    # ❗ SAFETY CHECK
    if sl is None:
        return

    # normalize
    sl = normalize_price(sl, symbol_info.digits)

    if tp != 0.0:
        tp = normalize_price(tp, symbol_info.digits)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)

    if is_manual:
        log(f"🧠 Manual SL SET | SL: {sl:.3f} | Retcode: {result.retcode}")
    else:
        log(f"🎯 Bot SL/TP SET | SL: {sl:.3f} | TP: {tp:.3f} | Retcode: {result.retcode}")


# =========================
# CEK SUDAH ADA SL TP
# =========================
def is_sl_tp_set(position):
    return position.sl != 0.0 and position.tp != 0.0


# =========================
# HAPUS PENDING LAWAN
# =========================
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

            if order.type in [
                mt5.ORDER_TYPE_SELL_STOP,
                mt5.ORDER_TYPE_SELL_LIMIT,
            ]:
                result = mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )

                log(f"❌ Hapus SELL pending: {order.ticket} | Retcode: {result.retcode}")

        # =========================
        # JIKA POSISI SELL
        # =========================
        elif position_type == mt5.POSITION_TYPE_SELL:

            if order.type in [
                mt5.ORDER_TYPE_BUY_STOP,
                mt5.ORDER_TYPE_BUY_LIMIT,
            ]:
                result = mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )

                log(f"❌ Hapus BUY pending: {order.ticket} | Retcode: {result.retcode}")