import time
import MetaTrader5 as mt5

from strategy.market_mode import get_market_mode
from config.settings import *
from core.mt5_connector import connect, shutdown
from core.market_data import get_tick
from core.order_manager import (
    has_pending_orders,
    place_buy_stop,
    place_sell_stop,
    place_buy_limit,
    place_sell_limit,
)
from core.position_manager import (
    has_position,
    get_position,
    set_sl_tp,
    close_opposite_pending,
    is_sl_tp_set,
    is_manual_position,
)
from utils.logger import log
from utils.price_formatter import normalize_price
from risk.breakeven import apply_break_even
from risk.trailing import apply_trailing

# =========================
# GLOBAL
# =========================
last_position_ticket = None
last_trade_time = 0
COOLDOWN_SECONDS = 25


def run_bot():
    global last_trade_time, last_position_ticket

    if not connect():
        return

    log("🚀 Bot started...")

    while True:
        tick = get_tick(SYMBOL)

        if tick is None:
            log("❌ Tick tidak tersedia")
            time.sleep(2)
            continue

        symbol_info = mt5.symbol_info(SYMBOL)

        if symbol_info is None:
            log("❌ Symbol tidak ditemukan")
            time.sleep(2)
            continue

        bid = tick.bid
        ask = tick.ask
        spread = ask - bid

        log(f"📊 Bid: {bid:.3f} | Ask: {ask:.3f} | Spread: {spread:.3f}")

        # =========================
        # ADA POSISI (BOT + MANUAL)
        # =========================
        if has_position(SYMBOL):
            position = get_position(SYMBOL)

            if position is None:
                time.sleep(2)
                continue

            # 🔥 DETEKSI MODE
            if is_manual_position(position):
                log("🧠 MODE: MANUAL TRADE")
            else:
                log("🤖 MODE: BOT TRADE")

            # 🔥 HANDLE POSISI BARU
            if position.ticket != last_position_ticket:
                log("🆕 Posisi baru terdeteksi")
                time.sleep(1)

                close_opposite_pending(SYMBOL, position.type)

                last_position_ticket = position.ticket
                last_trade_time = time.time()

            # 🔥 SET SL (manual / bot)
            if not is_sl_tp_set(position):
                set_sl_tp(position)

            # 🔥 BE + TRAILING (SEMUA POSISI)
            apply_break_even(position)
            apply_trailing(position)

            time.sleep(2)
            continue

        # =========================
        # BELUM ADA POSISI
        # =========================
        current_time = time.time()

        # cooldown
        if current_time - last_trade_time < COOLDOWN_SECONDS:
            log("⏳ Cooldown aktif")
            time.sleep(2)
            continue

        # spread filter keras
        if spread > 0.5:
            log("⚠️ Spread terlalu lebar")
            time.sleep(2)
            continue

        # spread normal filter
        if spread > MAX_SPREAD:
            log("⚠️ Spread terlalu besar")
            time.sleep(2)
            continue

        # pending check
        if has_pending_orders(SYMBOL):
            log("⏳ Pending masih ada")
            time.sleep(2)
            continue

        # =========================
        # DETECT MODE
        # =========================
        mode = get_market_mode(SYMBOL)
        log(f"📊 Market Mode: {mode}")

        # 🔥 DISTANCE (ANTI DEKAT)
        distance = max(spread * MULTIPLIER, 0.4)

        # =========================
        # BREAKOUT MODE
        # =========================
        if mode == "VOLATILE":
            buy_price = normalize_price(ask + distance, symbol_info.digits)
            sell_price = normalize_price(bid - distance, symbol_info.digits)

            log("🚀 MODE: BREAKOUT")
            log(f"🎯 Buy Stop : {buy_price:.3f}")
            log(f"🎯 Sell Stop: {sell_price:.3f}")

            place_buy_stop(SYMBOL, buy_price)
            place_sell_stop(SYMBOL, sell_price)

        # =========================
        # REVERSAL MODE
        # =========================
        elif mode == "SIDEWAYS":
            buy_price = normalize_price(bid - distance, symbol_info.digits)
            sell_price = normalize_price(ask + distance, symbol_info.digits)

            log("🔄 MODE: REVERSAL")
            log(f"🎯 Buy Limit : {buy_price:.3f}")
            log(f"🎯 Sell Limit: {sell_price:.3f}")

            place_buy_limit(SYMBOL, buy_price)
            place_sell_limit(SYMBOL, sell_price)

        # =========================
        # NORMAL MODE (NO TRADE)
        # =========================
        elif mode == "NORMAL":
            log("⚠️ Market normal, skip")

        time.sleep(5)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        shutdown()