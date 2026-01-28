"""
Data classes for arbitrage opportunities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict


@dataclass
class ExchangePrice:
    """Current price state for a pair on an exchange"""
    exchange: str
    pair: str
    bid: float
    ask: float
    timestamp: datetime
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    
    @property
    def mid(self) -> float:
        """Mid-market price"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """Bid-ask spread"""
        return self.ask - self.bid
    
    @property
    def spread_percent(self) -> float:
        """Bid-ask spread as percentage"""
        return ((self.ask - self.bid) / self.mid) * 100
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "pair": self.pair,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread_percent": round(self.spread_percent, 4),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ArbitrageOpportunity:
    """Represents a detected cross-exchange arbitrage opportunity"""
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float  # Ask price on buy exchange
    sell_price: float  # Bid price on sell exchange
    profit_percent: float
    timestamp: datetime
    
    # Optional fields for enhanced analysis
    buy_size: Optional[float] = None
    sell_size: Optional[float] = None
    estimated_slippage: Optional[float] = None
    estimated_fees: Optional[float] = None
    net_profit_percent: Optional[float] = None
    confidence: Optional[float] = None
    
    def to_dict(self) -> dict:
        result = {
            "pair": self.pair,
            "buy_exchange": self.buy_exchange,
            "sell_exchange": self.sell_exchange,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "profit_percent": round(self.profit_percent, 4),
            "timestamp": self.timestamp.isoformat(),
        }
        
        if self.net_profit_percent is not None:
            result["net_profit_percent"] = round(self.net_profit_percent, 4)
        if self.confidence is not None:
            result["confidence"] = round(self.confidence, 4)
        if self.estimated_slippage is not None:
            result["estimated_slippage"] = round(self.estimated_slippage, 4)
        if self.estimated_fees is not None:
            result["estimated_fees"] = round(self.estimated_fees, 4)
            
        return result
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row for export"""
        return [
            self.timestamp.isoformat(),
            self.pair,
            self.buy_exchange,
            self.sell_exchange,
            str(self.buy_price),
            str(self.sell_price),
            str(round(self.profit_percent, 4)),
            str(round(self.net_profit_percent, 4)) if self.net_profit_percent else "",
            str(round(self.confidence, 4)) if self.confidence else "",
        ]
    
    @staticmethod
    def csv_headers() -> List[str]:
        """CSV headers for export"""
        return [
            "timestamp",
            "pair",
            "buy_exchange",
            "sell_exchange",
            "buy_price",
            "sell_price",
            "profit_percent",
            "net_profit_percent",
            "confidence",
        ]


@dataclass
class TriangularOpportunity:
    """Represents a triangular arbitrage opportunity within a single exchange"""
    exchange: str
    base_currency: str
    pairs: List[str]
    sides: List[str]  # 'buy' or 'sell' for each leg
    prices: Dict[str, ExchangePrice]
    profit_percent: float
    timestamp: datetime
    
    # Calculation details
    start_amount: float = 10000.0  # Starting capital in base currency
    end_amount: Optional[float] = None
    profit_amount: Optional[float] = None
    
    def __post_init__(self):
        if self.end_amount is None:
            self.end_amount = self.start_amount * (1 + self.profit_percent / 100)
        if self.profit_amount is None:
            self.profit_amount = self.end_amount - self.start_amount
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "base_currency": self.base_currency,
            "pairs": self.pairs,
            "sides": self.sides,
            "prices": {k: v.to_dict() for k, v in self.prices.items()},
            "profit_percent": round(self.profit_percent, 4),
            "start_amount": self.start_amount,
            "end_amount": round(self.end_amount, 2) if self.end_amount else None,
            "profit_amount": round(self.profit_amount, 2) if self.profit_amount else None,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row for export"""
        return [
            self.timestamp.isoformat(),
            self.exchange,
            self.base_currency,
            "->".join(self.pairs),
            "->".join(self.sides),
            str(round(self.profit_percent, 4)),
            str(round(self.start_amount, 2)),
            str(round(self.end_amount, 2)) if self.end_amount else "",
            str(round(self.profit_amount, 2)) if self.profit_amount else "",
        ]
    
    @staticmethod
    def csv_headers() -> List[str]:
        """CSV headers for export"""
        return [
            "timestamp",
            "exchange",
            "base_currency",
            "path",
            "sides",
            "profit_percent",
            "start_amount",
            "end_amount",
            "profit_amount",
        ]


@dataclass
class StatisticalArbitrageSignal:
    """Statistical arbitrage signal based on mean reversion"""
    pair_a: str
    pair_b: str
    z_score: float
    correlation: float
    signal: str  # 'long_spread', 'short_spread', 'neutral'
    confidence: float
    action: str
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "pair_a": self.pair_a,
            "pair_b": self.pair_b,
            "z_score": round(self.z_score, 4),
            "correlation": round(self.correlation, 4),
            "signal": self.signal,
            "confidence": round(self.confidence, 4),
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MLPrediction:
    """Machine learning prediction for arbitrage opportunity"""
    pair: str
    probability: float
    time_horizon_ms: int
    confidence: float
    features: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        result = {
            "pair": self.pair,
            "probability": round(self.probability, 4),
            "time_horizon_ms": self.time_horizon_ms,
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp.isoformat(),
        }
        if self.features:
            result["features"] = self.features
        return result
