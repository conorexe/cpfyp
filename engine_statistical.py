"""
Statistical Arbitrage Engine

Implements mean-reversion strategies based on:
- Pair correlation analysis
- Z-score based entry/exit signals
- Cointegration testing
- Spread analysis

This is more sophisticated than simple price arbitrage as it
uses statistical relationships rather than direct price differences.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque
import math

logger = logging.getLogger(__name__)


@dataclass
class PriceHistory:
    """Rolling window of prices for a pair/exchange"""
    max_size: int = 500  # ~5 minutes at 100ms updates
    prices: deque = field(default_factory=lambda: deque(maxlen=500))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=500))
    
    def add(self, price: float, timestamp: datetime):
        self.prices.append(price)
        self.timestamps.append(timestamp)
    
    def get_prices(self) -> List[float]:
        return list(self.prices)
    
    def mean(self) -> float:
        if not self.prices:
            return 0.0
        return sum(self.prices) / len(self.prices)
    
    def std(self) -> float:
        if len(self.prices) < 2:
            return 0.0
        mean = self.mean()
        variance = sum((p - mean) ** 2 for p in self.prices) / (len(self.prices) - 1)
        return math.sqrt(variance)
    
    def z_score(self, current_price: float) -> float:
        """Calculate z-score of current price vs historical distribution"""
        std = self.std()
        if std == 0:
            return 0.0
        return (current_price - self.mean()) / std


@dataclass
class SpreadHistory:
    """Rolling window of spread between two assets"""
    max_size: int = 500
    spreads: deque = field(default_factory=lambda: deque(maxlen=500))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=500))
    
    def add(self, spread: float, timestamp: datetime):
        self.spreads.append(spread)
        self.timestamps.append(timestamp)
    
    def mean(self) -> float:
        if not self.spreads:
            return 0.0
        return sum(self.spreads) / len(self.spreads)
    
    def std(self) -> float:
        if len(self.spreads) < 2:
            return 0.0
        mean = self.mean()
        variance = sum((s - mean) ** 2 for s in self.spreads) / (len(self.spreads) - 1)
        return math.sqrt(variance)
    
    def z_score(self) -> float:
        """Z-score of current spread"""
        if len(self.spreads) < 2:
            return 0.0
        std = self.std()
        if std == 0:
            return 0.0
        current = self.spreads[-1] if self.spreads else 0
        return (current - self.mean()) / std
    
    def half_life(self) -> Optional[float]:
        """
        Estimate half-life of mean reversion (in number of observations).
        Uses simplified Ornstein-Uhlenbeck estimation.
        """
        if len(self.spreads) < 50:
            return None
        
        spreads = list(self.spreads)
        mean = self.mean()
        
        # Calculate mean reversion coefficient
        demeaned = [s - mean for s in spreads]
        
        numerator = 0.0
        denominator = 0.0
        
        for i in range(1, len(demeaned)):
            numerator += demeaned[i] * demeaned[i-1]
            denominator += demeaned[i-1] ** 2
        
        if denominator == 0:
            return None
        
        rho = numerator / denominator
        
        if rho >= 1 or rho <= 0:
            return None
        
        # Half-life = -ln(2) / ln(rho)
        half_life = -math.log(2) / math.log(rho)
        
        return half_life if half_life > 0 else None


@dataclass
class StatArbSignal:
    """Statistical arbitrage trading signal"""
    pair_a: str  # First asset (e.g., "BTC/USDT")
    pair_b: str  # Second asset (e.g., "ETH/USDT")
    exchange: str
    signal: str  # "long_spread", "short_spread", "neutral"
    z_score: float
    spread: float
    mean_spread: float
    std_spread: float
    half_life: Optional[float]
    correlation: float
    confidence: float  # 0-1 confidence in signal
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "pair_a": self.pair_a,
            "pair_b": self.pair_b,
            "exchange": self.exchange,
            "signal": self.signal,
            "z_score": round(self.z_score, 3),
            "spread": round(self.spread, 6),
            "mean_spread": round(self.mean_spread, 6),
            "std_spread": round(self.std_spread, 6),
            "half_life": round(self.half_life, 1) if self.half_life else None,
            "correlation": round(self.correlation, 4),
            "confidence": round(self.confidence, 2),
            "timestamp": self.timestamp.isoformat(),
            "action": self._get_action(),
        }
    
    def _get_action(self) -> str:
        if self.signal == "long_spread":
            return f"BUY {self.pair_a}, SELL {self.pair_b}"
        elif self.signal == "short_spread":
            return f"SELL {self.pair_a}, BUY {self.pair_b}"
        return "Hold"


class StatisticalArbitrageEngine:
    """
    Detects statistical arbitrage opportunities using mean-reversion.
    
    Strategy:
    1. Track price ratio (spread) between correlated pairs
    2. Calculate z-score of current spread vs historical
    3. Generate signal when z-score exceeds threshold
    4. Expect spread to revert to mean
    
    Example:
    - BTC/USDT and ETH/USDT are highly correlated
    - If BTC rises faster than ETH (spread widens)
    - Z-score becomes positive (> 2)
    - Signal: Short BTC, Long ETH (expect spread to narrow)
    """
    
    def __init__(
        self,
        z_score_entry: float = 2.0,
        z_score_exit: float = 0.5,
        min_correlation: float = 0.7,
        min_history: int = 100
    ):
        """
        Args:
            z_score_entry: Z-score threshold to enter trade
            z_score_exit: Z-score threshold to exit trade
            min_correlation: Minimum correlation to consider pair
            min_history: Minimum price points before generating signals
        """
        self.z_score_entry = z_score_entry
        self.z_score_exit = z_score_exit
        self.min_correlation = min_correlation
        self.min_history = min_history
        
        # Price histories: (exchange, pair) -> PriceHistory
        self.price_history: Dict[Tuple[str, str], PriceHistory] = {}
        
        # Spread histories: (exchange, pair_a, pair_b) -> SpreadHistory
        self.spread_history: Dict[Tuple[str, str, str], SpreadHistory] = {}
        
        # Current signals
        self.signals: List[StatArbSignal] = []
        
        # Signal history
        self.signal_history: List[StatArbSignal] = []
        
        # Tracked pairs for stat arb
        self.tracked_pairs: List[Tuple[str, str]] = [
            ("BTC/USDT", "ETH/USDT"),
            ("ETH/USDT", "SOL/USDT"),
            ("BTC/USDT", "SOL/USDT"),
        ]
        
        # Callbacks
        self._on_signal_callbacks: List = []
    
    def on_signal(self, callback):
        """Register callback for new signals"""
        self._on_signal_callbacks.append(callback)
    
    def update_price(self, exchange: str, pair: str, price: float, timestamp: Optional[datetime] = None):
        """Update price and check for stat arb signals"""
        timestamp = timestamp or datetime.now()
        
        # Store price history
        key = (exchange, pair)
        if key not in self.price_history:
            self.price_history[key] = PriceHistory()
        self.price_history[key].add(price, timestamp)
        
        # Update spreads for tracked pairs
        for pair_a, pair_b in self.tracked_pairs:
            if pair in (pair_a, pair_b):
                self._update_spread(exchange, pair_a, pair_b, timestamp)
    
    def _update_spread(self, exchange: str, pair_a: str, pair_b: str, timestamp: datetime):
        """Update spread between two pairs and check for signals"""
        key_a = (exchange, pair_a)
        key_b = (exchange, pair_b)
        
        # Need history for both pairs
        if key_a not in self.price_history or key_b not in self.price_history:
            return
        
        hist_a = self.price_history[key_a]
        hist_b = self.price_history[key_b]
        
        # Need enough data
        if len(hist_a.prices) < self.min_history or len(hist_b.prices) < self.min_history:
            return
        
        # Calculate current spread (price ratio)
        price_a = hist_a.prices[-1]
        price_b = hist_b.prices[-1]
        
        if price_b == 0:
            return
        
        spread = price_a / price_b
        
        # Store spread history
        spread_key = (exchange, pair_a, pair_b)
        if spread_key not in self.spread_history:
            self.spread_history[spread_key] = SpreadHistory()
        self.spread_history[spread_key].add(spread, timestamp)
        
        # Calculate correlation
        correlation = self._calculate_correlation(hist_a, hist_b)
        
        # Only proceed if highly correlated
        if correlation < self.min_correlation:
            return
        
        spread_hist = self.spread_history[spread_key]
        
        # Need enough spread history
        if len(spread_hist.spreads) < self.min_history:
            return
        
        # Calculate z-score
        z_score = spread_hist.z_score()
        
        # Determine signal
        signal = self._determine_signal(z_score)
        
        # Calculate confidence based on half-life and z-score magnitude
        half_life = spread_hist.half_life()
        confidence = self._calculate_confidence(z_score, half_life, correlation)
        
        # Only emit signal if entry threshold exceeded
        if abs(z_score) >= self.z_score_entry:
            stat_signal = StatArbSignal(
                pair_a=pair_a,
                pair_b=pair_b,
                exchange=exchange,
                signal=signal,
                z_score=z_score,
                spread=spread,
                mean_spread=spread_hist.mean(),
                std_spread=spread_hist.std(),
                half_life=half_life,
                correlation=correlation,
                confidence=confidence,
                timestamp=timestamp
            )
            
            # Update current signals
            self.signals = [s for s in self.signals if not (
                s.pair_a == pair_a and s.pair_b == pair_b and s.exchange == exchange
            )]
            self.signals.append(stat_signal)
            
            # Add to history
            self.signal_history.append(stat_signal)
            if len(self.signal_history) > 100:
                self.signal_history.pop(0)
            
            # Notify listeners
            logger.info(
                f"📊 STAT ARB: {exchange} | {pair_a}/{pair_b} | "
                f"Z={z_score:.2f} | Signal: {signal} | Confidence: {confidence:.0%}"
            )
            
            for callback in self._on_signal_callbacks:
                try:
                    callback(stat_signal)
                except Exception as e:
                    logger.error(f"Stat arb callback error: {e}")
    
    def _calculate_correlation(self, hist_a: PriceHistory, hist_b: PriceHistory) -> float:
        """Calculate Pearson correlation between two price series"""
        prices_a = hist_a.get_prices()
        prices_b = hist_b.get_prices()
        
        # Use same length
        n = min(len(prices_a), len(prices_b))
        if n < 10:
            return 0.0
        
        prices_a = prices_a[-n:]
        prices_b = prices_b[-n:]
        
        mean_a = sum(prices_a) / n
        mean_b = sum(prices_b) / n
        
        numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(prices_a, prices_b))
        
        std_a = math.sqrt(sum((a - mean_a) ** 2 for a in prices_a))
        std_b = math.sqrt(sum((b - mean_b) ** 2 for b in prices_b))
        
        if std_a == 0 or std_b == 0:
            return 0.0
        
        return numerator / (std_a * std_b)
    
    def _determine_signal(self, z_score: float) -> str:
        """Determine signal based on z-score"""
        if z_score >= self.z_score_entry:
            return "short_spread"  # Spread is too high, expect it to narrow
        elif z_score <= -self.z_score_entry:
            return "long_spread"  # Spread is too low, expect it to widen
        else:
            return "neutral"
    
    def _calculate_confidence(
        self, 
        z_score: float, 
        half_life: Optional[float],
        correlation: float
    ) -> float:
        """
        Calculate confidence score for signal.
        
        Higher confidence with:
        - Stronger z-score (more extreme deviation)
        - Faster mean reversion (lower half-life)
        - Higher correlation
        """
        # Z-score factor (0.5-1.0 for z=2-4)
        z_factor = min(1.0, max(0.5, (abs(z_score) - self.z_score_entry) / 2 + 0.5))
        
        # Half-life factor (faster = better)
        if half_life and half_life < 50:
            hl_factor = min(1.0, 50 / max(1, half_life))
        else:
            hl_factor = 0.3
        
        # Correlation factor
        corr_factor = (correlation - self.min_correlation) / (1 - self.min_correlation)
        corr_factor = max(0, min(1, corr_factor))
        
        # Weighted average
        confidence = 0.4 * z_factor + 0.3 * hl_factor + 0.3 * corr_factor
        
        return confidence
    
    def get_pair_analysis(self, exchange: str, pair_a: str, pair_b: str) -> Optional[dict]:
        """Get detailed analysis for a pair"""
        spread_key = (exchange, pair_a, pair_b)
        
        if spread_key not in self.spread_history:
            return None
        
        spread_hist = self.spread_history[spread_key]
        
        key_a = (exchange, pair_a)
        key_b = (exchange, pair_b)
        
        if key_a not in self.price_history or key_b not in self.price_history:
            return None
        
        hist_a = self.price_history[key_a]
        hist_b = self.price_history[key_b]
        
        correlation = self._calculate_correlation(hist_a, hist_b)
        
        return {
            "pair_a": pair_a,
            "pair_b": pair_b,
            "exchange": exchange,
            "current_spread": spread_hist.spreads[-1] if spread_hist.spreads else 0,
            "mean_spread": spread_hist.mean(),
            "std_spread": spread_hist.std(),
            "z_score": spread_hist.z_score(),
            "half_life": spread_hist.half_life(),
            "correlation": correlation,
            "data_points": len(spread_hist.spreads),
            "price_a": hist_a.prices[-1] if hist_a.prices else 0,
            "price_b": hist_b.prices[-1] if hist_b.prices else 0,
        }
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "stat_arb_signals": [s.to_dict() for s in self.signals],
            "stat_arb_history": [s.to_dict() for s in self.signal_history[-20:]],
            "tracked_pairs": [
                {"pair_a": a, "pair_b": b} 
                for a, b in self.tracked_pairs
            ],
            "pair_analyses": [
                self.get_pair_analysis(exchange, pair_a, pair_b)
                for exchange in set(key[0] for key in self.spread_history.keys())
                for pair_a, pair_b in self.tracked_pairs
                if self.get_pair_analysis(exchange, pair_a, pair_b)
            ],
            "config": {
                "z_score_entry": self.z_score_entry,
                "z_score_exit": self.z_score_exit,
                "min_correlation": self.min_correlation,
                "min_history": self.min_history,
            }
        }
