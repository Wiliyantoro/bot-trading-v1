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
    get_positions,   # 🔥 TAMBAHAN
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

    log(f"🚀 Bot started... MODE: {TRADING_MODE}")

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
        # ADA POSISI (MULTI POSITION SUPPORT)
        # =========================
        if has_position(SYMBOL):

            positions = get_positions(SYMBOL)

            if not positions:
                time.sleep(2)
                continue

            # 🔥 HANDLE POSISI BARU (sekali saja)
            first_position = positions[0]

            if first_position.ticket != last_position_ticket:
                log("🆕 Posisi baru terdeteksi")
                time.sleep(1)

                close_opposite_pending(SYMBOL, first_position.type)

                last_position_ticket = first_position.ticket
                last_trade_time = time.time()

            # =========================
            # 🔥 LOOP SEMUA POSISI
            # =========================
            for position in positions:

                if position is None:
                    continue

                # 🔥 DETEKSI MANUAL / BOT
                if is_manual_position(position):
                    log(f"🧠 MANUAL POSITION | Ticket: {position.ticket}")
                else:
                    log(f"🤖 BOT POSITION | Ticket: {position.ticket}")

                # =========================
                # SET SL/TP
                # =========================
                if not is_sl_tp_set(position):
                    set_sl_tp(position)

                # =========================
                # BREAK EVEN
                # =========================
                apply_break_even(position)

                # =========================
                # TRAILING + TP DINAMIS
                # =========================
                apply_trailing(position)

            time.sleep(2)
            continue

        # =========================
        # MODE MANUAL → STOP ENTRY
        # =========================
        if TRADING_MODE == "MANUAL":
            log("⏸️ MODE MANUAL → Bot tidak entry")
            time.sleep(3)
            continue

        # =========================
        # AUTO MODE ENTRY
        # =========================
        current_time = time.time()

        if current_time - last_trade_time < COOLDOWN_SECONDS:
            log("⏳ Cooldown aktif")
            time.sleep(2)
            continue

        if spread > 0.5:
            log("⚠️ Spread terlalu lebar")
            time.sleep(2)
            continue

        if spread > MAX_SPREAD:
            log("⚠️ Spread terlalu besar")
            time.sleep(2)
            continue

        if has_pending_orders(SYMBOL):
            log("⏳ Pending masih ada")
            time.sleep(2)
            continue

        # =========================
        # DETECT MARKET MODE
        # =========================
        mode = get_market_mode(SYMBOL)
        log(f"📊 Market Mode: {mode}")

        distance = max(spread * MULTIPLIER, 0.4)

        # =========================
        # BREAKOUT
        # =========================
        if mode == "VOLATILE":
            buy_price = normalize_price(ask + distance, symbol_info.digits)
            sell_price = normalize_price(bid - distance, symbol_info.digits)

            log("🚀 BREAKOUT")
            log(f"🎯 Buy Stop : {buy_price:.3f}")
            log(f"🎯 Sell Stop: {sell_price:.3f}")

            place_buy_stop(SYMBOL, buy_price)
            place_sell_stop(SYMBOL, sell_price)

        # =========================
        # REVERSAL
        # =========================
        elif mode == "SIDEWAYS":
            buy_price = normalize_price(bid - distance, symbol_info.digits)
            sell_price = normalize_price(ask + distance, symbol_info.digits)

            log("🔄 REVERSAL")
            log(f"🎯 Buy Limit : {buy_price:.3f}")
            log(f"🎯 Sell Limit: {sell_price:.3f}")

            place_buy_limit(SYMBOL, buy_price)
            place_sell_limit(SYMBOL, sell_price)

        elif mode == "NORMAL":
            log("⚠️ Market normal, skip")

        time.sleep(5)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        shutdown()