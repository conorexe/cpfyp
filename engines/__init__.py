"""
Arbitrage Engines Package

This package contains all the arbitrage detection and analysis engines:

Core Engines:
- ArbitrageEngine: Simple cross-exchange arbitrage
- TriangularArbitrageEngine: Single-exchange triangular paths
- OrderBookAggregator: Cross-exchange order book aggregation
- StatisticalArbitrageEngine: Mean-reversion pair trading

Advanced Arbitrage:
- CrossExchangeTriangularEngine: Multi-exchange triangular paths
- FuturesSpotBasisEngine: Futures-spot funding rate arbitrage
- DexCexArbitrageEngine: DEX/CEX price arbitrage
- LatencyArbitrageEngine: Stale quote exploitation

ML & Analytics:
- MLEngine: Basic ML predictions and regime detection
- AdvancedMLEngine: LSTM/Transformer with ONNX runtime
- ExecutionSimulator: Realistic slippage and fee modeling

Data & Monitoring:
- TickStorage: In-memory tick storage
- TimescaleDBStorage: PostgreSQL/TimescaleDB integration
- ReplayEngine: Historical data replay
- MetricsEngine: Prometheus metrics export
"""

# Re-export all engines for clean imports
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import ArbitrageEngine, ArbitrageOpportunity
from engine_triangular import TriangularArbitrageEngine, TriangularOpportunity
from engine_orderbook import OrderBookAggregator, AggregatedOrderBook
from engine_statistical import StatisticalArbitrageEngine, StatArbSignal
from engine_ml import MLEngine, Prediction, MarketRegime, Anomaly
from engine_storage import TickStorage, Tick, OHLCV, ReplayEngine as BasicReplayEngine

from engine_cross_triangular import CrossExchangeTriangularEngine, CrossExchangeOpportunity
from engine_futures_spot import FuturesSpotBasisEngine, FuturesSpotOpportunity
from engine_dex_cex import DexCexArbitrageEngine, DexCexOpportunity
from engine_latency import LatencyArbitrageEngine, LatencyOpportunity

from engine_execution import ExecutionSimulator, SlippageModel, ArbitrageExecutionPlan
from engine_metrics import MetricsEngine, metrics_engine
from engine_ml_advanced import AdvancedMLEngine, AdvancedFeatures, PredictionResult
from engine_timescale import TimescaleDBStorage, InMemoryFallback, create_tick_storage
from engine_replay import ReplayEngine, ReplaySession, ReplayConfig

__all__ = [
    # Core engines
    'ArbitrageEngine',
    'TriangularArbitrageEngine',
    'OrderBookAggregator',
    'StatisticalArbitrageEngine',
    'MLEngine',
    'TickStorage',
    
    # Advanced arbitrage
    'CrossExchangeTriangularEngine',
    'FuturesSpotBasisEngine',
    'DexCexArbitrageEngine',
    'LatencyArbitrageEngine',
    
    # Phase 1-3 engines
    'ExecutionSimulator',
    'MetricsEngine',
    'AdvancedMLEngine',
    'TimescaleDBStorage',
    'ReplayEngine',
    
    # Data classes
    'ArbitrageOpportunity',
    'TriangularOpportunity',
    'CrossExchangeOpportunity',
    'FuturesSpotOpportunity',
    'DexCexOpportunity',
    'LatencyOpportunity',
    'StatArbSignal',
    'Prediction',
    'PredictionResult',
    'AdvancedFeatures',
    'Tick',
    'OHLCV',
    'AggregatedOrderBook',
    'MarketRegime',
    'Anomaly',
    
    # Utilities
    'SlippageModel',
    'ArbitrageExecutionPlan',
    'ReplaySession',
    'ReplayConfig',
    'metrics_engine',
    'create_tick_storage',
]
