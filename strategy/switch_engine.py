import time
import MetaTrader5 as mt5

from core.order_manager import update_opposite_pending
from core.position_manager import close_opposite_pending, close_opposite_positions
from utils.price_formatter import normalize_price
from utils.logger import log

# =========================
# CACHE STATE
# =========================
_last_update_time = {}
_last_stop_price = {}   # 🔥 LOCK PRICE
_last_direction = {}    # BUY / SELL

MIN_UPDATE_INTERVAL = 2
MIN_PRICE_STEP = 5

MIN_PROFIT_TO_ACTIVATE = 50  # bisa kamu setting

def log_symbol(symbol, msg):
    log(f"[SWITCH-LOCK][{symbol}] {msg}")


def should_update(symbol, new_price, point):
    last_time = _last_update_time.get(symbol, 0)

    if time.time() - last_time < MIN_UPDATE_INTERVAL:
        return False

    last_price = _last_stop_price.get(symbol)
    if last_price is not None:
        if abs(new_price - last_price) < (point * MIN_PRICE_STEP):
            return False

    return True


def mark_updated(symbol, price):
    _last_update_time[symbol] = time.time()
    _last_stop_price[symbol] = price

def run_switch(symbol, positions, bid, ask, symbol_info, config, base_distance):
    if not positions:
        return

    position = max(positions, key=lambda pos: pos.time)

    point = symbol_info.point
    digits = symbol_info.digits

    # =========================
    # HITUNG PROFIT
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
        direction = "BUY"
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = position.price_open - ask
        direction = "SELL"
    else:
        return

    # 🔥 AKTIFKAN HANYA SAAT PROFIT
    if profit < (point * MIN_PROFIT_TO_ACTIVATE):
        return

    # =========================
    # HANDLE DIRECTION CHANGE (RESET LOCK)
    # =========================
    last_dir = _last_direction.get(symbol)
    if last_dir != direction:
        _last_stop_price[symbol] = None  # reset lock
        _last_direction[symbol] = direction

    # =========================
    # CLOSE LAWAN
    # =========================
    close_opposite_positions(symbol, position.type)
    close_opposite_pending(symbol, position.type)

    # =========================
    # HITUNG STOP BARU
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        # SELL STOP (naik saja)
        new_price = bid - base_distance

        last_price = _last_stop_price.get(symbol)

        if last_price is not None:
            # ❌ tidak boleh turun
            if new_price < last_price:
                return

    else:
        # BUY STOP (turun saja)
        new_price = ask + base_distance

        last_price = _last_stop_price.get(symbol)

        if last_price is not None:
            # ❌ tidak boleh naik
            if new_price > last_price:
                return

    new_price = normalize_price(new_price, digits)

    # =========================
    # ANTI SPAM
    # =========================
    if not should_update(symbol, new_price, point):
        return

    # =========================
    # UPDATE PENDING
    # =========================
    update_opposite_pending(symbol, new_price, config)

    mark_updated(symbol, new_price)

    if position.type == mt5.POSITION_TYPE_BUY:
        log_symbol(symbol, f"LOCK SELL STOP ↑ {new_price:.3f}")
    else:
        log_symbol(symbol, f"LOCK BUY STOP ↓ {new_price:.3f}")