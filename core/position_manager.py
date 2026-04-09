import MetaTrader5 as mt5
import time
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
    return position.magic != MAGIC_NUMBER



def apply_fast_cut_loss(position):
    import time
    import MetaTrader5 as mt5

    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
        return

    digits = symbol_info.digits

    # =========================
    # ⏱️ UMUR POSISI
    # =========================
    current_time = time.time()
    age = current_time - position.time

    price_open = position.price_open
    sl = position.sl

    # =========================
    # HITUNG LOSS
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        loss = tick.bid - price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        loss = price_open - tick.ask
    else:
        return

    # hanya jika minus
    if loss >= 0:
        return

    # =========================
    # 🔥 STEP SL BERDASARKAN WAKTU
    # =========================
    new_sl = None

    # ⏱️ 5–10 detik → SL = -1.00
    if 5 <= age <= 10:
        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open - 1.00
        else:
            new_sl = price_open + 1.00

        log("⚡ FAST CUT LEVEL 1 (1.00)")

    # ⏱️ 20–30 detik → SL = -0.50
    elif 20 <= age <= 30:
        if position.type == mt5.POSITION_TYPE_BUY:
            new_sl = price_open - 0.50
        else:
            new_sl = price_open + 0.50

        log("⚡ FAST CUT LEVEL 2 (0.50)")

    else:
        return

    # =========================
    # 🔥 ANTI TURUN SL
    # =========================
    if sl != 0.0:
        if position.type == mt5.POSITION_TYPE_BUY and new_sl <= sl:
            return
        if position.type == mt5.POSITION_TYPE_SELL and new_sl >= sl:
            return

    # =========================
    # NORMALIZE
    # =========================
    new_sl = normalize_price(new_sl, digits)

    # =========================
    # EXECUTE
    # =========================
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": position.ticket,
        "sl": new_sl,
        "tp": position.tp,
    }

    result = mt5.order_send(request)

    log(f"⚡ TIME SL UPDATE | SL -> {new_sl:.3f} | Retcode: {result.retcode}")

# =========================
# SET SL / TP (FINAL FIXED)
# =========================
def set_sl_tp(position):
    symbol_info = mt5.symbol_info(position.symbol)
    tick = mt5.symbol_info_tick(position.symbol)

    if symbol_info is None or tick is None:
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

    # 🔥 ANTI TURUN SL
    if position.type == mt5.POSITION_TYPE_BUY and position.sl != 0.0:
        if sl <= position.sl:
            log("⛔ SL tidak boleh turun (BUY), skip")
            return

    if position.type == mt5.POSITION_TYPE_SELL and position.sl != 0.0:
        if sl >= position.sl:
            log("⛔ SL tidak boleh naik (SELL), skip")
            return

    # 🔥 ANTI SPAM
    current_sl = position.sl if position.sl else 0.0
    current_tp = position.tp if position.tp else 0.0

    if abs(current_sl - sl) < (point * 0.5):
        if tp == 0.0 or abs(current_tp - tp) < (point * 0.5):
            log("⚠️ SL/TP sama, skip update")
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
            log(f"🧠 Manual SL SET | SL: {sl:.3f}")
        else:
            log(f"🎯 Bot SL/TP SET | SL: {sl:.3f} | TP: {tp:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        log("⚠️ Tidak ada perubahan SL/TP")

    else:
        log(f"❌ Gagal set SL/TP | Retcode: {result.retcode}")


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
                result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": order.ticket
                })

                log(f"❌ Hapus SELL pending: {order.ticket} | Retcode: {result.retcode}")

        elif position_type == mt5.POSITION_TYPE_SELL:
            if order.type in [
                mt5.ORDER_TYPE_BUY_STOP,
                mt5.ORDER_TYPE_BUY_LIMIT,
            ]:
                result = mt5.order_send({
                    "action": mt5.TRADE_ACTION_REMOVE,
                    "order": order.ticket
                })

                log(f"❌ Hapus BUY pending: {order.ticket} | Retcode: {result.retcode}")