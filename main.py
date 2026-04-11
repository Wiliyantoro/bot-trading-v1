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

# =========================
# GLOBAL
# =========================
last_position_ticket = {}
last_trade_time = {}


def log_symbol(symbol, message):
    log(f"[{symbol}] {message}")


def run_breakout(symbol, ask, bid, symbol_info, distance, config):
    buy_price = normalize_price(ask + distance, symbol_info.digits)
    sell_price = normalize_price(bid - distance, symbol_info.digits)

    log_symbol(symbol, "BREAKOUT")
    log_symbol(symbol, f"Buy Stop : {buy_price:.3f}")
    log_symbol(symbol, f"Sell Stop: {sell_price:.3f}")

    place_buy_stop(symbol, buy_price, config)
    place_sell_stop(symbol, sell_price, config)


def run_reversal(symbol, ask, bid, symbol_info, distance, config):
    buy_price = normalize_price(bid - distance, symbol_info.digits)
    sell_price = normalize_price(ask + distance, symbol_info.digits)

    log_symbol(symbol, "REVERSAL")
    log_symbol(symbol, f"Buy Limit : {buy_price:.3f}")
    log_symbol(symbol, f"Sell Limit: {sell_price:.3f}")

    place_buy_limit(symbol, buy_price, config)
    place_sell_limit(symbol, sell_price, config)


def get_switch_follow_distance(position, bid, ask, point):
    if position.type == mt5.POSITION_TYPE_BUY:
        profit = bid - position.price_open
    elif position.type == mt5.POSITION_TYPE_SELL:
        profit = position.price_open - ask
    else:
        return SWITCH_DISTANCE

    distance_follow = SWITCH_DISTANCE - (profit * SWITCH_FOLLOW_MULTIPLIER)
    distance_follow = min(SWITCH_MAX_DISTANCE, distance_follow)
    distance_follow = max(point, distance_follow)
    return distance_follow


def run_bot():
    global last_trade_time, last_position_ticket

    if not connect():
        return

    log(
        f"Bot started... MODE: {TRADING_MODE} | STRATEGY: {STRATEGY_MODE} | SYMBOLS: {', '.join(SYMBOLS)}"
    )

    while True:
        for symbol in SYMBOLS:
            try:
                config = get_symbol_config(symbol)
            except ValueError as error:
                log_symbol(symbol, f"Config error: {error}")
                continue

            tick = get_tick(symbol)

            if tick is None:
                log_symbol(symbol, "Tick tidak tersedia")
                time.sleep(SLEEP_NO_TICK)
                continue

            symbol_info = mt5.symbol_info(symbol)

            if symbol_info is None:
                log_symbol(symbol, "Symbol tidak ditemukan")
                time.sleep(SLEEP_NO_SYMBOL)
                continue

            bid = tick.bid
            ask = tick.ask
            spread = ask - bid

            log_symbol(symbol, f"Bid: {bid:.3f} | Ask: {ask:.3f} | Spread: {spread:.3f}")

            # =========================
            # ADA POSISI (MULTI POSITION)
            # =========================
            if has_position(symbol):
                positions = get_positions(symbol)

                if not positions:
                    time.sleep(SLEEP_EMPTY_POSITIONS)
                    continue

                first_position = positions[0]
                if STRATEGY_MODE == "SWITCH":
                    first_position = max(positions, key=lambda pos: pos.time)
                symbol_last_ticket = last_position_ticket.get(symbol)

                if first_position.ticket != symbol_last_ticket:
                    log_symbol(symbol, "Posisi baru terdeteksi")
                    time.sleep(SLEEP_NEW_POSITION)

                    if STRATEGY_MODE != "SWITCH":
                        close_opposite_pending(symbol, first_position.type)

                    last_position_ticket[symbol] = first_position.ticket
                    last_trade_time[symbol] = time.time()

                if STRATEGY_MODE == "SWITCH":
                    close_opposite_positions(symbol, first_position.type)
                    positions = get_positions(symbol)
                    if not positions:
                        time.sleep(SLEEP_EMPTY_POSITIONS)
                        continue

                    first_position = max(positions, key=lambda pos: pos.time)

                    distance_follow = get_switch_follow_distance(
                        first_position,
                        bid,
                        ask,
                        symbol_info.point,
                    )

                    if first_position.type == mt5.POSITION_TYPE_BUY:
                        close_opposite_pending(symbol, mt5.POSITION_TYPE_SELL)
                        sell_price = normalize_price(bid - distance_follow, symbol_info.digits)
                        update_opposite_pending(symbol, sell_price, config)
                        log_symbol(symbol, f"SWITCH FOLLOW SELL STOP: {sell_price:.3f}")
                    elif first_position.type == mt5.POSITION_TYPE_SELL:
                        close_opposite_pending(symbol, mt5.POSITION_TYPE_BUY)
                        buy_price = normalize_price(ask + distance_follow, symbol_info.digits)
                        update_opposite_pending(symbol, buy_price, config)
                        log_symbol(symbol, f"SWITCH FOLLOW BUY STOP: {buy_price:.3f}")

                for position in positions:
                    if position is None:
                        continue

                    if is_manual_position(position):
                        log_symbol(symbol, f"MANUAL POSITION | Ticket: {position.ticket}")
                    else:
                        log_symbol(symbol, f"BOT POSITION | Ticket: {position.ticket}")

                    if ENABLE_BASIC_BE:
                        apply_basic_be(position)

                    if ENABLE_DYNAMIC_SL:
                        apply_fast_cut_loss(position)

                    if ENABLE_DYNAMIC_BE:
                        apply_break_even(position)

                    if not is_sl_tp_set(position):
                        set_sl_tp(position, config)

                    apply_trailing(position, config)

                time.sleep(SLEEP_AFTER_POSITION_CYCLE)
                continue

            # =========================
            # MODE MANUAL -> STOP ENTRY
            # =========================
            if TRADING_MODE == "MANUAL":
                log_symbol(symbol, "MODE MANUAL -> Bot tidak entry")
                time.sleep(SLEEP_MANUAL_MODE)
                continue

            if STRATEGY_MODE == "SWITCH":
                buy_price = normalize_price(ask + SWITCH_DISTANCE, symbol_info.digits)
                sell_price = normalize_price(bid - SWITCH_DISTANCE, symbol_info.digits)

                update_opposite_pending(symbol, buy_price, config)
                update_opposite_pending(symbol, sell_price, config)

                log_symbol(
                    symbol,
                    f"SWITCH INIT | Buy Stop: {buy_price:.3f} | Sell Stop: {sell_price:.3f}",
                )

                time.sleep(SLEEP_LOOP_END)
                continue

            # =========================
            # AUTO MODE ENTRY
            # =========================
            current_time = time.time()
            symbol_last_trade_time = last_trade_time.get(symbol, 0)

            if current_time - symbol_last_trade_time < COOLDOWN_SECONDS:
                log_symbol(symbol, "Cooldown aktif")
                time.sleep(SLEEP_COOLDOWN)
                continue

            if spread > config["MAX_SPREAD"]:
                log_symbol(
                    symbol,
                    f"Spread terlalu besar ({spread:.3f} > {config['MAX_SPREAD']:.3f})",
                )
                time.sleep(SLEEP_SPREAD_BLOCK)
                continue

            if has_pending_orders(symbol):
                log_symbol(symbol, "Pending masih ada")
                time.sleep(SLEEP_PENDING_BLOCK)
                continue

            distance = max(spread * config["MULTIPLIER"], MIN_ENTRY_DISTANCE)

            # =========================
            # STRATEGY MODE CONTROL
            # =========================
            if STRATEGY_MODE == "BREAKOUT":
                run_breakout(symbol, ask, bid, symbol_info, distance, config)

            elif STRATEGY_MODE == "REVERSAL":
                run_reversal(symbol, ask, bid, symbol_info, distance, config)

            elif STRATEGY_MODE == "POINT":
                point_signal = detect_buy_sell_point(symbol)
                is_buy = point_signal.get("buy", False)
                is_sell = point_signal.get("sell", False)

                if is_buy:
                    buy_price = normalize_price(bid - distance, symbol_info.digits)
                    log_symbol(symbol, f"POINT BUY LIMIT: {buy_price:.3f}")
                    place_buy_limit(symbol, buy_price, config)

                if is_sell:
                    sell_price = normalize_price(ask + distance, symbol_info.digits)
                    log_symbol(symbol, f"POINT SELL LIMIT: {sell_price:.3f}")
                    place_sell_limit(symbol, sell_price, config)

                if not is_buy and not is_sell:
                    log_symbol(symbol, "POINT signal tidak ada, skip")

            elif STRATEGY_MODE == "AUTO":
                mode = get_market_mode(symbol)
                log_symbol(symbol, f"Market Mode: {mode}")

                if mode == "VOLATILE":
                    run_breakout(symbol, ask, bid, symbol_info, distance, config)
                elif mode == "SIDEWAYS":
                    run_reversal(symbol, ask, bid, symbol_info, distance, config)
                elif mode == "NORMAL":
                    log_symbol(symbol, "Market normal, skip")
            else:
                log_symbol(symbol, "STRATEGY_MODE tidak valid")

            time.sleep(SLEEP_LOOP_END)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        shutdown()
