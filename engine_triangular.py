"""
Triangular Arbitrage Engine

Detects arbitrage opportunities within a single exchange by trading through
multiple pairs in a cycle.

Example cycle:
  USDT → BTC → ETH → USDT
  1. Buy BTC with USDT (BTC/USDT)
  2. Buy ETH with BTC (ETH/BTC)
  3. Sell ETH for USDT (ETH/USDT)
  
If the product of exchange rates yields more USDT than you started with, profit!
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from collections import defaultdict
import itertools

logger = logging.getLogger(__name__)


@dataclass
class TriangularPath:
    """Represents a triangular arbitrage path"""
    exchange: str
    base_currency: str  # Starting currency (e.g., "USDT")
    pairs: List[str]    # Trading pairs in order (e.g., ["BTC/USDT", "ETH/BTC", "ETH/USDT"])
    sides: List[str]    # "buy" or "sell" for each pair
    
    def __str__(self):
        steps = []
        for pair, side in zip(self.pairs, self.sides):
            steps.append(f"{side.upper()} {pair}")
        return " → ".join(steps)


@dataclass
class TriangularOpportunity:
    """Represents a detected triangular arbitrage opportunity"""
    exchange: str
    path: TriangularPath
    start_amount: float  # Amount of base currency to start with
    end_amount: float    # Expected amount after completing cycle
    profit_amount: float
    profit_percent: float
    prices: Dict[str, Tuple[float, float]]  # pair -> (bid, ask) used
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "base_currency": self.path.base_currency,
            "pairs": self.path.pairs,
            "sides": self.path.sides,
            "path_description": str(self.path),
            "start_amount": round(self.start_amount, 2),
            "end_amount": round(self.end_amount, 2),
            "profit_amount": round(self.profit_amount, 2),
            "profit_percent": round(self.profit_percent, 4),
            "prices": {pair: {"bid": bid, "ask": ask} for pair, (bid, ask) in self.prices.items()},
            "timestamp": self.timestamp.isoformat(),
        }


class TriangularArbitrageEngine:
    """
    Detects triangular arbitrage opportunities on a single exchange.
    
    This is more sophisticated than simple cross-exchange arbitrage because:
    - No transfer delays between exchanges
    - Can be executed atomically
    - Requires graph theory to find profitable cycles
    """
    
    def __init__(self, min_profit_threshold: float = 0.1, trading_fee: float = 0.001):
        """
        Args:
            min_profit_threshold: Minimum profit % to flag as opportunity
            trading_fee: Trading fee per trade (0.001 = 0.1%)
        """
        self.min_profit_threshold = min_profit_threshold
        self.trading_fee = trading_fee
        
        # Store latest prices: exchange -> pair -> (bid, ask)
        self.prices: Dict[str, Dict[str, Tuple[float, float]]] = defaultdict(dict)
        
        # Pre-computed triangular paths for each exchange
        self.triangular_paths: Dict[str, List[TriangularPath]] = {}
        
        # Current opportunities
        self.opportunities: List[TriangularOpportunity] = []
        
        # History (last 50)
        self.history: List[TriangularOpportunity] = []
        
        # Callbacks
        self._on_opportunity_callbacks: List = []
    
    def on_opportunity(self, callback):
        """Register callback for new triangular opportunities"""
        self._on_opportunity_callbacks.append(callback)
    
    def update_price(self, exchange: str, pair: str, bid: float, ask: float):
        """Update price for a pair and check for triangular opportunities"""
        self.prices[exchange][pair] = (bid, ask)
        
        # If this exchange doesn't have paths computed yet, do it now
        if exchange not in self.triangular_paths:
            self._compute_triangular_paths(exchange)
        
        # Check all paths on this exchange
        self._check_triangular_opportunities(exchange)
    
    def _compute_triangular_paths(self, exchange: str):
        """
        Compute all possible triangular arbitrage paths for an exchange.
        
        A triangular path consists of 3 trades that form a cycle.
        For example: USDT → BTC → ETH → USDT
        """
        pairs = list(self.prices[exchange].keys())
        
        if len(pairs) < 3:
            self.triangular_paths[exchange] = []
            return
        
        # Build currency graph
        currencies = set()
        edges: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)  # from_currency -> [(to_currency, pair, side)]
        
        for pair in pairs:
            if '/' not in pair:
                continue
            base, quote = pair.split('/')
            currencies.add(base)
            currencies.add(quote)
            
            # You can buy base with quote (ask price)
            edges[quote].append((base, pair, 'buy'))
            # You can sell base for quote (bid price)
            edges[base].append((quote, pair, 'sell'))
        
        # Find all 3-step cycles starting from USDT (or USD, USDC, etc.)
        base_currencies = ['USDT', 'USD', 'USDC', 'BUSD']
        paths = []
        
        for start_currency in base_currencies:
            if start_currency not in currencies:
                continue
            
            # Find all 3-step paths that return to start_currency
            for curr1, pair1, side1 in edges[start_currency]:
                for curr2, pair2, side2 in edges[curr1]:
                    for curr3, pair3, side3 in edges[curr2]:
                        if curr3 == start_currency:
                            path = TriangularPath(
                                exchange=exchange,
                                base_currency=start_currency,
                                pairs=[pair1, pair2, pair3],
                                sides=[side1, side2, side3]
                            )
                            paths.append(path)
        
        self.triangular_paths[exchange] = paths
        logger.info(f"[{exchange}] Computed {len(paths)} triangular paths")
    
    def _check_triangular_opportunities(self, exchange: str):
        """Check all triangular paths on an exchange for profit"""
        if exchange not in self.triangular_paths:
            return
        
        new_opportunities = []
        
        for path in self.triangular_paths[exchange]:
            opportunity = self._calculate_triangular_profit(exchange, path)
            if opportunity:
                new_opportunities.append(opportunity)
        
        # Update opportunities list
        self.opportunities = [o for o in self.opportunities if o.exchange != exchange]
        self.opportunities.extend(new_opportunities)
        self.opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
        
        # Notify listeners and add to history
        for opp in new_opportunities:
            logger.info(
                f"🔺 TRIANGULAR ARB: {opp.exchange} | {opp.path.base_currency} | "
                f"{' → '.join(opp.path.pairs)} | Profit: {opp.profit_percent:.3f}%"
            )
            
            self.history.append(opp)
            if len(self.history) > 50:
                self.history.pop(0)
            
            for callback in self._on_opportunity_callbacks:
                try:
                    callback(opp)
                except Exception as e:
                    logger.error(f"Triangular opportunity callback error: {e}")
    
    def _calculate_triangular_profit(
        self, 
        exchange: str, 
        path: TriangularPath,
        start_amount: float = 10000.0
    ) -> Optional[TriangularOpportunity]:
        """
        Calculate profit for a triangular path.
        
        Args:
            exchange: Exchange name
            path: Triangular path to evaluate
            start_amount: Amount of base currency to start with
        
        Returns:
            TriangularOpportunity if profitable, None otherwise
        """
        # Check if all required prices are available
        prices_used = {}
        for pair in path.pairs:
            if pair not in self.prices[exchange]:
                return None
            prices_used[pair] = self.prices[exchange][pair]
        
        # Simulate the trades
        current_amount = start_amount
        
        for pair, side in zip(path.pairs, path.sides):
            bid, ask = self.prices[exchange][pair]
            base, quote = pair.split('/')
            
            if side == 'buy':
                # Buying base with quote
                # We pay the ask price + fee
                price = ask
                # Amount of base we get = current_amount / price
                current_amount = (current_amount / price) * (1 - self.trading_fee)
            else:  # sell
                # Selling base for quote
                # We get the bid price - fee
                price = bid
                # Amount of quote we get = current_amount * price
                current_amount = (current_amount * price) * (1 - self.trading_fee)
        
        # Calculate profit
        profit_amount = current_amount - start_amount
        profit_percent = (profit_amount / start_amount) * 100
        
        # Only return if above threshold
        if profit_percent >= self.min_profit_threshold:
            return TriangularOpportunity(
                exchange=exchange,
                path=path,
                start_amount=start_amount,
                end_amount=current_amount,
                profit_amount=profit_amount,
                profit_percent=profit_percent,
                prices=prices_used,
                timestamp=datetime.now()
            )
        
        return None
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "triangular_opportunities": [o.to_dict() for o in self.opportunities],
            "triangular_history": [o.to_dict() for o in self.history[-20:]],
            "paths_computed": {
                exchange: len(paths) 
                for exchange, paths in self.triangular_paths.items()
            }
        }
