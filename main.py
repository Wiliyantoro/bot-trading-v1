import time
import MetaTrader5 as mt5

from config.settings import (
    COOLDOWN_SECONDS,
    ENABLE_BASIC_BE,
    ENABLE_DYNAMIC_BE,
    ENABLE_DYNAMIC_SL,
    MIN_ENTRY_DISTANCE,
    SLEEP_AFTER_POSITION_CYCLE,
    SLEEP_COOLDOWN,
    SLEEP_EMPTY_POSITIONS,
    SLEEP_LOOP_END,
    SLEEP_MANUAL_MODE,
    SLEEP_NEW_POSITION,
    SLEEP_NO_SYMBOL,
    SLEEP_NO_TICK,
    SLEEP_PENDING_BLOCK,
    SLEEP_SPREAD_BLOCK,
    STRATEGY_MODE,
    SWITCH_DISTANCE,
    SWITCH_FOLLOW_MULTIPLIER,
    SWITCH_MAX_DISTANCE,
    SYMBOLS,
    TRADING_MODE,
    get_symbol_config,
)
from core.market_data import get_tick
from core.mt5_connector import connect, shutdown
from core.order_manager import (
    has_pending_orders,
    place_buy_limit,
    place_buy_stop,
    place_sell_limit,
    place_sell_stop,
    update_opposite_pending,
)
from core.position_manager import (
    apply_fast_cut_loss,
    close_opposite_positions,
    close_opposite_pending,
    get_positions,
    has_position,
    is_manual_position,
    is_sl_tp_set,
    set_sl_tp,
)
from risk.breakeven import apply_break_even
from risk.breakeven_basic import apply_basic_be
from risk.trailing import apply_trailing
from strategy.market_mode import get_market_mode
from strategy.point_detector import detect_buy_sell_point
from utils.logger import log
from utils.price_formatter import normalize_price

last_position_ticket = {}
last_trade_time = {}
last_flip_time = {}  # 🔥 tambahan anti flip spam


def log_symbol(symbol, message):
    log(f"[{symbol}] {message}")


# =========================
# 🔥 SWITCH FOLLOW (FIX TOTAL)
# =========================
def get_switch_follow_distance(position, bid, ask):
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = position.price_open - ask
    else:
        return SWITCH_DISTANCE

    # 🔥 FIX: makin profit → makin dekat
    distance = SWITCH_DISTANCE + (profit * SWITCH_FOLLOW_MULTIPLIER)

    # 🔥 batas max
    distance = min(distance, SWITCH_MAX_DISTANCE)

    # 🔥 minimal jarak
    if distance <= 0:
        distance = SWITCH_DISTANCE

    return distance


def run_bot():
    global last_trade_time, last_position_ticket, last_flip_time

    if not connect():
        return

    log(f"🚀 Bot started | MODE: {TRADING_MODE} | STRATEGY: {STRATEGY_MODE}")

    while True:
        for symbol in SYMBOLS:

            config = get_symbol_config(symbol)

            tick = get_tick(symbol)
            if tick is None:
                time.sleep(SLEEP_NO_TICK)
                continue

            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                time.sleep(SLEEP_NO_SYMBOL)
                continue

            bid = tick.bid
            ask = tick.ask
            spread = ask - bid

            log_symbol(symbol, f"Bid: {bid:.3f} | Ask: {ask:.3f}")

            # =========================
            # ADA POSISI
            # =========================
            if has_position(symbol):

                positions = get_positions(symbol)
                if not positions:
                    time.sleep(SLEEP_EMPTY_POSITIONS)
                    continue

                # ambil posisi terbaru
                position = max(positions, key=lambda p: p.time)

                # 🔥 ANTI FLIP SPAM
                now = time.time()
                last_flip = last_flip_time.get(symbol, 0)

                # =========================
                # 🔥 SWITCH LOGIC
                # =========================
                if STRATEGY_MODE == "SWITCH":

                    # 🔥 CLOSE posisi lawan
                    close_opposite_positions(symbol, position.type)

                    # 🔥 HITUNG FOLLOW
                    distance = get_switch_follow_distance(position, bid, ask)

                    # =========================
                    # BUY ACTIVE
                    # =========================
                    if position.type == mt5.POSITION_TYPE_BUY:
                        close_opposite_pending(symbol, mt5.POSITION_TYPE_SELL)

                        sell_price = normalize_price(
                            bid - distance, symbol_info.digits
                        )

                        update_opposite_pending(symbol, sell_price, config)

                        log_symbol(symbol, f"SWITCH FOLLOW SELL: {sell_price:.3f}")

                    # =========================
                    # SELL ACTIVE
                    # =========================
                    elif position.type == mt5.POSITION_TYPE_SELL:
                        close_opposite_pending(symbol, mt5.POSITION_TYPE_BUY)

                        buy_price = normalize_price(
                            ask + distance, symbol_info.digits
                        )

                        update_opposite_pending(symbol, buy_price, config)

                        log_symbol(symbol, f"SWITCH FOLLOW BUY: {buy_price:.3f}")

                # =========================
                # MANAGEMENT
                # =========================
                for pos in positions:

                    if ENABLE_BASIC_BE:
                        apply_basic_be(pos)

                    if ENABLE_DYNAMIC_SL:
                        apply_fast_cut_loss(pos)

                    if ENABLE_DYNAMIC_BE:
                        apply_break_even(pos)

                    if not is_sl_tp_set(pos):
                        set_sl_tp(pos, config)

                    apply_trailing(pos, config)

                time.sleep(SLEEP_AFTER_POSITION_CYCLE)
                continue

            # =========================
            # MANUAL MODE
            # =========================
            if TRADING_MODE == "MANUAL":
                time.sleep(SLEEP_MANUAL_MODE)
                continue

            # =========================
            # INIT SWITCH
            # =========================
            if STRATEGY_MODE == "SWITCH":

                buy_price = normalize_price(
                    ask + SWITCH_DISTANCE, symbol_info.digits
                )
                sell_price = normalize_price(
                    bid - SWITCH_DISTANCE, symbol_info.digits
                )

                update_opposite_pending(symbol, buy_price, config)
                update_opposite_pending(symbol, sell_price, config)

                log_symbol(
                    symbol,
                    f"SWITCH INIT | BUY: {buy_price:.3f} | SELL: {sell_price:.3f}",
                )

                time.sleep(SLEEP_LOOP_END)
                continue

            # =========================
            # NORMAL STRATEGY (TIDAK DIUBAH)
            # =========================
            if has_pending_orders(symbol):
                time.sleep(SLEEP_PENDING_BLOCK)
                continue

            distance = max(spread * config["MULTIPLIER"], MIN_ENTRY_DISTANCE)

            if STRATEGY_MODE == "BREAKOUT":
                place_buy_stop(symbol, ask + distance, config)
                place_sell_stop(symbol, bid - distance, config)

            elif STRATEGY_MODE == "REVERSAL":
                place_buy_limit(symbol, bid - distance, config)
                place_sell_limit(symbol, ask + distance, config)

            elif STRATEGY_MODE == "POINT":
                signal = detect_buy_sell_point(symbol)

                if signal.get("buy"):
                    place_buy_limit(symbol, bid - distance, config)

                if signal.get("sell"):
                    place_sell_limit(symbol, ask + distance, config)

            time.sleep(SLEEP_LOOP_END)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        shutdown()