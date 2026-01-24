"""
Futures-Spot Basis Arbitrage Engine

Detects arbitrage opportunities between perpetual futures and spot markets
by analyzing funding rates.

Strategy:
1. When funding rate is positive (longs pay shorts):
   - If rate is high: SHORT futures, LONG spot
   - Collect funding payments while hedged
   
2. When funding rate is negative (shorts pay longs):
   - If rate is very negative: LONG futures, SHORT spot
   - Collect funding payments while hedged

This is a "carry trade" that profits from funding rate differentials
without directional market exposure.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from collections import deque
import math

logger = logging.getLogger(__name__)


@dataclass
class FundingRateData:
    """Funding rate data for a perpetual contract"""
    exchange: str
    symbol: str
    funding_rate: float  # Current 8-hour funding rate
    predicted_rate: float  # Predicted next funding rate
    next_funding_time: datetime
    mark_price: float
    index_price: float
    timestamp: datetime
    
    def annualized_rate(self) -> float:
        """Convert 8-hour rate to annualized"""
        # 3 funding periods per day × 365 days
        return self.funding_rate * 3 * 365 * 100


@dataclass
class FundingRateHistory:
    """Rolling history of funding rates"""
    max_size: int = 100
    rates: deque = field(default_factory=lambda: deque(maxlen=100))
    timestamps: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add(self, rate: float, timestamp: datetime):
        self.rates.append(rate)
        self.timestamps.append(timestamp)
    
    def mean(self) -> float:
        if not self.rates:
            return 0.0
        return sum(self.rates) / len(self.rates)
    
    def std(self) -> float:
        if len(self.rates) < 2:
            return 0.0
        mean = self.mean()
        variance = sum((r - mean) ** 2 for r in self.rates) / (len(self.rates) - 1)
        return math.sqrt(variance)
    
    def z_score(self, current_rate: float) -> float:
        std = self.std()
        if std == 0:
            return 0.0
        return (current_rate - self.mean()) / std


@dataclass
class FuturesSpotOpportunity:
    """Represents a futures-spot basis arbitrage opportunity"""
    exchange: str
    symbol: str
    direction: str  # "cash_and_carry" (short futures) or "reverse_cash_carry" (long futures)
    spot_price: float
    futures_price: float
    basis: float  # Futures - Spot
    basis_percent: float
    funding_rate: float
    funding_rate_annualized: float
    expected_profit_8h: float  # Expected profit per 8-hour period
    expected_profit_annual: float
    z_score: float  # How unusual is this funding rate
    confidence: float
    risk_level: str  # "low", "medium", "high"
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "type": "futures_spot_basis",
            "exchange": self.exchange,
            "symbol": self.symbol,
            "direction": self.direction,
            "action": self._get_action(),
            "spot_price": round(self.spot_price, 2),
            "futures_price": round(self.futures_price, 2),
            "basis": round(self.basis, 2),
            "basis_percent": round(self.basis_percent, 4),
            "funding_rate": round(self.funding_rate, 6),
            "funding_rate_annualized": round(self.funding_rate_annualized, 2),
            "expected_profit_8h": round(self.expected_profit_8h, 4),
            "expected_profit_annual": round(self.expected_profit_annual, 2),
            "z_score": round(self.z_score, 2),
            "confidence": round(self.confidence, 2),
            "risk_level": self.risk_level,
            "timestamp": self.timestamp.isoformat(),
        }
    
    def _get_action(self) -> str:
        if self.direction == "cash_and_carry":
            return f"SHORT {self.symbol} Perpetual, LONG {self.symbol} Spot"
        else:
            return f"LONG {self.symbol} Perpetual, SHORT {self.symbol} Spot"


class FuturesSpotBasisEngine:
    """
    Detects funding rate arbitrage opportunities between perpetual futures and spot.
    
    Key concepts:
    - Perpetual futures use funding rates to keep prices close to spot
    - When futures > spot (contango), longs pay shorts → short futures, long spot
    - When futures < spot (backwardation), shorts pay longs → long futures, short spot
    - Profit comes from collecting funding while being delta-neutral
    
    Risk factors:
    - Funding rates can flip direction
    - Basis can widen before converging
    - Exchange counterparty risk
    - Liquidation risk on futures position
    """
    
    # Simulated funding rates (in production, would come from exchange APIs)
    DEFAULT_FUNDING_INTERVALS = {
        "Binance": 8,    # hours
        "Bybit": 8,
        "OKX": 8,
        "dYdX": 1,
    }
    
    def __init__(
        self,
        min_funding_rate: float = 0.0001,  # 0.01% per 8h = ~10.95% annual
        min_annualized_return: float = 5.0,  # 5% minimum annual return
        max_basis_percent: float = 0.5,     # Max 0.5% basis to consider
    ):
        self.min_funding_rate = min_funding_rate
        self.min_annualized_return = min_annualized_return
        self.max_basis_percent = max_basis_percent
        
        # Spot prices: exchange -> pair -> (bid, ask)
        self.spot_prices: Dict[str, Dict[str, Tuple[float, float]]] = {}
        
        # Simulated futures prices and funding rates
        self.futures_data: Dict[str, Dict[str, FundingRateData]] = {}
        
        # Funding rate history for z-score calculation
        self.funding_history: Dict[str, Dict[str, FundingRateHistory]] = {}
        
        # Current opportunities
        self.opportunities: List[FuturesSpotOpportunity] = []
        
        # History
        self.history: List[FuturesSpotOpportunity] = []
        
        # Callbacks
        self._on_opportunity_callbacks: List = []
        
        # Track update count for funding rate simulation
        self._update_count = 0
    
    def on_opportunity(self, callback):
        """Register callback for new opportunities"""
        self._on_opportunity_callbacks.append(callback)
    
    def update_price(self, exchange: str, pair: str, bid: float, ask: float):
        """
        Update spot price and simulate corresponding futures data.
        In production, futures prices and funding rates would come from real APIs.
        """
        # Store spot price
        if exchange not in self.spot_prices:
            self.spot_prices[exchange] = {}
        self.spot_prices[exchange][pair] = (bid, ask)
        
        # Simulate futures data for supported exchanges
        if exchange in ["Binance", "Bybit", "OKX"]:
            self._simulate_futures_data(exchange, pair, (bid + ask) / 2)
            self._check_opportunities(exchange, pair)
        
        self._update_count += 1
    
    def _simulate_futures_data(self, exchange: str, pair: str, spot_mid: float):
        """
        Simulate realistic futures data.
        In production, this would come from actual perpetual futures APIs.
        """
        import random
        
        # Simulate basis (futures premium/discount)
        # Typically 0.01% to 0.1% premium in bull markets
        base_basis = random.gauss(0.0003, 0.0002)  # Mean 0.03%, std 0.02%
        
        # Add some persistence (trending funding)
        if exchange in self.futures_data and pair in self.futures_data[exchange]:
            prev_rate = self.futures_data[exchange][pair].funding_rate
            # Mean reversion with momentum
            base_funding = prev_rate * 0.8 + random.gauss(0.0001, 0.0003) * 0.2
        else:
            base_funding = random.gauss(0.0001, 0.0003)
        
        # Clamp funding rate to realistic range (-0.1% to 0.3% per 8h)
        funding_rate = max(-0.001, min(0.003, base_funding))
        
        # Calculate futures price from spot + basis
        futures_price = spot_mid * (1 + base_basis)
        
        # Create funding rate data
        now = datetime.now()
        next_funding = now + timedelta(hours=random.uniform(0.5, 8))
        
        funding_data = FundingRateData(
            exchange=exchange,
            symbol=pair,
            funding_rate=funding_rate,
            predicted_rate=funding_rate * random.uniform(0.8, 1.2),  # Some noise
            next_funding_time=next_funding,
            mark_price=futures_price,
            index_price=spot_mid,
            timestamp=now
        )
        
        # Store
        if exchange not in self.futures_data:
            self.futures_data[exchange] = {}
        self.futures_data[exchange][pair] = funding_data
        
        # Update funding history
        if exchange not in self.funding_history:
            self.funding_history[exchange] = {}
        if pair not in self.funding_history[exchange]:
            self.funding_history[exchange][pair] = FundingRateHistory()
        self.funding_history[exchange][pair].add(funding_rate, now)
    
    def _check_opportunities(self, exchange: str, pair: str):
        """Check for funding rate arbitrage opportunities"""
        if exchange not in self.futures_data or pair not in self.futures_data[exchange]:
            return
        if exchange not in self.spot_prices or pair not in self.spot_prices[exchange]:
            return
        
        futures = self.futures_data[exchange][pair]
        spot_bid, spot_ask = self.spot_prices[exchange][pair]
        spot_mid = (spot_bid + spot_ask) / 2
        
        # Calculate basis
        basis = futures.mark_price - spot_mid
        basis_percent = (basis / spot_mid) * 100
        
        # Skip if basis is too large (inefficient market)
        if abs(basis_percent) > self.max_basis_percent:
            return
        
        # Calculate funding rate metrics
        funding_rate = futures.funding_rate
        annualized_rate = futures.annualized_rate()
        
        # Get z-score for this funding rate
        z_score = 0.0
        if exchange in self.funding_history and pair in self.funding_history[exchange]:
            history = self.funding_history[exchange][pair]
            if len(history.rates) >= 10:
                z_score = history.z_score(funding_rate)
        
        # Determine if opportunity exists
        opportunity = None
        
        if funding_rate >= self.min_funding_rate and annualized_rate >= self.min_annualized_return:
            # Positive funding: Cash and carry (short futures, long spot)
            expected_profit_8h = abs(funding_rate) * 100  # As percentage
            expected_profit_annual = abs(annualized_rate)
            
            confidence = self._calculate_confidence(z_score, funding_rate, basis_percent)
            risk_level = self._assess_risk(z_score, basis_percent, funding_rate)
            
            opportunity = FuturesSpotOpportunity(
                exchange=exchange,
                symbol=pair,
                direction="cash_and_carry",
                spot_price=spot_mid,
                futures_price=futures.mark_price,
                basis=basis,
                basis_percent=basis_percent,
                funding_rate=funding_rate,
                funding_rate_annualized=annualized_rate,
                expected_profit_8h=expected_profit_8h,
                expected_profit_annual=expected_profit_annual,
                z_score=z_score,
                confidence=confidence,
                risk_level=risk_level,
                timestamp=datetime.now()
            )
        
        elif funding_rate <= -self.min_funding_rate and abs(annualized_rate) >= self.min_annualized_return:
            # Negative funding: Reverse cash and carry (long futures, short spot)
            expected_profit_8h = abs(funding_rate) * 100
            expected_profit_annual = abs(annualized_rate)
            
            confidence = self._calculate_confidence(z_score, funding_rate, basis_percent)
            risk_level = self._assess_risk(z_score, basis_percent, funding_rate)
            
            opportunity = FuturesSpotOpportunity(
                exchange=exchange,
                symbol=pair,
                direction="reverse_cash_carry",
                spot_price=spot_mid,
                futures_price=futures.mark_price,
                basis=basis,
                basis_percent=basis_percent,
                funding_rate=funding_rate,
                funding_rate_annualized=annualized_rate,
                expected_profit_8h=expected_profit_8h,
                expected_profit_annual=expected_profit_annual,
                z_score=z_score,
                confidence=confidence,
                risk_level=risk_level,
                timestamp=datetime.now()
            )
        
        if opportunity:
            # Update opportunities list
            self.opportunities = [
                o for o in self.opportunities 
                if not (o.exchange == exchange and o.symbol == pair)
            ]
            self.opportunities.append(opportunity)
            self.opportunities.sort(key=lambda x: x.expected_profit_annual, reverse=True)
            
            # Add to history
            self.history.append(opportunity)
            if len(self.history) > 100:
                self.history.pop(0)
            
            # Log significant opportunities
            if abs(z_score) > 1.5 or opportunity.expected_profit_annual > 15:
                logger.info(
                    f"📊 FUTURES-SPOT: {exchange} {pair} | "
                    f"{opportunity.direction.replace('_', ' ').upper()} | "
                    f"Funding: {funding_rate*100:.4f}% | "
                    f"Annual: {annualized_rate:.1f}% | Z={z_score:.2f}"
                )
            
            # Notify listeners
            for callback in self._on_opportunity_callbacks:
                try:
                    callback(opportunity)
                except Exception as e:
                    logger.error(f"Futures-spot callback error: {e}")
    
    def _calculate_confidence(
        self, 
        z_score: float, 
        funding_rate: float, 
        basis_percent: float
    ) -> float:
        """Calculate confidence in the opportunity"""
        # Higher confidence with:
        # - Extreme z-score (unusual funding rate)
        # - Lower basis (efficient market)
        # - Higher absolute funding rate
        
        z_factor = min(1.0, abs(z_score) / 3.0)  # Max at z=3
        basis_factor = 1.0 - min(1.0, abs(basis_percent) / self.max_basis_percent)
        rate_factor = min(1.0, abs(funding_rate) / 0.001)  # Max at 0.1%
        
        confidence = 0.4 * z_factor + 0.3 * basis_factor + 0.3 * rate_factor
        return max(0.0, min(1.0, confidence))
    
    def _assess_risk(
        self, 
        z_score: float, 
        basis_percent: float, 
        funding_rate: float
    ) -> str:
        """Assess risk level of the opportunity"""
        risk_score = 0
        
        # High z-score means rate might revert
        if abs(z_score) > 2.5:
            risk_score += 2
        elif abs(z_score) > 1.5:
            risk_score += 1
        
        # Large basis means potential convergence risk
        if abs(basis_percent) > 0.3:
            risk_score += 2
        elif abs(basis_percent) > 0.1:
            risk_score += 1
        
        # Very high funding might flip
        if abs(funding_rate) > 0.002:
            risk_score += 1
        
        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        return "low"
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        # Calculate aggregate stats
        total_annual_return = sum(o.expected_profit_annual for o in self.opportunities)
        avg_funding = 0
        if self.opportunities:
            avg_funding = sum(o.funding_rate for o in self.opportunities) / len(self.opportunities)
        
        return {
            "futures_spot_opportunities": [o.to_dict() for o in self.opportunities[:10]],
            "futures_spot_history": [o.to_dict() for o in self.history[-20:]],
            "total_pairs_tracked": sum(len(pairs) for pairs in self.futures_data.values()),
            "avg_funding_rate": round(avg_funding * 100, 4),
            "total_potential_annual_return": round(total_annual_return, 2),
            "exchanges_with_futures": list(self.futures_data.keys()),
            "config": {
                "min_funding_rate": self.min_funding_rate,
                "min_annualized_return": self.min_annualized_return,
                "max_basis_percent": self.max_basis_percent,
            }
        }
