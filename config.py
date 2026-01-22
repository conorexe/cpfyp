"""Configuration for the Crypto Arbitrage Bot"""

# ============================================================
# OPERATION MODE
# ============================================================
# Options:
# - "cpp": Use high-performance C++ WebSocket clients (best for production)
# - "python": Use Python WebSocket clients (easier setup, no compilation needed)
# - "simulation": Generate realistic mock data (for testing when network is blocked)
MODE = "cpp"  # Change to "python" or "simulation" as needed

# Legacy flag for backward compatibility
SIMULATION_MODE = (MODE == "simulation")

# Trading pairs to monitor (normalized format)
TRADING_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
]

# Minimum profit percentage to flag as opportunity
MIN_PROFIT_THRESHOLD = 0.01  # 0.01% - lower for simulation to see more opportunities

# Triangular arbitrage settings
ENABLE_TRIANGULAR_ARBITRAGE = True
TRIANGULAR_MIN_PROFIT_THRESHOLD = 0.1  # 0.1% - typically needs higher threshold due to 3 trades
TRIANGULAR_TRADING_FEE = 0.001  # 0.1% per trade (typical exchange fee)

# Exchange WebSocket endpoints
EXCHANGE_WS_URLS = {
    "binance": "wss://stream.binance.com:9443/ws",
    "kraken": "wss://ws.kraken.com/v2",  # Kraken v2 API
    "coinbase": "wss://advanced-trade-ws.coinbase.com",  # Advanced Trade API
}

# Set to True if you're behind a proxy/firewall with SSL inspection
# This will disable certificate verification (not recommended for production)
SKIP_SSL_VERIFY = True

# Pair mappings per exchange (exchange-specific format)
PAIR_MAPPINGS = {
    "binance": {
        "BTC/USDT": "btcusdt",
        "ETH/USDT": "ethusdt",
        "SOL/USDT": "solusdt",
        "XRP/USDT": "xrpusdt",
    },
    "kraken": {
        "BTC/USDT": "XBT/USDT",
        "ETH/USDT": "ETH/USDT",
        "SOL/USDT": "SOL/USDT",
        "XRP/USDT": "XRP/USDT",
    },
    "coinbase": {
        "BTC/USDT": "BTC-USDT",
        "ETH/USDT": "ETH-USDT",
        "SOL/USDT": "SOL-USDT",
        "XRP/USDT": "XRP-USDT",
    },
}

# WebSocket reconnection settings
RECONNECT_DELAY = 5  # seconds
MAX_RECONNECT_ATTEMPTS = 10

# Web server settings
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
