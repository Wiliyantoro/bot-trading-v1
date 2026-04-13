import MetaTrader5 as mt5

from config.settings import (
    FAST_CUT_LEVEL_1_OFFSET,
    FAST_CUT_LEVEL_2_OFFSET,
    FAST_CUT_WINDOW_1_END,
    FAST_CUT_WINDOW_1_START,
    FAST_CUT_WINDOW_2_END,
    FAST_CUT_WINDOW_2_START,
    MAGIC_NUMBER,
    POSITION_CHANGE_TOLERANCE_POINT,
    POSITION_SLTP_BUFFER_MULTIPLIER,
    SLIPPAGE,
    SL_POINTS,
    TP_POINTS,
)
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
    return position.magic != MAGIC_NUMBER


def apply_fast_cut_loss(position):
    import time

    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    digits = symbol_info.digits

    current_time = time.time()
    age = current_time - position.time

    price_open = position.price_open
    sl = position.sl

    if position.type == mt5.POSITION_TYPE_BUY:
        loss = tick.bid - price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        loss = price_open - tick.ask
    else:
        return

    if loss >= 0:
        return

    new_sl = None

    if FAST_CUT_WINDOW_1_START <= age <= FAST_CUT_WINDOW_1_END:
        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open - FAST_CUT_LEVEL_1_OFFSET
        else:
            new_sl = price_open + FAST_CUT_LEVEL_1_OFFSET

        log(f"FAST CUT LEVEL 1 ({FAST_CUT_LEVEL_1_OFFSET:.2f})")

    elif FAST_CUT_WINDOW_2_START <= age <= FAST_CUT_WINDOW_2_END:
        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open - FAST_CUT_LEVEL_2_OFFSET
        else:
            new_sl = price_open + FAST_CUT_LEVEL_2_OFFSET

        log(f"FAST CUT LEVEL 2 ({FAST_CUT_LEVEL_2_OFFSET:.2f})")

    else:
        return

    if sl != 0.0:
        if position.type == mt5.POSITION_TYPE_BUY and new_sl <= sl:
            return
        if position.type == mt5.POSITION_TYPE_SELL and new_sl >= sl:
            return

    new_sl = normalize_price(new_sl, digits)

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": position.tp,
    }

    result = mt5.order_send(request)

    log(f"TIME SL UPDATE | SL -> {new_sl:.3f} | Retcode: {result.retcode}")


# =========================
# SET SL / TP (FINAL FIXED)
# =========================
def set_sl_tp(position, config=None):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    point = symbol_info.point
    stop_level = symbol_info.trade_stops_level * point

    spread = tick.ask - tick.bid
    buffer = spread * POSITION_SLTP_BUFFER_MULTIPLIER
    min_distance = stop_level + buffer

    price_open = position.price_open
    ticket = position.ticket

    sl_points = SL_POINTS
    tp_points = TP_POINTS

    if config is not None:
        sl_points = config.get("SL_POINTS", SL_POINTS)
        tp_points = config.get("TP_POINTS", TP_POINTS)

    sl = None
    tp = None

    is_manual = is_manual_position(position)

    if position.type == mt5.POSITION_TYPE_BUY:
        sl = price_open - (sl_points * point)

        if not is_manual:
            tp = price_open + (tp_points * point)
        else:
            tp = 0.0

        if (tick.bid - sl) < min_distance:
            sl = tick.bid - min_distance

        if not is_manual:
            if (tp - tick.bid) < min_distance:
                tp = tick.bid + min_distance

    elif position.type == mt5.POSITION_TYPE_SELL:
        sl = price_open + (sl_points * point)

        if not is_manual:
            tp = price_open - (tp_points * point)
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

    if position.type == mt5.POSITION_TYPE_BUY and position.sl != 0.0:
        if sl <= position.sl:
            log("SL tidak boleh turun (BUY), skip")
            return

    if position.type == mt5.POSITION_TYPE_SELL and position.sl != 0.0:
        if sl >= position.sl:
            log("SL tidak boleh naik (SELL), skip")
            return

    current_sl = position.sl if position.sl else 0.0
    current_tp = position.tp if position.tp else 0.0

    tolerance = point * POSITION_CHANGE_TOLERANCE_POINT

    if abs(current_sl - sl) < tolerance:
        if tp == 0.0 or abs(current_tp - tp) < tolerance:
            log("SL/TP sama, skip update")
            return

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": sl,
        "tp": tp,
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        if is_manual:
            log(f"Manual SL SET | SL: {sl:.3f}")
        else:
            log(f"Bot SL/TP SET | SL: {sl:.3f} | TP: {tp:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        log("Tidak ada perubahan SL/TP")

    else:
        log(f"Gagal set SL/TP | Retcode: {result.retcode}")


# =========================
# CEK SUDAH ADA SL TP
# =========================
def is_sl_tp_set(position):
    if is_manual_position(position):
        return position.sl != 0.0
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

        if position_type == mt5.POSITION_TYPE_BUY:
            if order.type in [
                mt5.ORDER_TYPE_SELL_STOP,
                mt5.ORDER_TYPE_SELL_LIMIT,
            ]:
                result = mt5.order_send(
                    {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": order.ticket,
                    }
                )

                log(f"Hapus SELL pending: {order.ticket} | Retcode: {result.retcode}")

        elif position_type == mt5.POSITION_TYPE_SELL:
            if order.type in [
                mt5.ORDER_TYPE_BUY_STOP,
                mt5.ORDER_TYPE_BUY_LIMIT,
            ]:
                result = mt5.order_send(
                    {
                        "action": mt5.TRADE_ACTION_REMOVE,
                        "order": order.ticket,
                    }
                )

                log(f"Hapus BUY pending: {order.ticket} | Retcode: {result.retcode}")


def close_opposite_positions(symbol, active_position_type):
    positions = get_positions(symbol)
    if not positions:
        return

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return

    for position in positions:
        if position.symbol != symbol:
            continue

        if active_position_type == mt5.POSITION_TYPE_BUY:
            should_close = position.type == mt5.POSITION_TYPE_SELL
        elif active_position_type == mt5.POSITION_TYPE_SELL:
            should_close = position.type == mt5.POSITION_TYPE_BUY
        else:
            continue

        if not should_close:
            continue

        if position.type == mt5.POSITION_TYPE_BUY:
            close_type = mt5.ORDER_TYPE_SELL
            close_price = tick.bid
        else:
            close_type = mt5.ORDER_TYPE_BUY
            close_price = tick.ask

        symbol_info = mt5.symbol_info(symbol)

        filling_mode = symbol_info.filling_mode

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "position": position.ticket,
            "volume": position.volume,
            "type": close_type,
            "price": close_price,
            "deviation": SLIPPAGE,
            "magic": MAGIC_NUMBER,
            "comment": "Flip close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,  # 🔥 AUTO FIX
        }

        result = mt5.order_send(request)
        log(
            f"Close opposite position {position.ticket} | Type: {position.type} | Retcode: {result.retcode}"
        )
