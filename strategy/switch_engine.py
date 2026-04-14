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
_last_stop_price = {}
_initial_stop_price = {}  # 🔥 SIMPAN SL AWAL
_initial_range = {}  # 🔥 SIMPAN JARAK AWAL

MIN_UPDATE_INTERVAL = 2
MIN_PRICE_STEP = 5


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

def get_atr(symbol, timeframe=mt5.TIMEFRAME_M5, period=14):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, period + 1)

    if rates is None or len(rates) < period:
        return 0

    trs = []
    for i in range(1, len(rates)):
        high = rates[i]['high']
        low = rates[i]['low']
        prev_close = rates[i-1]['close']

        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)

    return sum(trs) / len(trs)

def run_switch(symbol, positions, bid, ask, symbol_info, config, base_distance):
    if not positions:
        return

    point = symbol_info.point
    digits = symbol_info.digits

    # 🔥 GLOBAL CONTROL
    # =========================
    # ATR BASED DISTANCE 🔥
    # =========================
    atr = get_atr(symbol)

    # fallback kalau ATR gagal
    if atr == 0:
        atr = point * 150

    MULTIPLIER = 1.5

    MIN_LOCK_DISTANCE = atr * MULTIPLIER
    #MIN_LOCK_DISTANCE = point * 75   # ≈ 1.5$ (jarak minimum SL dari harga)
    TRAIL_STEP = point * 50           # step trailing biar halus

    # =========================
    # AMBIL POSISI AKTIF
    # =========================
    position = positions[0]

    # =========================
    # CLEAN MULTI POSISI
    # =========================
    if len(positions) > 1:
        log_symbol(symbol, "FORCE CLEAN → KEEP 1 POSITION")
        latest = max(positions, key=lambda p: p.time)
        close_opposite_positions(symbol, latest.type)

        # RESET
        _last_stop_price[symbol] = None
        _last_update_time[symbol] = 0
        _initial_stop_price[symbol] = None
        _initial_range[symbol] = None

        position = latest
        positions = [latest]

    # =========================
    # INITIAL SL (WAJIB ADA)
    # =========================
    if _last_stop_price.get(symbol) is None:
        if position.type == mt5.POSITION_TYPE_BUY:
            sl_price = normalize_price(bid - base_distance, digits)
            opposite_price = ask + base_distance
        else:
            sl_price = normalize_price(ask + base_distance, digits)
            opposite_price = bid - base_distance

        update_opposite_pending(symbol, sl_price, config)
        mark_updated(symbol, sl_price)
        _initial_stop_price[symbol] = sl_price

        # 🔥 SIMPAN RANGE AWAL
        _initial_range[symbol] = abs(opposite_price - sl_price)

        log_symbol(symbol, f"INIT SL PASANG → {sl_price:.3f}")
        return

    # =========================
    # HITUNG PROFIT
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
    else:
        profit = position.price_open - ask

    # =========================
    # FASE 1: BELUM PROFIT
    # =========================
    if profit <= 0:
        log_symbol(symbol, "NO PROFIT → HOLD SL")
        return

    # =========================
    # FASE 2: PROFIT KECIL (LOCK 0.1$)
    # =========================
    SMALL_PROFIT = point * 50   # ±0.5$
    LOCK_PROFIT = point * 10    # ±0.1$

    if profit < SMALL_PROFIT:
        log_symbol(symbol, f"SMALL PROFIT → LOCK ({profit/point:.1f})")

        if position.type == mt5.POSITION_TYPE_BUY:
            new_price = position.price_open + LOCK_PROFIT
        else:
            new_price = position.price_open - LOCK_PROFIT

        new_price = normalize_price(new_price, digits)

        last_price = _last_stop_price.get(symbol)

        # arah tidak boleh kebalik
        if position.type == mt5.POSITION_TYPE_BUY:
            if last_price is not None and new_price < last_price:
                return
        else:
            if last_price is not None and new_price > last_price:
                return

        if not should_update(symbol, new_price, point):
            return

        update_opposite_pending(symbol, new_price, config)
        mark_updated(symbol, new_price)

        return

    # =========================
    # FASE 3: PROFIT BESAR (PAKAI RANGE)
    # =========================
    range_distance = _initial_range.get(symbol, base_distance)

    if range_distance is None or range_distance <= 0:
        range_distance = base_distance

    if position.type == mt5.POSITION_TYPE_BUY:
        # SELL STOP → hanya boleh naik
        new_price = bid - range_distance

        last_price = _last_stop_price.get(symbol)
        if last_price is not None and new_price < last_price:
            return

        # 🔥 JAGA JARAK MINIMUM
        if (bid - new_price) < MIN_LOCK_DISTANCE:
            return

    else:
        # BUY STOP → hanya boleh turun
        new_price = ask + range_distance

        last_price = _last_stop_price.get(symbol)
        if last_price is not None and new_price > last_price:
            return

        # 🔥 JAGA JARAK MINIMUM
        if (new_price - ask) < MIN_LOCK_DISTANCE:
            return

    new_price = normalize_price(new_price, digits)

    # =========================
    # TRAILING STEP (BIAR HALUS)
    # =========================
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
    # UPDATE TRAILING
    # =========================
    update_opposite_pending(symbol, new_price, config)
    mark_updated(symbol, new_price)

    if position.type == mt5.POSITION_TYPE_BUY:
        log_symbol(symbol, f"SELL STOP ↑ {new_price:.3f}")
    else:
        log_symbol(symbol, f"BUY STOP ↓ {new_price:.3f}")