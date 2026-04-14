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


def run_switch(symbol, positions, bid, ask, symbol_info, config, base_distance):
    if not positions:
        return

    point = symbol_info.point
    digits = symbol_info.digits

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

        position = latest
        positions = [latest]

    # =========================
    # DETEKSI SWITCH
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        sell_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_SELL]

        if sell_positions:
            buy_profit = bid - position.price_open
            sell_profit = sum(p.price_open - ask for p in sell_positions)

            # 🔥 PILIH YANG LEBIH PROFIT
            if sell_profit > buy_profit:
                log_symbol(symbol, "KEEP SELL → CLOSE BUY (FAKE SWITCH)")
                close_opposite_positions(symbol, mt5.POSITION_TYPE_SELL)
                return

            else:
                log_symbol(symbol, "VALID SWITCH → CLOSE SELL")
                close_opposite_positions(symbol, mt5.POSITION_TYPE_BUY)

                _last_stop_price[symbol] = None
                _last_update_time[symbol] = 0
                _initial_stop_price[symbol] = None

                sl_price = normalize_price(bid - base_distance, digits)
                update_opposite_pending(symbol, sl_price, config)
                mark_updated(symbol, sl_price)
                _initial_stop_price[symbol] = sl_price

                return

    elif position.type == mt5.POSITION_TYPE_SELL:
        buy_positions = [p for p in positions if p.type == mt5.POSITION_TYPE_BUY]

        if buy_positions:
            sell_profit = position.price_open - ask
            buy_profit = sum(bid - p.price_open for p in buy_positions)
            MIN_SWITCH_PROFIT = point * 20
            # 🔥 PILIH YANG LEBIH PROFIT
            if buy_profit > (sell_profit + MIN_SWITCH_PROFIT):
                log_symbol(symbol, "KEEP BUY → CLOSE SELL (FAKE SWITCH)")
                close_opposite_positions(symbol, mt5.POSITION_TYPE_BUY)
                return

            else:
                log_symbol(symbol, "VALID SWITCH → CLOSE BUY")
                close_opposite_positions(symbol, mt5.POSITION_TYPE_SELL)

                _last_stop_price[symbol] = None
                _last_update_time[symbol] = 0
                _initial_stop_price[symbol] = None

                sl_price = normalize_price(ask + base_distance, digits)
                update_opposite_pending(symbol, sl_price, config)
                mark_updated(symbol, sl_price)
                _initial_stop_price[symbol] = sl_price

                return

    # =========================
    # INITIAL SL (WAJIB ADA)
    # =========================
    if _last_stop_price.get(symbol) is None:
        if position.type == mt5.POSITION_TYPE_BUY:
            sl_price = normalize_price(bid - base_distance, digits)
        else:
            sl_price = normalize_price(ask + base_distance, digits)

        update_opposite_pending(symbol, sl_price, config)
        mark_updated(symbol, sl_price)
        _initial_stop_price[symbol] = sl_price

        log_symbol(symbol, f"INIT SL PASANG → {sl_price:.3f}")
        return

    # =========================
    # PROFIT CHECK
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
    else:
        profit = position.price_open - ask

    MIN_PROFIT_ACTIVATE = point * 100  # ± $1

    # 🔥 HARD LOCK TRAILING (WAJIB)
    if profit < MIN_PROFIT_ACTIVATE:
        log_symbol(symbol, f"LOCK SL | PROFIT: {profit/point:.1f} pts")

        # ❗ pastikan tidak ada update sama sekali
        return

    # =========================
    # HOLD SL (TIDAK BOLEH GERAK)
    # =========================
    if profit < MIN_PROFIT_ACTIVATE:
        log_symbol(symbol, "WAIT PROFIT → LOCK SL")
        return

    # =========================
    # TRAILING LOGIC (STRICT)
    # =========================
    if position.type == mt5.POSITION_TYPE_BUY:
        # SELL STOP → hanya boleh naik
        new_price = bid - base_distance

        last_price = _last_stop_price.get(symbol)
        if last_price is not None and new_price < last_price:
            return

        MIN_LOCK_DISTANCE = point * 150
        if (bid - new_price) < MIN_LOCK_DISTANCE:
            return

    else:
        # BUY STOP → hanya boleh turun
        new_price = ask + base_distance

        last_price = _last_stop_price.get(symbol)
        if last_price is not None and new_price > last_price:
            return

        MIN_LOCK_DISTANCE = point * 150
        if (new_price - ask) < MIN_LOCK_DISTANCE:
            return

    new_price = normalize_price(new_price, digits)

    # =========================
    # TRAILING STEP
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
    # UPDATE TRAILING
    # =========================
    update_opposite_pending(symbol, new_price, config)
    mark_updated(symbol, new_price)

    if position.type == mt5.POSITION_TYPE_BUY:
        log_symbol(symbol, f"SELL STOP ↑ {new_price:.3f}")
    else:
        log_symbol(symbol, f"BUY STOP ↓ {new_price:.3f}")
