"""
Cross-Exchange Triangular Arbitrage Engine

Detects arbitrage opportunities by trading through multiple pairs ACROSS exchanges.

Example cycle:
  Binance BTC/USDT → Kraken ETH/BTC → Coinbase ETH/USDT → USDT
  1. Buy BTC with USDT on Binance
  2. Buy ETH with BTC on Kraken
  3. Sell ETH for USDT on Coinbase

This is more complex than single-exchange triangular as it involves:
- Transfer delays between exchanges
- Different fee structures per exchange
- Exchange-specific liquidity
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict
import itertools

logger = logging.getLogger(__name__)


@dataclass
class CrossExchangePath:
    """Represents a cross-exchange triangular arbitrage path"""
    base_currency: str  # Starting currency (e.g., "USDT")
    steps: List[Tuple[str, str, str]]  # List of (exchange, pair, side)
    
    def __str__(self):
        parts = []
        for exchange, pair, side in self.steps:
            parts.append(f"{side.upper()} {pair}@{exchange}")
        return " → ".join(parts)
    
    def exchanges_involved(self) -> Set[str]:
        return set(step[0] for step in self.steps)


@dataclass
class CrossExchangeOpportunity:
    """Represents a detected cross-exchange triangular opportunity"""
    path: CrossExchangePath
    start_amount: float
    end_amount: float
    profit_amount: float
    profit_percent: float
    prices_used: Dict[str, Dict[str, Tuple[float, float]]]  # exchange -> pair -> (bid, ask)
    fees_total: float
    estimated_transfer_time_ms: int
    risk_score: float  # 0-1, higher = more risky
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "type": "cross_exchange_triangular",
            "base_currency": self.path.base_currency,
            "path_description": str(self.path),
            "steps": [
                {"exchange": ex, "pair": pair, "side": side}
                for ex, pair, side in self.path.steps
            ],
            "exchanges": list(self.path.exchanges_involved()),
            "start_amount": round(self.start_amount, 2),
            "end_amount": round(self.end_amount, 2),
            "profit_amount": round(self.profit_amount, 2),
            "profit_percent": round(self.profit_percent, 4),
            "fees_total": round(self.fees_total, 4),
            "estimated_transfer_time_ms": self.estimated_transfer_time_ms,
            "risk_score": round(self.risk_score, 2),
            "timestamp": self.timestamp.isoformat(),
        }


class CrossExchangeTriangularEngine:
    """
    Detects triangular arbitrage opportunities across multiple exchanges.
    
    This is significantly more complex than single-exchange triangular because:
    - Prices must be fetched from different exchanges
    - Different fee structures must be considered
    - Transfer times between exchanges introduce risk
    - Path computation spans multiple price sources
    """
    
    # Estimated transfer times between exchanges (ms)
    TRANSFER_TIMES = {
        ("Binance", "Kraken"): 60000,
        ("Binance", "Coinbase"): 60000,
        ("Binance", "Bybit"): 30000,
        ("Binance", "OKX"): 30000,
        ("Kraken", "Coinbase"): 90000,
        ("Kraken", "Bybit"): 60000,
        ("Kraken", "OKX"): 60000,
        ("Coinbase", "Bybit"): 60000,
        ("Coinbase", "OKX"): 60000,
        ("Bybit", "OKX"): 30000,
    }
    
    # Exchange-specific trading fees
    EXCHANGE_FEES = {
        "Binance": 0.001,   # 0.1%
        "Kraken": 0.002,    # 0.2%
        "Coinbase": 0.004,  # 0.4%
        "Bybit": 0.001,     # 0.1%
        "OKX": 0.001,       # 0.1%
    }
    
    def __init__(
        self, 
        min_profit_threshold: float = 0.3,  # Higher threshold for cross-exchange
        max_transfer_time_ms: int = 120000   # 2 minutes max transfer window
    ):
        self.min_profit_threshold = min_profit_threshold
        self.max_transfer_time_ms = max_transfer_time_ms
        
        # Store prices: exchange -> pair -> (bid, ask, timestamp)
        self.prices: Dict[str, Dict[str, Tuple[float, float, datetime]]] = defaultdict(dict)
        
        # Current opportunities
        self.opportunities: List[CrossExchangeOpportunity] = []
        
        # History
        self.history: List[CrossExchangeOpportunity] = []
        
        # Pre-computed paths (generated dynamically)
        self.cross_exchange_paths: List[CrossExchangePath] = []
        
        # Callbacks
        self._on_opportunity_callbacks: List = []
    
    def on_opportunity(self, callback):
        """Register callback for new opportunities"""
        self._on_opportunity_callbacks.append(callback)
    
    def update_price(self, exchange: str, pair: str, bid: float, ask: float):
        """Update price and check for cross-exchange triangular opportunities"""
        self.prices[exchange][pair] = (bid, ask, datetime.now())
        
        # Recompute paths if we have enough exchanges
        if len(self.prices) >= 2:
            self._compute_cross_exchange_paths()
            self._check_opportunities()
    
    def _compute_cross_exchange_paths(self):
        """
        Compute all possible cross-exchange triangular paths.
        
        A valid path:
        1. Starts and ends with same currency (USDT, USD, etc.)
        2. Uses 2-3 different exchanges
        3. Forms a complete cycle
        """
        if len(self.prices) < 2:
            self.cross_exchange_paths = []
            return
        
        # Build global currency graph
        # edges: (currency, exchange) -> [(target_currency, pair, side, target_exchange)]
        edges: Dict[Tuple[str, str], List[Tuple[str, str, str, str]]] = defaultdict(list)
        all_currencies = set()
        
        for exchange, pairs in self.prices.items():
            for pair in pairs.keys():
                if '/' not in pair:
                    continue
                base, quote = pair.split('/')
                all_currencies.add(base)
                all_currencies.add(quote)
                
                # Can buy base with quote (stay on same exchange)
                edges[(quote, exchange)].append((base, pair, 'buy', exchange))
                # Can sell base for quote (stay on same exchange)
                edges[(base, exchange)].append((quote, pair, 'sell', exchange))
                
                # Cross-exchange transfers (instant for this model)
                # Can transfer base to other exchanges
                for other_exchange in self.prices.keys():
                    if other_exchange != exchange:
                        edges[(base, exchange)].append((base, f"TRANSFER_{base}", 'transfer', other_exchange))
                        edges[(quote, exchange)].append((quote, f"TRANSFER_{quote}", 'transfer', other_exchange))
        
        # Find 3-step paths starting from USDT on any exchange
        base_currencies = ['USDT', 'USD', 'USDC']
        paths = []
        
        for start_currency in base_currencies:
            if start_currency not in all_currencies:
                continue
            
            # For each exchange that has the starting currency
            for start_exchange in self.prices.keys():
                # Check if this exchange has any pair with the starting currency
                has_start_currency = any(
                    start_currency in pair.split('/')
                    for pair in self.prices[start_exchange].keys()
                )
                if not has_start_currency:
                    continue
                
                # BFS for paths of length 2-4 (allowing transfers)
                self._find_paths_bfs(
                    start_currency, start_exchange, edges, paths, max_trades=3
                )
        
        # Filter to unique paths with at least 2 exchanges
        seen = set()
        unique_paths = []
        for path in paths:
            path_key = str(path)
            if path_key not in seen and len(path.exchanges_involved()) >= 2:
                seen.add(path_key)
                unique_paths.append(path)
        
        self.cross_exchange_paths = unique_paths[:100]  # Limit for performance
        
        if len(self.cross_exchange_paths) > 0:
            logger.debug(f"Computed {len(self.cross_exchange_paths)} cross-exchange triangular paths")
    
    def _find_paths_bfs(
        self,
        start_currency: str,
        start_exchange: str,
        edges: Dict,
        paths: List[CrossExchangePath],
        max_trades: int = 3
    ):
        """Find all valid cycles using BFS"""
        # State: (current_currency, current_exchange, steps_taken, trades_made, visited_pairs)
        queue = [(start_currency, start_exchange, [], 0, set())]
        
        while queue:
            curr_currency, curr_exchange, steps, trades, visited = queue.pop(0)
            
            # If we've made some trades and returned to start, record the path
            if trades >= 2 and curr_currency == start_currency:
                # Check if we used multiple exchanges
                exchanges_used = set(step[0] for step in steps if not step[1].startswith('TRANSFER'))
                if len(exchanges_used) >= 2:
                    path = CrossExchangePath(
                        base_currency=start_currency,
                        steps=[(ex, pair, side) for ex, pair, side in steps if not pair.startswith('TRANSFER')]
                    )
                    if len(path.steps) >= 2:
                        paths.append(path)
                continue
            
            # Don't exceed max trades
            if trades >= max_trades:
                continue
            
            # Explore neighbors
            for next_currency, pair, side, next_exchange in edges.get((curr_currency, curr_exchange), []):
                # Skip if we've already used this pair on this exchange (no loops)
                pair_key = f"{curr_exchange}:{pair}"
                if pair_key in visited and not pair.startswith('TRANSFER'):
                    continue
                
                new_visited = visited.copy()
                new_visited.add(pair_key)
                
                new_steps = steps + [(curr_exchange if not pair.startswith('TRANSFER') else next_exchange, pair, side)]
                new_trades = trades + (0 if pair.startswith('TRANSFER') else 1)
                
                # Only allow 1 transfer per path
                transfer_count = sum(1 for s in new_steps if s[1].startswith('TRANSFER'))
                if transfer_count > 2:
                    continue
                
                queue.append((next_currency, next_exchange, new_steps, new_trades, new_visited))
    
    def _check_opportunities(self):
        """Check all cross-exchange paths for profit"""
        new_opportunities = []
        
        for path in self.cross_exchange_paths:
            opportunity = self._calculate_profit(path)
            if opportunity:
                new_opportunities.append(opportunity)
        
        # Update opportunities
        self.opportunities = new_opportunities
        self.opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
        
        # Notify listeners and add to history
        for opp in new_opportunities[:5]:  # Top 5 only
            if opp.profit_percent >= self.min_profit_threshold:
                logger.info(
                    f"🔀 CROSS-EXCHANGE ARB: {opp.path.base_currency} | "
                    f"{' → '.join(opp.path.exchanges_involved())} | "
                    f"Profit: {opp.profit_percent:.3f}% | Risk: {opp.risk_score:.2f}"
                )
                
                self.history.append(opp)
                if len(self.history) > 50:
                    self.history.pop(0)
                
                for callback in self._on_opportunity_callbacks:
                    try:
                        callback(opp)
                    except Exception as e:
                        logger.error(f"Cross-exchange opportunity callback error: {e}")
    
    def _calculate_profit(
        self,
        path: CrossExchangePath,
        start_amount: float = 10000.0
    ) -> Optional[CrossExchangeOpportunity]:
        """Calculate profit for a cross-exchange path"""
        current_amount = start_amount
        total_fees = 0.0
        total_transfer_time = 0
        prices_used = defaultdict(dict)
        
        prev_exchange = None
        
        for exchange, pair, side in path.steps:
            # Check if we need to "transfer" between exchanges
            if prev_exchange and prev_exchange != exchange:
                # Add transfer time
                key = tuple(sorted([prev_exchange, exchange]))
                transfer_time = self.TRANSFER_TIMES.get(key, 60000)
                total_transfer_time += transfer_time
            
            # Get price for this step
            if pair not in self.prices.get(exchange, {}):
                return None  # Missing price data
            
            bid, ask, _ = self.prices[exchange][pair]
            prices_used[exchange][pair] = (bid, ask)
            
            # Calculate trade
            fee_rate = self.EXCHANGE_FEES.get(exchange, 0.001)
            
            if side == 'buy':
                # Buying base with quote
                current_amount = (current_amount / ask) * (1 - fee_rate)
            else:  # sell
                # Selling base for quote
                current_amount = (current_amount * bid) * (1 - fee_rate)
            
            total_fees += fee_rate * current_amount
            prev_exchange = exchange
        
        # Calculate profit
        profit_amount = current_amount - start_amount
        profit_percent = (profit_amount / start_amount) * 100
        
        # Skip if total transfer time exceeds maximum
        if total_transfer_time > self.max_transfer_time_ms:
            return None
        
        # Calculate risk score (higher = more risky)
        # Based on: number of exchanges, transfer time, profit margin
        num_exchanges = len(path.exchanges_involved())
        time_risk = total_transfer_time / self.max_transfer_time_ms
        profit_risk = max(0, 1 - (profit_percent / 1.0))  # Higher profit = lower risk
        risk_score = (0.3 * num_exchanges / 3) + (0.4 * time_risk) + (0.3 * profit_risk)
        risk_score = min(1.0, max(0.0, risk_score))
        
        if profit_percent >= self.min_profit_threshold:
            return CrossExchangeOpportunity(
                path=path,
                start_amount=start_amount,
                end_amount=current_amount,
                profit_amount=profit_amount,
                profit_percent=profit_percent,
                prices_used=dict(prices_used),
                fees_total=total_fees,
                estimated_transfer_time_ms=total_transfer_time,
                risk_score=risk_score,
                timestamp=datetime.now()
            )
        
        return None
    
    def _get_transfer_time(self, ex1: str, ex2: str) -> int:
        """Get estimated transfer time between two exchanges"""
        key = tuple(sorted([ex1, ex2]))
        return self.TRANSFER_TIMES.get(key, 60000)
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "cross_exchange_opportunities": [o.to_dict() for o in self.opportunities[:10]],
            "cross_exchange_history": [o.to_dict() for o in self.history[-20:]],
            "paths_computed": len(self.cross_exchange_paths),
            "exchanges_active": list(self.prices.keys()),
            "config": {
                "min_profit_threshold": self.min_profit_threshold,
                "max_transfer_time_ms": self.max_transfer_time_ms,
            }
        }
