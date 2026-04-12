import time
import MetaTrader5 as mt5

from config.settings import (
    LOT,
    MAGIC_NUMBER,
    ORDER_VALIDATE_BUFFER_MULTIPLIER,
    SLIPPAGE,
)
from utils.logger import log

# 🔥 TRACK UPDATE
last_pending_update = {}

# 🔥 COOLDOWN UPDATE
PENDING_UPDATE_COOLDOWN = 2


def validate_price(symbol, price, order_type):
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if symbol_info is None or tick is None:
        return price

    point = symbol_info.point
    stop_level = symbol_info.trade_stops_level * point

    spread = tick.ask - tick.bid
    buffer = spread * ORDER_VALIDATE_BUFFER_MULTIPLIER
    min_distance = stop_level + buffer

    if order_type == mt5.ORDER_TYPE_BUY_STOP:
        if (price - tick.ask) < min_distance:
            price = tick.ask + min_distance

    elif order_type == mt5.ORDER_TYPE_SELL_STOP:
        if (tick.bid - price) < min_distance:
            price = tick.bid - min_distance

    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
        if (tick.bid - price) < min_distance:
            price = tick.bid - min_distance

    elif order_type == mt5.ORDER_TYPE_SELL_LIMIT:
        if (price - tick.ask) < min_distance:
            price = tick.ask + min_distance

    return round(price, symbol_info.digits)


def _get_lot(config):
    if config is None:
        return LOT
    return config.get("LOT", LOT)


def get_pending_orders(symbol):
    orders = mt5.orders_get(symbol=symbol)
    return orders if orders else []


def has_pending_orders(symbol):
    return len(get_pending_orders(symbol)) > 0


# =========================
# PLACE ORDERS (TIDAK DIUBAH)
# =========================
def place_buy_stop(symbol, price, config=None):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_BUY_STOP)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": _get_lot(config),
        "type": mt5.ORDER_TYPE_BUY_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"Buy Stop @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_sell_stop(symbol, price, config=None):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_SELL_STOP)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": _get_lot(config),
        "type": mt5.ORDER_TYPE_SELL_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"Sell Stop @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_buy_limit(symbol, price, config=None):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_BUY_LIMIT)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": _get_lot(config),
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"Buy Limit @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_sell_limit(symbol, price, config=None):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_SELL_LIMIT)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": _get_lot(config),
        "type": mt5.ORDER_TYPE_SELL_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"Sell Limit @ {price:.3f} | Retcode: {result.retcode}")
    return result


# =========================
# 🔥 SMART UPDATE PENDING
# =========================
def update_opposite_pending(symbol, price, config=None):
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if symbol_info is None or tick is None:
        return None

    now = time.time()
    last_time = last_pending_update.get(symbol, 0)

    # 🔥 COOLDOWN
    if now - last_time < PENDING_UPDATE_COOLDOWN:
        return None

    target_type = (
        mt5.ORDER_TYPE_BUY_STOP if price >= tick.ask else mt5.ORDER_TYPE_SELL_STOP
    )

    price = validate_price(symbol, price, target_type)

    orders = get_pending_orders(symbol)
    same_orders = [o for o in orders if o.type == target_type]

    tolerance = symbol_info.point * 2

    # =========================
    # 🔥 CEK APA PERLU UPDATE
    # =========================
    if same_orders:
        current = same_orders[0]

        if abs(current.price_open - price) < tolerance:
            return current

        # 🔥 REMOVE OLD
        for order in same_orders:
            mt5.order_send(
                {"action": mt5.TRADE_ACTION_REMOVE, "order": order.ticket}
            )
            log(f"Remove pending {order.ticket}")

    # =========================
    # 🔥 PLACE NEW
    # =========================
    if target_type == mt5.ORDER_TYPE_BUY_STOP:
        result = place_buy_stop(symbol, price, config)
    else:
        result = place_sell_stop(symbol, price, config)

    last_pending_update[symbol] = now

    return result