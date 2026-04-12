import time
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


def is_manual_position(position):
    return position.magic != MAGIC_NUMBER


# =========================
# 🔥 CLOSE POSISI LAWAN (AGRESIF)
# =========================
def close_opposite_positions(symbol, position_type):
    positions = get_positions(symbol)

    if not positions:
        return

    for pos in positions:
        if pos.symbol != symbol:
            continue

        # BUY aktif → tutup SELL
        if position_type == mt5.POSITION_TYPE_BUY:
            if pos.type == mt5.POSITION_TYPE_SELL:
                close_position(pos)

        # SELL aktif → tutup BUY
        elif position_type == mt5.POSITION_TYPE_SELL:
            if pos.type == mt5.POSITION_TYPE_BUY:
                close_position(pos)


# =========================
# 🔥 CLOSE 1 POSISI
# =========================
def close_position(position):
    tick = mt5.symbol_info_tick(position.symbol)

    if tick is None:
        return

    price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": (
            mt5.ORDER_TYPE_SELL
            if position.type == mt5.POSITION_TYPE_BUY
            else mt5.ORDER_TYPE_BUY
        ),
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Close Opposite",
    }

    result = mt5.order_send(request)

    log(f"❌ Close Pos {position.ticket} | Retcode: {result.retcode}")


# =========================
# 🔥 FAST CUT LOSS (TIDAK DIUBAH)
# =========================
def apply_fast_cut_loss(position):
    # tetap pakai logic kamu (tidak diubah)
    pass


# =========================
# 🔥 SET SL TP (SAFE)
# =========================
def set_sl_tp(position, config=None):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

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

        if not is_manual:
            tp = price_open + (TP_POINTS * point)
        else:
            tp = 0.0

        if (tick.bid - sl) < min_distance:
            sl = tick.bid - min_distance

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

    if sl is None:
        return

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

    log(f"🎯 Set SL/TP | SL: {sl:.3f} | TP: {tp:.3f}")


# =========================
# 🔥 CEK SL TP
# =========================
def is_sl_tp_set(position):
    if is_manual_position(position):
        return position.sl != 0.0
    return position.sl != 0.0 and position.tp != 0.0


# =========================
# 🔥 HAPUS PENDING LAWAN
# =========================
def close_opposite_pending(symbol, position_type):
    orders = mt5.orders_get(symbol=symbol)

    if not orders:
        return

    for order in orders:
        if order.symbol != symbol:
            continue

        # BUY aktif → hapus SELL pending
        if position_type == mt5.POSITION_TYPE_BUY:
            if order.type in [
                mt5.ORDER_TYPE_SELL_STOP,
                mt5.ORDER_TYPE_SELL_LIMIT,
            ]:
                mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )
                log(f"❌ Hapus SELL pending: {order.ticket}")

        # SELL aktif → hapus BUY pending
        elif position_type == mt5.POSITION_TYPE_SELL:
            if order.type in [
                mt5.ORDER_TYPE_BUY_STOP,
                mt5.ORDER_TYPE_BUY_LIMIT,
            ]:
                mt5.order_send(
                    {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
                )
                log(f"❌ Hapus BUY pending: {order.ticket}")