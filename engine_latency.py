"""
Latency Arbitrage Engine

Detects and exploits price discrepancies caused by slow exchange price feeds.

Strategy:
1. Monitor price update frequencies and latencies across exchanges
2. When one exchange's feed is stale (slow to update):
   - Use faster exchanges as the "true" price signal
   - Trade against stale quotes before they update
3. Profit from the information asymmetry

Key metrics:
- Feed latency (time between updates)
- Price staleness (age of last quote)
- Update frequency deviation
- Cross-exchange price correlation

Risk factors:
- Exchange may reject stale quotes
- API rate limits
- Order execution latency
- Quote validity windows
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict, deque
import math
import statistics

logger = logging.getLogger(__name__)


@dataclass
class ExchangeFeedMetrics:
    """Metrics for an exchange's price feed quality"""
    exchange: str
    pair: str
    avg_latency_ms: float
    update_frequency_hz: float  # Updates per second
    staleness_score: float  # 0-1, higher = more stale
    last_update: datetime
    price: float
    is_stale: bool
    stale_duration_ms: int
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "pair": self.pair,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "update_frequency_hz": round(self.update_frequency_hz, 3),
            "staleness_score": round(self.staleness_score, 3),
            "last_update": self.last_update.isoformat(),
            "price": round(self.price, 4),
            "is_stale": self.is_stale,
            "stale_duration_ms": self.stale_duration_ms,
        }


@dataclass
class FeedLatencyHistory:
    """Rolling history of feed update timestamps"""
    max_size: int = 200
    timestamps: deque = field(default_factory=lambda: deque(maxlen=200))
    prices: deque = field(default_factory=lambda: deque(maxlen=200))
    latencies: deque = field(default_factory=lambda: deque(maxlen=200))
    
    def add(self, price: float, timestamp: datetime):
        if self.timestamps:
            latency = (timestamp - self.timestamps[-1]).total_seconds() * 1000
            self.latencies.append(latency)
        self.timestamps.append(timestamp)
        self.prices.append(price)
    
    def avg_latency_ms(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)
    
    def update_frequency_hz(self) -> float:
        if len(self.timestamps) < 2:
            return 0.0
        
        time_span = (self.timestamps[-1] - self.timestamps[0]).total_seconds()
        if time_span == 0:
            return 0.0
        
        return (len(self.timestamps) - 1) / time_span
    
    def latency_std(self) -> float:
        if len(self.latencies) < 2:
            return 0.0
        return statistics.stdev(self.latencies)
    
    def time_since_last_update_ms(self) -> int:
        if not self.timestamps:
            return 0
        return int((datetime.now() - self.timestamps[-1]).total_seconds() * 1000)
    
    def is_stale(self, threshold_ms: int = 1000) -> bool:
        return self.time_since_last_update_ms() > threshold_ms


@dataclass
class LatencyOpportunity:
    """Represents a latency arbitrage opportunity"""
    stale_exchange: str
    fast_exchange: str
    pair: str
    stale_price: float
    fast_price: float  # More recent/accurate price
    predicted_move: float  # Expected price movement on stale exchange
    predicted_move_percent: float
    staleness_ms: int
    confidence: float
    direction: str  # "long" or "short"
    time_window_ms: int  # Estimated time window for opportunity
    risk_score: float
    feed_metrics: Dict[str, ExchangeFeedMetrics]
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "type": "latency_arbitrage",
            "stale_exchange": self.stale_exchange,
            "fast_exchange": self.fast_exchange,
            "pair": self.pair,
            "stale_price": round(self.stale_price, 4),
            "fast_price": round(self.fast_price, 4),
            "predicted_move": round(self.predicted_move, 4),
            "predicted_move_percent": round(self.predicted_move_percent, 4),
            "staleness_ms": self.staleness_ms,
            "confidence": round(self.confidence, 2),
            "direction": self.direction,
            "action": self._get_action(),
            "time_window_ms": self.time_window_ms,
            "risk_score": round(self.risk_score, 2),
            "feed_metrics": {ex: m.to_dict() for ex, m in self.feed_metrics.items()},
            "timestamp": self.timestamp.isoformat(),
        }
    
    def _get_action(self) -> str:
        if self.direction == "long":
            return f"BUY on {self.stale_exchange} (stale at ${self.stale_price:.2f}, expect ${self.fast_price:.2f})"
        else:
            return f"SELL on {self.stale_exchange} (stale at ${self.stale_price:.2f}, expect ${self.fast_price:.2f})"


class LatencyArbitrageEngine:
    """
    Detects latency arbitrage opportunities from slow exchange feeds.
    
    How it works:
    1. Track update frequency and latency for each exchange
    2. Identify when one exchange's feed becomes stale
    3. Use consensus price from faster exchanges as true price
    4. Calculate expected profit from trading against stale quote
    
    Real-world considerations:
    - HFT firms use co-location for microsecond advantages
    - This engine works at millisecond level (more accessible)
    - Exchange APIs have varying latencies
    - Order execution speed is critical
    """
    
    # Staleness thresholds per exchange (ms)
    # Lower = exchange usually updates faster, so staleness is more notable
    STALENESS_THRESHOLDS = {
        "Binance": 500,    # Binance is usually very fast
        "Bybit": 500,
        "OKX": 500,
        "Kraken": 1000,    # Kraken can be slower
        "Coinbase": 1000,
    }
    
    # Minimum exchanges needed for consensus price
    MIN_CONSENSUS_EXCHANGES = 2
    
    def __init__(
        self,
        min_staleness_ms: int = 500,
        min_price_diff_percent: float = 0.05,  # 0.05% minimum
        max_time_window_ms: int = 2000,
    ):
        self.min_staleness_ms = min_staleness_ms
        self.min_price_diff_percent = min_price_diff_percent
        self.max_time_window_ms = max_time_window_ms
        
        # Feed histories: (exchange, pair) -> FeedLatencyHistory
        self.feed_histories: Dict[Tuple[str, str], FeedLatencyHistory] = defaultdict(FeedLatencyHistory)
        
        # Current prices: exchange -> pair -> (bid, ask, timestamp)
        self.prices: Dict[str, Dict[str, Tuple[float, float, datetime]]] = defaultdict(dict)
        
        # Current opportunities
        self.opportunities: List[LatencyOpportunity] = []
        
        # History
        self.history: List[LatencyOpportunity] = []
        
        # Feed metrics cache
        self.feed_metrics: Dict[Tuple[str, str], ExchangeFeedMetrics] = {}
        
        # Callbacks
        self._on_opportunity_callbacks: List = []
    
    def on_opportunity(self, callback):
        """Register callback for new opportunities"""
        self._on_opportunity_callbacks.append(callback)
    
    def update_price(self, exchange: str, pair: str, bid: float, ask: float):
        """Update price and analyze for latency opportunities"""
        now = datetime.now()
        mid_price = (bid + ask) / 2
        
        # Store price
        self.prices[exchange][pair] = (bid, ask, now)
        
        # Update feed history
        key = (exchange, pair)
        self.feed_histories[key].add(mid_price, now)
        
        # Update feed metrics
        self._update_feed_metrics(exchange, pair)
        
        # Check for latency opportunities
        self._check_latency_opportunities(pair)
    
    def _update_feed_metrics(self, exchange: str, pair: str):
        """Update feed quality metrics for an exchange/pair"""
        key = (exchange, pair)
        history = self.feed_histories[key]
        
        if len(history.timestamps) < 10:
            return
        
        avg_latency = history.avg_latency_ms()
        update_freq = history.update_frequency_hz()
        staleness_ms = history.time_since_last_update_ms()
        threshold = self.STALENESS_THRESHOLDS.get(exchange, 1000)
        
        # Calculate staleness score (0-1)
        staleness_score = min(1.0, staleness_ms / (threshold * 2))
        
        is_stale = staleness_ms > threshold
        
        current_price = history.prices[-1] if history.prices else 0
        
        metrics = ExchangeFeedMetrics(
            exchange=exchange,
            pair=pair,
            avg_latency_ms=avg_latency,
            update_frequency_hz=update_freq,
            staleness_score=staleness_score,
            last_update=history.timestamps[-1] if history.timestamps else now,
            price=current_price,
            is_stale=is_stale,
            stale_duration_ms=staleness_ms if is_stale else 0
        )
        
        self.feed_metrics[key] = metrics
    
    def _check_latency_opportunities(self, pair: str):
        """Check for latency arbitrage opportunities on a pair"""
        # Get all exchanges with this pair
        exchanges_with_pair = [
            ex for ex in self.prices.keys()
            if pair in self.prices[ex]
        ]
        
        if len(exchanges_with_pair) < self.MIN_CONSENSUS_EXCHANGES:
            return
        
        # Calculate feed metrics for each exchange
        exchange_metrics = {}
        for ex in exchanges_with_pair:
            key = (ex, pair)
            if key in self.feed_metrics:
                exchange_metrics[ex] = self.feed_metrics[key]
        
        if len(exchange_metrics) < 2:
            return
        
        # Find stale exchanges
        stale_exchanges = [
            ex for ex, m in exchange_metrics.items()
            if m.is_stale or m.stale_duration_ms > self.min_staleness_ms
        ]
        
        # Find fast exchanges (for consensus price)
        fast_exchanges = [
            ex for ex, m in exchange_metrics.items()
            if not m.is_stale and m.stale_duration_ms < self.min_staleness_ms
        ]
        
        if not stale_exchanges or not fast_exchanges:
            return
        
        # Calculate consensus price from fast exchanges
        fast_prices = [exchange_metrics[ex].price for ex in fast_exchanges]
        consensus_price = sum(fast_prices) / len(fast_prices)
        
        new_opportunities = []
        
        for stale_ex in stale_exchanges:
            stale_metrics = exchange_metrics[stale_ex]
            stale_price = stale_metrics.price
            
            # Calculate price discrepancy
            price_diff = consensus_price - stale_price
            price_diff_percent = (price_diff / stale_price) * 100
            
            if abs(price_diff_percent) < self.min_price_diff_percent:
                continue
            
            # Determine direction
            direction = "long" if price_diff > 0 else "short"
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                stale_metrics,
                fast_exchanges,
                exchange_metrics,
                price_diff_percent
            )
            
            # Estimate time window
            time_window = self._estimate_time_window(stale_metrics)
            
            if time_window > self.max_time_window_ms:
                continue
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(
                stale_metrics, time_window, price_diff_percent
            )
            
            # Choose best fast exchange as reference
            best_fast_ex = min(fast_exchanges, key=lambda x: exchange_metrics[x].staleness_score)
            
            opportunity = LatencyOpportunity(
                stale_exchange=stale_ex,
                fast_exchange=best_fast_ex,
                pair=pair,
                stale_price=stale_price,
                fast_price=consensus_price,
                predicted_move=price_diff,
                predicted_move_percent=price_diff_percent,
                staleness_ms=stale_metrics.stale_duration_ms,
                confidence=confidence,
                direction=direction,
                time_window_ms=time_window,
                risk_score=risk_score,
                feed_metrics={ex: m for ex, m in exchange_metrics.items()},
                timestamp=datetime.now()
            )
            
            new_opportunities.append(opportunity)
        
        # Update opportunities
        if new_opportunities:
            # Remove old opportunities for this pair
            self.opportunities = [o for o in self.opportunities if o.pair != pair]
            self.opportunities.extend(new_opportunities)
            self.opportunities.sort(key=lambda x: abs(x.predicted_move_percent), reverse=True)
            
            # Log significant opportunities
            for opp in new_opportunities:
                if abs(opp.predicted_move_percent) >= 0.1:
                    logger.info(
                        f"⚡ LATENCY ARB: {opp.pair} | "
                        f"{opp.stale_exchange} stale by {opp.staleness_ms}ms | "
                        f"{opp.direction.upper()} | "
                        f"Expected move: {opp.predicted_move_percent:.3f}% | "
                        f"Window: {opp.time_window_ms}ms"
                    )
            
            # Add to history
            for opp in new_opportunities:
                self.history.append(opp)
            if len(self.history) > 100:
                self.history = self.history[-100:]
            
            # Notify listeners
            for opp in new_opportunities:
                for callback in self._on_opportunity_callbacks:
                    try:
                        callback(opp)
                    except Exception as e:
                        logger.error(f"Latency arb callback error: {e}")
    
    def _calculate_confidence(
        self,
        stale_metrics: ExchangeFeedMetrics,
        fast_exchanges: List[str],
        all_metrics: Dict[str, ExchangeFeedMetrics],
        price_diff_percent: float
    ) -> float:
        """Calculate confidence in the latency opportunity"""
        # More fast exchanges = higher confidence in consensus price
        consensus_factor = min(1.0, len(fast_exchanges) / 3)
        
        # Larger price diff = higher confidence (but cap it)
        diff_factor = min(1.0, abs(price_diff_percent) / 0.5)
        
        # Clearer staleness = higher confidence
        staleness_factor = min(1.0, stale_metrics.stale_duration_ms / 2000)
        
        # Fast exchanges agree = higher confidence
        fast_prices = [all_metrics[ex].price for ex in fast_exchanges]
        if len(fast_prices) > 1:
            price_std = statistics.stdev(fast_prices)
            mean_price = statistics.mean(fast_prices)
            agreement_factor = 1.0 - min(1.0, (price_std / mean_price) * 100)
        else:
            agreement_factor = 0.5
        
        confidence = (
            0.25 * consensus_factor +
            0.25 * diff_factor +
            0.25 * staleness_factor +
            0.25 * agreement_factor
        )
        
        return max(0.0, min(1.0, confidence))
    
    def _estimate_time_window(self, stale_metrics: ExchangeFeedMetrics) -> int:
        """Estimate how long the opportunity window will last"""
        # Based on average update frequency
        if stale_metrics.update_frequency_hz > 0:
            expected_update_ms = 1000 / stale_metrics.update_frequency_hz
        else:
            expected_update_ms = 1000
        
        # Already stale for some time, estimate remaining window
        time_stale = stale_metrics.stale_duration_ms
        remaining = max(0, expected_update_ms * 1.5 - time_stale)
        
        return int(remaining)
    
    def _calculate_risk_score(
        self,
        stale_metrics: ExchangeFeedMetrics,
        time_window: int,
        price_diff_percent: float
    ) -> float:
        """Calculate risk score (0-1, higher = riskier)"""
        # Shorter time window = higher risk
        time_risk = 1.0 - min(1.0, time_window / 1000)
        
        # Very large price diff might be data error
        if abs(price_diff_percent) > 0.5:
            diff_risk = 0.8
        elif abs(price_diff_percent) > 0.2:
            diff_risk = 0.4
        else:
            diff_risk = 0.1
        
        # Exchange with highly variable latency = higher risk
        if stale_metrics.avg_latency_ms > 500:
            latency_risk = 0.6
        elif stale_metrics.avg_latency_ms > 200:
            latency_risk = 0.3
        else:
            latency_risk = 0.1
        
        risk_score = 0.4 * time_risk + 0.3 * diff_risk + 0.3 * latency_risk
        
        return max(0.0, min(1.0, risk_score))
    
    def get_feed_health(self) -> Dict[str, Dict[str, dict]]:
        """Get health status of all exchange feeds"""
        health = defaultdict(dict)
        
        for (exchange, pair), metrics in self.feed_metrics.items():
            health[exchange][pair] = metrics.to_dict()
        
        return dict(health)
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        # Calculate aggregate stats
        stale_feeds = [
            m for m in self.feed_metrics.values()
            if m.is_stale
        ]
        
        return {
            "latency_opportunities": [o.to_dict() for o in self.opportunities[:10]],
            "latency_history": [o.to_dict() for o in self.history[-20:]],
            "feed_health": self.get_feed_health(),
            "stale_feed_count": len(stale_feeds),
            "total_feeds_monitored": len(self.feed_metrics),
            "exchanges_monitored": list(set(m.exchange for m in self.feed_metrics.values())),
            "config": {
                "min_staleness_ms": self.min_staleness_ms,
                "min_price_diff_percent": self.min_price_diff_percent,
                "max_time_window_ms": self.max_time_window_ms,
            }
        }
