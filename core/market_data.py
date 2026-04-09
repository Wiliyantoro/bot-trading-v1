import MetaTrader5 as mt5


def get_tick(symbol):
    tick = mt5.symbol_info_tick(symbol)
    return tick


def get_spread(symbol):
    tick = get_tick(symbol)
    if tick is None:
        return None

    spread = tick.ask - tick.bid
    return spread
