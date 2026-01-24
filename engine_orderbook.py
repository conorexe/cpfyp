"""
Order Book Aggregation Engine

Provides L2/L3 order book depth across multiple exchanges,
enabling advanced arbitrage strategies and liquidity analysis.

Features:
- Aggregated best bid/ask across all exchanges
- Full depth visualization (top 20 levels)
- Liquidity imbalance detection
- Spread analysis
- Order flow metrics
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import heapq

logger = logging.getLogger(__name__)


@dataclass
class OrderBookLevel:
    """Single price level in order book"""
    price: float
    quantity: float
    exchange: str
    timestamp: datetime


@dataclass
class AggregatedOrderBook:
    """Aggregated order book across exchanges for a trading pair"""
    pair: str
    bids: List[OrderBookLevel]  # Sorted by price descending (best first)
    asks: List[OrderBookLevel]  # Sorted by price ascending (best first)
    timestamp: datetime
    
    @property
    def best_bid(self) -> Optional[OrderBookLevel]:
        return self.bids[0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[OrderBookLevel]:
        return self.asks[0] if self.asks else None
    
    @property
    def spread(self) -> float:
        if self.best_bid and self.best_ask:
            return self.best_ask.price - self.best_bid.price
        return 0.0
    
    @property
    def spread_percent(self) -> float:
        if self.best_bid and self.best_ask:
            mid = (self.best_bid.price + self.best_ask.price) / 2
            return (self.spread / mid) * 100 if mid > 0 else 0.0
        return 0.0
    
    @property
    def bid_depth(self) -> float:
        """Total bid liquidity in base currency"""
        return sum(level.quantity for level in self.bids)
    
    @property
    def ask_depth(self) -> float:
        """Total ask liquidity in base currency"""
        return sum(level.quantity for level in self.asks)
    
    @property
    def imbalance(self) -> float:
        """
        Order book imbalance: positive = more bids (bullish), negative = more asks (bearish)
        Range: -1 to +1
        """
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return 0.0
        return (self.bid_depth - self.ask_depth) / total
    
    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "best_bid": {"price": self.best_bid.price, "quantity": self.best_bid.quantity, "exchange": self.best_bid.exchange} if self.best_bid else None,
            "best_ask": {"price": self.best_ask.price, "quantity": self.best_ask.quantity, "exchange": self.best_ask.exchange} if self.best_ask else None,
            "spread": round(self.spread, 8),
            "spread_percent": round(self.spread_percent, 4),
            "bid_depth": round(self.bid_depth, 4),
            "ask_depth": round(self.ask_depth, 4),
            "imbalance": round(self.imbalance, 4),
            "bids": [{"price": l.price, "quantity": l.quantity, "exchange": l.exchange} for l in self.bids[:10]],
            "asks": [{"price": l.price, "quantity": l.quantity, "exchange": l.exchange} for l in self.asks[:10]],
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExchangeMetrics:
    """Performance metrics for an exchange feed"""
    exchange: str
    last_update: datetime
    updates_per_second: float = 0.0
    avg_latency_ms: float = 0.0
    stale_count: int = 0
    error_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "last_update": self.last_update.isoformat(),
            "updates_per_second": round(self.updates_per_second, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "stale_count": self.stale_count,
            "error_count": self.error_count,
            "status": self._get_status(),
        }
    
    def _get_status(self) -> str:
        age = (datetime.now() - self.last_update).total_seconds()
        if age > 5:
            return "stale"
        if self.error_count > 10:
            return "degraded"
        return "healthy"


class OrderBookAggregator:
    """
    Aggregates order book data from multiple exchanges.
    
    Features:
    - Maintains top N levels per exchange
    - Provides unified view across all venues
    - Tracks liquidity and imbalance
    - Monitors exchange feed health
    """
    
    def __init__(self, max_levels: int = 20):
        self.max_levels = max_levels
        
        # Order books: pair -> exchange -> (bids, asks)
        # bids: list of (price, quantity) sorted by price descending
        # asks: list of (price, quantity) sorted by price ascending
        self._books: Dict[str, Dict[str, Tuple[List, List]]] = defaultdict(dict)
        
        # Exchange metrics
        self._metrics: Dict[str, ExchangeMetrics] = {}
        self._update_counts: Dict[str, List[datetime]] = defaultdict(list)
        
        # Callbacks
        self._on_book_update_callbacks: List = []
    
    def on_book_update(self, callback):
        """Register callback for order book updates"""
        self._on_book_update_callbacks.append(callback)
    
    def update_book(
        self, 
        exchange: str, 
        pair: str, 
        bid: float, 
        ask: float,
        bid_quantity: float = 1.0,
        ask_quantity: float = 1.0,
        timestamp: Optional[datetime] = None
    ):
        """
        Update order book from a price feed.
        
        For simulation, we create synthetic depth from bid/ask prices.
        In production, this would receive full L2 data.
        """
        timestamp = timestamp or datetime.now()
        
        # Generate synthetic depth levels (simulated)
        bids = self._generate_depth_levels(bid, bid_quantity, side='bid')
        asks = self._generate_depth_levels(ask, ask_quantity, side='ask')
        
        # Store in books
        self._books[pair][exchange] = (bids, asks)
        
        # Update metrics
        self._update_metrics(exchange, timestamp)
        
        # Notify listeners
        aggregated = self.get_aggregated_book(pair)
        for callback in self._on_book_update_callbacks:
            try:
                callback(aggregated)
            except Exception as e:
                logger.error(f"Order book callback error: {e}")
    
    def _generate_depth_levels(
        self, 
        best_price: float, 
        base_quantity: float,
        side: str,
        levels: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Generate synthetic order book depth.
        
        In production, this would come from actual L2 feeds.
        For simulation, we create realistic-looking depth.
        """
        result = []
        spread_increment = best_price * 0.0001  # 0.01% per level
        
        for i in range(levels):
            if side == 'bid':
                price = best_price - (i * spread_increment)
            else:
                price = best_price + (i * spread_increment)
            
            # Quantity increases at worse prices (realistic market microstructure)
            quantity = base_quantity * (1 + i * 0.5)
            result.append((price, quantity))
        
        return result
    
    def _update_metrics(self, exchange: str, timestamp: datetime):
        """Update exchange performance metrics"""
        if exchange not in self._metrics:
            self._metrics[exchange] = ExchangeMetrics(
                exchange=exchange,
                last_update=timestamp
            )
        
        metrics = self._metrics[exchange]
        metrics.last_update = timestamp
        
        # Calculate updates per second
        self._update_counts[exchange].append(timestamp)
        # Keep only last 10 seconds of updates
        cutoff = timestamp.timestamp() - 10
        self._update_counts[exchange] = [
            t for t in self._update_counts[exchange]
            if t.timestamp() > cutoff
        ]
        metrics.updates_per_second = len(self._update_counts[exchange]) / 10
    
    def get_aggregated_book(self, pair: str) -> AggregatedOrderBook:
        """
        Get aggregated order book across all exchanges for a pair.
        
        Bids sorted by price descending (best bid first).
        Asks sorted by price ascending (best ask first).
        """
        all_bids: List[OrderBookLevel] = []
        all_asks: List[OrderBookLevel] = []
        
        if pair not in self._books:
            return AggregatedOrderBook(
                pair=pair,
                bids=[],
                asks=[],
                timestamp=datetime.now()
            )
        
        for exchange, (bids, asks) in self._books[pair].items():
            timestamp = self._metrics.get(exchange, ExchangeMetrics(exchange, datetime.now())).last_update
            
            for price, quantity in bids:
                all_bids.append(OrderBookLevel(price, quantity, exchange, timestamp))
            
            for price, quantity in asks:
                all_asks.append(OrderBookLevel(price, quantity, exchange, timestamp))
        
        # Sort: bids descending by price, asks ascending by price
        all_bids.sort(key=lambda x: x.price, reverse=True)
        all_asks.sort(key=lambda x: x.price)
        
        # Trim to max levels
        all_bids = all_bids[:self.max_levels]
        all_asks = all_asks[:self.max_levels]
        
        return AggregatedOrderBook(
            pair=pair,
            bids=all_bids,
            asks=all_asks,
            timestamp=datetime.now()
        )
    
    def get_cross_exchange_spread(self, pair: str) -> Optional[Dict]:
        """
        Find best bid/ask across different exchanges.
        
        Returns arbitrage opportunity if best bid on one exchange
        is higher than best ask on another.
        """
        if pair not in self._books or len(self._books[pair]) < 2:
            return None
        
        best_bids = []  # (price, exchange)
        best_asks = []  # (price, exchange)
        
        for exchange, (bids, asks) in self._books[pair].items():
            if bids:
                best_bids.append((bids[0][0], exchange))
            if asks:
                best_asks.append((asks[0][0], exchange))
        
        if not best_bids or not best_asks:
            return None
        
        # Find best bid (highest) and best ask (lowest) across exchanges
        best_bid = max(best_bids, key=lambda x: x[0])
        best_ask = min(best_asks, key=lambda x: x[0])
        
        # Calculate potential profit
        profit_amount = best_bid[0] - best_ask[0]
        profit_percent = (profit_amount / best_ask[0]) * 100 if best_ask[0] > 0 else 0
        
        return {
            "pair": pair,
            "buy_exchange": best_ask[1],
            "buy_price": best_ask[0],
            "sell_exchange": best_bid[1],
            "sell_price": best_bid[0],
            "profit_amount": profit_amount,
            "profit_percent": profit_percent,
            "is_profitable": profit_percent > 0,
        }
    
    def get_all_metrics(self) -> Dict[str, dict]:
        """Get metrics for all exchanges"""
        return {
            exchange: metrics.to_dict()
            for exchange, metrics in self._metrics.items()
        }
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        pairs = list(self._books.keys())
        
        return {
            "order_books": {
                pair: self.get_aggregated_book(pair).to_dict()
                for pair in pairs[:10]  # Limit for performance
            },
            "exchange_metrics": self.get_all_metrics(),
            "cross_exchange_spreads": {
                pair: self.get_cross_exchange_spread(pair)
                for pair in pairs
                if self.get_cross_exchange_spread(pair)
            },
            "total_pairs": len(pairs),
            "total_exchanges": len(self._metrics),
        }
