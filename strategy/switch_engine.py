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
LOCK_TOLERANCE_MULTIPLIER = 15  # 🔥 kunci fleksibel


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

    point = symbol_info.point
    digits = symbol_info.digits

    # =========================
    # AMBIL POSISI AKTIF (HANYA 1)
    # =========================
    position = positions[0]

    # =========================
    # CLEAN JIKA ADA LEBIH DARI 1 POSISI
    # =========================
    if len(positions) > 1:
        log_symbol(symbol, "FORCE CLEAN → KEEP 1 POSITION")
        latest = max(positions, key=lambda p: p.time)
        close_opposite_positions(symbol, latest.type)
        return

    # =========================
    # DETEKSI SWITCH (KENA PENDING)
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]
        if sell_positions:
            log_symbol(symbol, "SWITCH → CLOSE BUY")
            close_opposite_positions(symbol, mt5.POSITION_TYPE_SELL)

            # 🔥 PASANG SL BARU (SELL STOP)
            sl_price = normalize_price(bid - base_distance, digits)
            if not should_update(symbol, sl_price, point):
                return
            update_opposite_pending(symbol, sl_price, config)
            mark_updated(symbol, sl_price)

            log_symbol(symbol, f"INIT SELL STOP (SL) ↓ {sl_price:.3f}")
            return

    elif position.type == mt5.POSITION_TYPE_SELL:
        buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]
        if buy_positions:
            log_symbol(symbol, "SWITCH → CLOSE SELL")
            close_opposite_positions(symbol, mt5.POSITION_TYPE_BUY)

            # 🔥 PASANG SL BARU (BUY STOP)
            sl_price = normalize_price(ask + base_distance, digits)
            if not should_update(symbol, sl_price, point):
                return
            update_opposite_pending(symbol, sl_price, config)
            mark_updated(symbol, sl_price)

            log_symbol(symbol, f"INIT BUY STOP (SL) ↑ {sl_price:.3f}")
            return

    # =========================
    # INITIAL SL (WAJIB ADA) 🔥
    # =========================
    last_price = _last_stop_price.get(symbol)

    if last_price is None:
        # belum pernah pasang SL → WAJIB pasang
        if position.type == mt5.POSITION_TYPE_BUY:
            sl_price = normalize_price(bid - base_distance, digits)
        else:
            sl_price = normalize_price(ask + base_distance, digits)

        update_opposite_pending(symbol, sl_price, config)
        mark_updated(symbol, sl_price)

        log_symbol(symbol, f"INIT SL PASANG → {sl_price:.3f}")
        return
    # =========================
    # PROFIT ACTIVATION (ANTI NOISE) 🔥
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
    else:
        profit = position.price_open - ask

    MIN_PROFIT_ACTIVATE = point * 100  # ≈ $1 (XAU)

    if profit < MIN_PROFIT_ACTIVATE:
        log_symbol(symbol, "WAIT PROFIT → NO TRAILING")
        return

    # =========================
    # TRAILING PENDING (STRICT)
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        # SELL STOP (naik saja)
        new_price = bid - base_distance

        last_price = _last_stop_price.get(symbol)

        if last_price is not None:
            # ❌ tidak boleh turun
            if new_price < last_price:
                return

        # ❌ jangan terlalu dekat harga (biar profit maksimal)
        MIN_LOCK_DISTANCE = point * 150
        if (bid - new_price) < MIN_LOCK_DISTANCE:
            return

    else:
        # BUY STOP (turun saja)
        new_price = ask + base_distance

        last_price = _last_stop_price.get(symbol)

        if last_price is not None:
            # ❌ tidak boleh naik
            if new_price > last_price:
                return

        # ❌ jangan terlalu dekat harga
        MIN_LOCK_DISTANCE = point * 150
        if (new_price - ask) < MIN_LOCK_DISTANCE:
            return

    new_price = normalize_price(new_price, digits)

    # =========================
    # TRAILING STEP (BIAR HALUS)
    # =========================
    TRAIL_STEP = point * 50
    last_price = _last_stop_price.get(symbol)

    if last_price is not None:
        if abs(new_price - last_price) < TRAIL_STEP:
            return

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
        log_symbol(symbol, f"SELL STOP ↑ {new_price:.3f}")
    else:
        log_symbol(symbol, f"BUY STOP ↓ {new_price:.3f}")