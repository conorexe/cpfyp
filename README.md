# 🚀 Crypto Arbitrage Bot MVP

A real-time cryptocurrency arbitrage opportunity detector using WebSocket feeds from major exchanges.

## Features

- **Real-time Price Feeds**: WebSocket connections to Binance, Kraken, and Coinbase
- **Arbitrage Detection**: Automatically identifies price discrepancies across exchanges
- **Live Dashboard**: Beautiful web interface showing opportunities in real-time
- **Multiple Modes**: Python, C++ (50-100x faster), or Simulation
- **Configurable Pairs**: Monitor multiple trading pairs simultaneously

## Quick Start

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Choose Your Mode

Edit `config.py` and set `MODE`:
- `"python"` - Python WebSocket clients (easy setup, no compilation)
- `"cpp"` - C++ high-performance engine (production-ready, requires build)
- `"simulation"` - Mock data for testing (no network needed)

### 3. Run the Bot

#### Option A: Python Mode (Default)
```bash
python main.py
```

#### Option B: C++ Mode (High Performance)
```bash
# Terminal 1: Build and run C++ engine
cd cpp
chmod +x build.sh  # Linux/Mac only
./build.sh         # or build.bat on Windows
cd build
./arb_bot          # or arb_bot.exe on Windows

# Terminal 2: Run Python dashboard
python main.py
```

#### Option C: Simulation Mode
```bash
# Set MODE = "simulation" in config.py
python main.py
```

### 4. Open Dashboard

Navigate to `http://localhost:8000` in your browser.

## Architecture

### Python Mode
```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Binance   │     │   Kraken    │     │  Coinbase   │
│  WebSocket  │     │  WebSocket  │     │  WebSocket  │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Arbitrage  │
                    │   Engine    │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    Web      │
                    │  Dashboard  │
                    └─────────────┘
```

### C++ Mode (High Performance)
```
┌─────────────────────────────────────────┐
│  C++ Engine (50-100x faster)            │
│                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Binance │  │ Kraken  │  │Coinbase │ │
│  │   WS    │  │   WS    │  │   WS    │ │
│  └────┬────┘  └────┬────┘  └────┬────┘ │
│       └────────────┼─────────────┘      │
│            ┌───────▼────────┐           │
│            │ TCP Server     │           │
│            │ (Port 5555)    │           │
│            └───────┬────────┘           │
└────────────────────┼────────────────────┘
                     │ JSON Stream
              ┌──────▼──────┐
              │   Python    │
              │  Dashboard  │
              └─────────────┘
```

## Supported Exchanges

| Exchange | Status | WebSocket API |
|----------|--------|---------------|
| Bybit    | ✅     | v5 Public Ticker |
| OKX      | ✅     | v5 Public Ticker |
| Binance  | ✅     | Public BookTicker |
| Kraken   | ⚠️     | v2 Ticker (may have SSL issues) |
| Coinbase | ⚠️     | Advanced Trade (may have SSL issues) |

## Monitored Pairs

- BTC/USDT
- ETH/USDT
- SOL/USDT
- XRP/USDT

## Configuration

Edit `config.py` to customize:
- **MODE**: Choose `"python"`, `"cpp"`, or `"simulation"`
- **Trading pairs**: BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT
- **Minimum threshold**: Profit percentage to flag opportunities
- **WebSocket settings**: Reconnection delays and attempts

## Performance Comparison

| Mode | Latency | Throughput | Setup Effort |
|------|---------|------------|--------------|
| Python | ~10ms | ~1K updates/s | ⭐ Easy |
| C++ | ~0.1ms | ~10K+ updates/s | ⭐⭐⭐ Advanced |
| Simulation | N/A | Unlimited | ⭐ Easy |

**When to use C++:**
- Production trading with real money
- Opportunities disappear in <100ms
- Need to process >5K updates/second
- Every millisecond counts

**When Python is fine:**
- MVP/testing phase
- Arbitrage windows are >500ms
- Monitoring only (not executing trades)
- `SKIP_SSL_VERIFY`: Set to `True` if behind a corporate proxy/firewall with SSL inspection

## Disclaimer

⚠️ This is an MVP for educational purposes. Real arbitrage trading involves:
- Exchange fees (trading + withdrawal)
- Transfer times between exchanges
- Slippage on large orders
- API rate limits
- Capital requirements on multiple exchanges

Always do your own research before trading.

## License

MIT
