# Crypto Arbitrage Bot - Full Stack Implementation

A high-performance, multi-strategy cryptocurrency arbitrage detection system with advanced ML predictions, real-time visualizations, and comprehensive monitoring.

## 🚀 Features

### Phase 1: Multi-Strategy Engine
- **Simple Cross-Exchange Arbitrage**: Buy low on Exchange A, sell high on Exchange B
- **Triangular Arbitrage**: USDT → BTC → ETH → USDT within single exchanges
- **Cross-Exchange Triangular**: Multi-exchange triangular paths with transfer simulation
- **Order Book Aggregation**: Unified view of liquidity across all venues
- **Execution Simulation**: Realistic slippage, fees, and transfer time modeling

### Phase 2: Data Engineering
- **TimescaleDB Integration**: Store billions of ticks with automatic compression
- **Historical Replay Engine**: Replay any day at 1x to 1000x speed for backtesting
- **Prometheus Metrics**: Full observability with Grafana dashboards
- **Feed Health Monitoring**: Track latency, staleness, and update rates

### Phase 3: ML Pipeline
- **Advanced Feature Engineering**:
  - Price velocity/acceleration
  - Order book imbalance
  - Cross-exchange spread momentum
  - Volatility regime features
  - Technical indicators (RSI, MACD, Bollinger)
- **Sequence Models**: LSTM/Transformer architecture for temporal patterns
- **ONNX Runtime**: <10ms inference latency
- **Opportunity Prediction**: Predict arbitrage windows 500ms-2s ahead

### Phase 4: Visualization Excellence
- **Order Book Heatmap**: Depth visualization with animated changes
- **Opportunity Flow Diagram**: Sankey diagram showing money movement
- **3D Market Visualization**: Interactive Three.js surface plots
- **Latency Globe**: World map with real-time exchange latencies

## 📁 Project Structure

```
├── config.py                    # Configuration settings
├── main.py                      # Main entry point
├── requirements.txt             # Python dependencies
│
├── engines/                     # Engine package (for clean imports)
│   └── __init__.py
│
├── engine.py                    # Core arbitrage detection
├── engine_triangular.py         # Triangular arbitrage paths
├── engine_orderbook.py          # Order book aggregation
├── engine_statistical.py        # Statistical arbitrage (mean reversion)
├── engine_ml.py                 # Basic ML predictions
├── engine_storage.py            # In-memory tick storage
│
├── engine_cross_triangular.py   # Cross-exchange triangular
├── engine_futures_spot.py       # Futures-spot basis arbitrage
├── engine_dex_cex.py            # DEX/CEX arbitrage
├── engine_latency.py            # Latency arbitrage
│
├── engine_execution.py          # Execution simulation
├── engine_timescale.py          # TimescaleDB integration
├── engine_replay.py             # Historical replay
├── engine_metrics.py            # Prometheus metrics
├── engine_ml_advanced.py        # Advanced ML with ONNX
│
├── dashboard.py                 # Main dashboard (FastAPI + WebSocket)
├── dashboard_advanced.py        # Advanced visualizations
│
├── exchanges/                   # Exchange connectors
│   ├── __init__.py
│   ├── base.py                  # Base exchange class
│   ├── binance.py
│   ├── bybit.py
│   ├── coinbase.py
│   ├── kraken.py
│   ├── okx.py
│   ├── simulator.py             # Mock exchange for testing
│   └── cpp_bridge.py            # C++ engine bridge
│
└── cpp/                         # High-performance C++ engine
    ├── CMakeLists.txt
    ├── src/
    └── include/
```

## 🛠 Installation

### Basic Setup

```bash
# Clone the repository
git clone <repository-url>
cd crypto-arbitrage-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Optional: TimescaleDB Setup

```bash
# Install TimescaleDB (using Docker)
docker run -d --name timescaledb \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=password \
    timescale/timescaledb:latest-pg15

# Create database
docker exec -it timescaledb psql -U postgres -c "CREATE DATABASE arbitrage;"
```

### Optional: C++ Engine Setup

```bash
cd cpp
mkdir build && cd build
cmake ..
make
./arb_bot  # Start C++ engine first
```

## 🚀 Quick Start

### Run in Simulation Mode (No API Keys Required)

```bash
# Edit config.py
MODE = "simulation"

# Start the bot
python main.py
```

### Run with Live Data

```bash
# Edit config.py
MODE = "python"  # or "cpp" for high performance

# Start the bot
python main.py
```

### Access Dashboards

- **Main Dashboard**: http://localhost:8000
- **Advanced Analytics**: http://localhost:8000/advanced
- **Prometheus Metrics**: http://localhost:8000/metrics
- **API State**: http://localhost:8000/api/state

## 📊 API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main dashboard |
| `GET /advanced` | Advanced visualizations |
| `GET /metrics` | Prometheus metrics |
| `GET /api/state` | Full system state |
| `GET /api/orderbook/{pair}` | Aggregated order book |
| `GET /api/ml/predictions` | ML predictions |
| `GET /api/ml/advanced` | Advanced ML state |
| `GET /api/ml/predict/{pair}` | Get prediction for pair |
| `GET /api/execution/stats` | Execution statistics |
| `GET /api/cross-triangular` | Cross-exchange opportunities |
| `GET /api/futures-spot` | Futures-spot opportunities |
| `GET /api/dex-cex` | DEX/CEX opportunities |
| `GET /api/latency` | Latency arbitrage opportunities |
| `WS /ws` | WebSocket for real-time updates |

## 🔧 Configuration

Edit `config.py` to customize:

```python
# Operation mode
MODE = "simulation"  # "python", "cpp", "simulation"

# Trading pairs
TRADING_PAIRS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT"]

# Arbitrage thresholds
MIN_PROFIT_THRESHOLD = 0.01  # 0.01% minimum
TRIANGULAR_MIN_PROFIT_THRESHOLD = 0.1  # 0.1% for triangular

# Enable/disable features
ENABLE_TRIANGULAR_ARBITRAGE = True
```

## 📈 Grafana Dashboard

Import the Grafana dashboard from `engine_metrics.py`:

```python
from engine_metrics import get_grafana_dashboard_json
dashboard = get_grafana_dashboard_json()
```

Key panels:
- Price update rates per exchange
- Feed latency percentiles (p95, p99)
- Opportunities detected per strategy
- ML prediction latency
- System memory usage

## 🧪 Testing with Replay

```python
from engine_replay import ReplayEngine, ReplayConfig
from engine_storage import TickStorage

# Create replay engine
storage = TickStorage()
replay = ReplayEngine(storage)

# Configure replay
config = ReplayConfig(
    speed=100,  # 100x speed
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 2)
)

# Run replay with callbacks
session = replay.create_session("backtest", config)
session.on_opportunity(lambda opp: print(f"Found: {opp}"))
await session.play()

print(session.stats.to_dict())
```

## 🤖 ML Model Training (Advanced)

The system uses rule-based prediction by default. To use trained models:

1. Export historical data to train on
2. Train LSTM/Transformer model
3. Export to ONNX format
4. Configure model path in `AdvancedMLEngine`

```python
engine = AdvancedMLEngine(model_path="models/predictor.onnx")
```

## 📝 Arbitrage Strategies

### 1. Simple Cross-Exchange
```
Buy BTC @ $65,000 on Binance
Sell BTC @ $65,100 on Coinbase
Profit: 0.15% - fees
```

### 2. Triangular (Single Exchange)
```
USDT → BTC → ETH → USDT
Start: $10,000
End: $10,050
Profit: 0.5% - fees (3 trades)
```

### 3. Cross-Exchange Triangular
```
Buy BTC @ Binance
Transfer to Kraken
Buy ETH @ Kraken
Transfer to Coinbase
Sell ETH @ Coinbase
```

### 4. Futures-Spot Basis
```
When funding rate is 0.03% (high):
- Short BTC-PERP on Binance
- Long BTC spot on Binance
- Collect funding every 8 hours
Annualized: ~32%
```

### 5. DEX/CEX Arbitrage
```
Uniswap ETH/USDC: $3,150
Binance ETH/USDT: $3,155
Buy DEX, Sell CEX
Profit: 0.16% - gas - fees
```

### 6. Latency Arbitrage
```
When Kraken feed is 500ms stale:
- Binance shows $65,100 (fresh)
- Kraken shows $65,000 (stale)
- Buy on Kraken before it updates
```

## 🔒 Security Notes

- **Never commit API keys** - Use environment variables
- **Test in simulation mode first**
- **Start with small amounts** when live trading
- **Monitor execution slippage** closely
- **Be aware of exchange rate limits**

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Submit pull request

## 🆘 Support

- Open an issue for bugs
- Discussions for questions
- PRs welcome!
