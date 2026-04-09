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

    # =========================
    # 🔥 ANTI INVALID
    # =========================
    stop_level = symbol_info.trade_stops_level * point
    spread = tick.ask - tick.bid
    buffer = spread * 1.2
    min_distance = stop_level + buffer

    price_open = position.price_open
    sl = position.sl

    new_sl = None

    # =========================
    # BUY
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = tick.bid - price_open
        profit_points = profit / point

        # =========================
        # 🔥 BELUM BE → pakai trailing lama
        # =========================
        if profit_points < TRAILING_START:
            return

        # =========================
        # 🔥 SUDAH BE → pakai trailing %
        # =========================
        if sl > price_open:
            trailing_distance = profit * 0.0002  # 0.02%
            new_sl = tick.bid - trailing_distance
        else:
            # fallback ke trailing lama
            dynamic_step = max(TRAILING_STEP, spread * 2)
            new_sl = tick.bid - (dynamic_step * point)

        # jaga jarak aman
        if (tick.bid - new_sl) < min_distance:
            new_sl = tick.bid - min_distance

        # jangan mundur
        if sl != 0.0 and new_sl <= sl:
            return

        # jangan dibawah open (hindari reset BE)
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

        if sl < price_open and sl != 0.0:
            trailing_distance = profit * 0.0002
            new_sl = tick.ask + trailing_distance
        else:
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

    # =========================
    # NORMALIZE
    # =========================
    new_sl = normalize_price(new_sl, digits)

    # =========================
    # 🔥 ANTI SPAM UPDATE
    # =========================
    if sl != 0.0 and abs(new_sl - sl) < (point * 0.5):
        return

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

    # =========================
    # LOG
    # =========================
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        log(f"🔵 Trailing aktif | SL -> {new_sl:.3f}")

    elif result.retcode == mt5.TRADE_RETCODE_NO_CHANGES:
        pass

    else:
        log(f"❌ Trailing error | Retcode: {result.retcode}")