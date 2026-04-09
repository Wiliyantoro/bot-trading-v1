import MetaTrader5 as mt5
from config.settings import *
from utils.logger import log

import MetaTrader5 as mt5
from config.settings import *
from utils.logger import log

def validate_price(symbol, price, order_type):
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if symbol_info is None or tick is None:
        return price

    point = symbol_info.point
    stop_level = symbol_info.trade_stops_level * point

    spread = tick.ask - tick.bid
    buffer = spread * 1.5

    min_distance = stop_level + buffer

    # =========================
    # BUY STOP
    # =========================
    if order_type == mt5.ORDER_TYPE_BUY_STOP:
        if (price - tick.ask) < min_distance:
            price = tick.ask + min_distance

    # =========================
    # SELL STOP
    # =========================
    elif order_type == mt5.ORDER_TYPE_SELL_STOP:
        if (tick.bid - price) < min_distance:
            price = tick.bid - min_distance

    # =========================
    # BUY LIMIT
    # =========================
    elif order_type == mt5.ORDER_TYPE_BUY_LIMIT:
        if (tick.bid - price) < min_distance:
            price = tick.bid - min_distance

    # =========================
    # SELL LIMIT
    # =========================
    elif order_type == mt5.ORDER_TYPE_SELL_LIMIT:
        if (price - tick.ask) < min_distance:
            price = tick.ask + min_distance

    return round(price, symbol_info.digits)

def get_pending_orders(symbol):
    orders = mt5.orders_get(symbol=symbol)
    return orders if orders else []


def has_pending_orders(symbol):
    orders = get_pending_orders(symbol)
    return len(orders) > 0


def place_buy_stop(symbol, price):
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📈 Buy Stop placed @ {price} | Result: {result}")
    return result


def place_sell_stop(symbol, price):
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_SELL_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📉 Sell Stop placed @ {price} | Result: {result}")
    return result


def place_buy_limit(symbol, price):
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📗 Buy Limit placed @ {price} | Result: {result.retcode}")
    return result


def place_sell_limit(symbol, price):
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_SELL_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📕 Sell Limit placed @ {price} | Result: {result.retcode}")
    return result


def get_pending_orders(symbol):
    orders = mt5.orders_get(symbol=symbol)
    return orders if orders else []


def has_pending_orders(symbol):
    orders = get_pending_orders(symbol)
    return len(orders) > 0


def place_buy_stop(symbol, price):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_BUY_STOP)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📈 Buy Stop @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_sell_stop(symbol, price):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_SELL_STOP)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_SELL_STOP,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Stop",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📉 Sell Stop @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_buy_limit(symbol, price):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_BUY_LIMIT)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Buy Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📗 Buy Limit @ {price:.3f} | Retcode: {result.retcode}")
    return result


def place_sell_limit(symbol, price):
    price = validate_price(symbol, price, mt5.ORDER_TYPE_SELL_LIMIT)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_SELL_LIMIT,
        "price": price,
        "deviation": SLIPPAGE,
        "magic": MAGIC_NUMBER,
        "comment": "Sell Limit",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    result = mt5.order_send(request)
    log(f"📕 Sell Limit @ {price:.3f} | Retcode: {result.retcode}")
    return result
