import MetaTrader5 as mt5
from utils.logger import log


def connect():
    if not mt5.initialize():
        log("❌ Gagal konek ke MT5")
        return False

    log("✅ Berhasil konek ke MT5")
    return True


def shutdown():
    mt5.shutdown()
    log("🔌 MT5 disconnected")
