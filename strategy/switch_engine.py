import time
import MetaTrader5 as mt5

from core.order_manager import update_opposite_pending
from core.position_manager import close_opposite_pending, close_opposite_positions
from utils.price_formatter import normalize_price
from utils.logger import log

# =========================
# CACHE (ANTI SPAM MODIFY)
# =========================
_last_update_price = {}
_last_update_time = {}

MIN_UPDATE_INTERVAL = 2  # detik
MIN_PRICE_STEP = 5  # points (sesuaikan nanti)


def log_symbol(symbol, msg):
    log(f"[SWITCH][{symbol}] {msg}")


def should_update(symbol, new_price, point):
    last_price = _last_update_price.get(symbol)
    last_time = _last_update_time.get(symbol, 0)

    now = time.time()

    # ⛔ jangan terlalu sering
    if now - last_time < MIN_UPDATE_INTERVAL:
        return False

    # ⛔ perubahan terlalu kecil
    if last_price is not None:
        if abs(new_price - last_price) < (point * MIN_PRICE_STEP):
            return False

    return True


def mark_updated(symbol, price):
    _last_update_price[symbol] = price
    _last_update_time[symbol] = time.time()


def calculate_follow_price(position, bid, ask, point, base_distance):
    """
    🔥 CORE LOGIC
    Harga stop mengikuti harga sekarang (bukan dari entry lagi)
    """

    if position.type == mt5.POSITION_TYPE_BUY:
        # follow sell stop
        return bid - base_distance

    elif position.type == mt5.POSITION_TYPE_SELL:
        # follow buy stop
        return ask + base_distance

    return None


def run_switch(symbol, positions, bid, ask, symbol_info, config, base_distance):
    if not positions:
        return

    # ambil posisi terakhir (paling baru)
    position = max(positions, key=lambda pos: pos.time)

    point = symbol_info.point
    digits = symbol_info.digits

    # 🔁 pastikan hanya 1 arah
    close_opposite_positions(symbol, position.type)

    # 🧹 hapus pending lawan
    close_opposite_pending(symbol, position.type)

    # 🎯 hitung harga follow
    new_price = calculate_follow_price(position, bid, ask, point, base_distance)

    if new_price is None:
        return

    new_price = normalize_price(new_price, digits)

    # ⛔ filter spam modify
    if not should_update(symbol, new_price, point):
        return

    # 🚀 update pending
    update_opposite_pending(symbol, new_price, config)

    mark_updated(symbol, new_price)

    if position.type == mt5.POSITION_TYPE_BUY:
        log_symbol(symbol, f"FOLLOW SELL STOP → {new_price:.3f}")
    else:
        log_symbol(symbol, f"FOLLOW BUY STOP → {new_price:.3f}")
