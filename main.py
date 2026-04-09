import time
import MetaTrader5 as mt5

from config.settings import *
from core.mt5_connector import connect, shutdown
from core.market_data import get_tick
from core.order_manager import has_pending_orders, place_buy_stop, place_sell_stop
from core.position_manager import (
    has_position,
    get_position,
    set_sl_tp,
)
from utils.logger import log
from utils.price_formatter import normalize_price
from risk.breakeven import apply_break_even
from risk.trailing import apply_trailing
from core.position_manager import close_opposite_pending
from core.position_manager import is_sl_tp_set
from core.order_manager import place_buy_limit, place_sell_limit
from strategy.trend_detector import get_trend
from strategy.fake_breakout_filter import (
    get_last_candle,
    is_strong_bullish,
    is_strong_bearish,
)

last_position_ticket = None
STRATEGY_MODE = "BREAKOUT"  # atau "REVERSAL,BREAKOUT"

last_trade_time = 0
COOLDOWN_SECONDS = 15


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
        # MODE: ADA POSISI
        # =========================
        if has_position(SYMBOL):
            log("📌 Posisi terdeteksi")

            position = get_position(SYMBOL)

            # hanya hapus kalau posisi SUDAH FIX

            if position is not None:
                # hanya delay saat posisi BARU
                if position.ticket != last_position_ticket:
                    log("🆕 Posisi baru terdeteksi, delay eksekusi...")
                    time.sleep(1)

                    close_opposite_pending(SYMBOL, position.type)

                    last_position_ticket = position.ticket

                    # 🔥 SET COOLDOWN DI SINI (BENAR)
                    last_trade_time = time.time()

            # ✅ set SL TP hanya sekali

            if not is_sl_tp_set(position):
                set_sl_tp(position)

            apply_break_even(position)

            # 🔥 NEW: TRAILING STOP

            apply_trailing(position)

            time.sleep(2)
            continue

        # =========================
        # MODE: BELUM ADA POSISI
        # =========================

        current_time = time.time()

        if current_time - last_trade_time < COOLDOWN_SECONDS:
            log("⏳ Cooldown aktif, skip entry...")
            time.sleep(2)
            continue
        # 🔥 HARD FILTER (SUPER LEBAR)
        if spread > 0.5:
            log("⚠️ Spread terlalu lebar (hard filter), skip...")
            time.sleep(2)
            continue
        if spread > MAX_SPREAD:
            log("⚠️ Spread terlalu besar, skip...")
            time.sleep(2)
            continue

        if has_pending_orders(SYMBOL):
            log("⏳ Pending order masih ada, skip...")
            time.sleep(2)
            continue

        base_distance = spread * MULTIPLIER
        min_distance = 0.35

        distance = max(base_distance, min_distance)

        trend = get_trend(SYMBOL)
        # 🔥 ANTI OVER-EXTENDED TREND
        rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M1, 0, 50)
        if rates is None or len(rates) < 30:
            log("❌ Gagal ambil data MA, skip...")
            time.sleep(2)
            continue
        closes = [r["close"] for r in rates]

        fast_ma = sum(closes[-10:]) / 10
        slow_ma = sum(closes[-30:]) / 30
        diff = abs(fast_ma - slow_ma)
        candle = get_last_candle(SYMBOL)

        if candle is None:
            log("❌ Candle tidak tersedia")
            time.sleep(2)
            continue
        # =========================
        # STRONG TREND MODE
        # =========================
        if diff > 3:
            log("🔥 Strong Trend terdeteksi!")

            if diff > 5:
                distance = max(distance * 0.6, 0.3)
            else:
                distance = max(distance * 0.8, 0.35)

            if has_pending_orders(SYMBOL):
                log("⏳ Sudah ada pending (strong trend), skip...")
                time.sleep(2)
                continue
            if trend == "UPTREND" and not is_strong_bullish(candle):
                log("⚠️ Skip BUY (weak candle)")
                continue

            if trend == "DOWNTREND" and not is_strong_bearish(candle):
                log("⚠️ Skip SELL (weak candle)")
                continue
            if trend == "UPTREND":
                buy_price = normalize_price(ask + distance, symbol_info.digits)

                # 🔥 VALIDASI STOP LEVEL DI SINI
                # stop_level = symbol_info.trade_stops_level * symbol_info.point
                # buffer = spread * 1.5
                # min_distance = stop_level + buffer
                # if (buy_price - ask) < min_distance:
                #     buy_price = ask + min_distance

                buy_price = normalize_price(buy_price, symbol_info.digits)

                log("🚀 MODE: STRONG UPTREND")
                log(f"🎯 Buy Stop Only : {buy_price:.3f}")

                place_buy_stop(SYMBOL, buy_price)

            elif trend == "DOWNTREND":
                sell_price = normalize_price(bid - distance, symbol_info.digits)

                stop_level = symbol_info.trade_stops_level * symbol_info.point
                if (bid - sell_price) < min_distance:
                    sell_price = bid - min_distance

                sell_price = normalize_price(sell_price, symbol_info.digits)

                log("🚀 MODE: STRONG DOWNTREND")
                log(f"🎯 Sell Stop Only: {sell_price:.3f}")

                place_sell_stop(SYMBOL, sell_price)

            time.sleep(5)
            continue

        log(f"📊 Trend: {trend}")

        candle = get_last_candle(SYMBOL)

        if candle is None:
            log("❌ Candle tidak tersedia")
            continue

        # =========================
        # BREAKOUT MODE + FILTER
        # =========================
        if trend in ["UPTREND", "DOWNTREND"]:
            buy_price = normalize_price(ask + distance, symbol_info.digits)
            sell_price = normalize_price(bid - distance, symbol_info.digits)

            # 🔥 FILTER FAKE BREAKOUT
            if not is_strong_bullish(candle):
                log("⚠️ Skip BUY - candle tidak kuat")
                buy_price = None

            if not is_strong_bearish(candle):
                log("⚠️ Skip SELL - candle tidak kuat")
                sell_price = None

            log("🚀 MODE: BREAKOUT + FILTER")
            # stop_level = symbol_info.trade_stops_level * symbol_info.point
            # if buy_price:
            #     if (buy_price - ask) < stop_level:
            #         buy_price = ask + stop_level

            buy_price = normalize_price(buy_price, symbol_info.digits)

            log(f"🎯 Buy Stop : {buy_price:.3f}")
            place_buy_stop(SYMBOL, buy_price)

            if sell_price:
                # if (bid - sell_price) < stop_level:
                #     sell_price = bid - stop_level

                sell_price = normalize_price(sell_price, symbol_info.digits)

                log(f"🎯 Sell Stop: {sell_price:.3f}")
                place_sell_stop(SYMBOL, sell_price)

        # =========================
        # REVERSAL MODE
        # =========================
        elif trend == "SIDEWAYS":
            buy_price = normalize_price(buy_price, symbol_info.digits)
            sell_price = normalize_price(sell_price, symbol_info.digits)

            log("🔄 MODE: REVERSAL")
            log(f"🎯 Buy Limit : {buy_price:.3f}")
            log(f"🎯 Sell Limit: {sell_price:.3f}")

            place_buy_limit(SYMBOL, buy_price)
            place_sell_limit(SYMBOL, sell_price)

        else:
            log("⚠️ Trend tidak jelas, skip...")

        time.sleep(5)


if __name__ == "__main__":
    try:
        run_bot()
    except KeyboardInterrupt:
        shutdown()
