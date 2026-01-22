"""Arbitrage calculation engine"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from collections import defaultdict

from exchanges.base import PriceUpdate
from config import MIN_PROFIT_THRESHOLD, TRADING_PAIRS

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    pair: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float  # Ask price on buy exchange
    sell_price: float  # Bid price on sell exchange
    profit_percent: float
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "pair": self.pair,
            "buy_exchange": self.buy_exchange,
            "sell_exchange": self.sell_exchange,
            "buy_price": self.buy_price,
            "sell_price": self.sell_price,
            "profit_percent": round(self.profit_percent, 4),
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ExchangePrice:
    """Current price state for a pair on an exchange"""
    exchange: str
    pair: str
    bid: float
    ask: float
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "exchange": self.exchange,
            "pair": self.pair,
            "bid": self.bid,
            "ask": self.ask,
            "mid": (self.bid + self.ask) / 2,
            "spread_percent": ((self.ask - self.bid) / ((self.bid + self.ask) / 2)) * 100,
            "timestamp": self.timestamp.isoformat(),
        }


class ArbitrageEngine:
    """
    Core engine for detecting arbitrage opportunities.
    
    Arbitrage opportunity exists when:
    - Exchange A's ask (buy) price < Exchange B's bid (sell) price
    - After accounting for fees, there's still profit
    
    Simple arbitrage formula:
    profit% = ((sell_bid - buy_ask) / buy_ask) * 100
    """
    
    def __init__(self, min_profit_threshold: float = MIN_PROFIT_THRESHOLD):
        self.min_profit_threshold = min_profit_threshold
        # prices[pair][exchange] = ExchangePrice
        self.prices: dict[str, dict[str, ExchangePrice]] = defaultdict(dict)
        # Current opportunities
        self.opportunities: list[ArbitrageOpportunity] = []
        # Historical opportunities (last 100)
        self.history: list[ArbitrageOpportunity] = []
        # Callbacks for UI updates
        self._on_opportunity_callbacks: list = []
        self._on_price_update_callbacks: list = []
        
    def on_opportunity(self, callback):
        """Register callback for new opportunities"""
        self._on_opportunity_callbacks.append(callback)
        
    def on_price_update(self, callback):
        """Register callback for price updates"""
        self._on_price_update_callbacks.append(callback)
    
    def process_price_update(self, update: PriceUpdate):
        """Process incoming price update and check for arbitrage"""
        # Store the new price
        self.prices[update.pair][update.exchange] = ExchangePrice(
            exchange=update.exchange,
            pair=update.pair,
            bid=update.bid,
            ask=update.ask,
            timestamp=update.timestamp
        )
        
        # Notify price update listeners
        for callback in self._on_price_update_callbacks:
            try:
                callback(update)
            except Exception as e:
                logger.error(f"Price callback error: {e}")
        
        # Check for arbitrage on this pair
        self._check_arbitrage(update.pair)
    
    def _check_arbitrage(self, pair: str):
        """Check for arbitrage opportunities across all exchanges for a pair"""
        if pair not in self.prices:
            return
        
        exchanges = list(self.prices[pair].keys())
        if len(exchanges) < 2:
            return
        
        new_opportunities = []
        
        # Compare all exchange pairs
        for i, ex1 in enumerate(exchanges):
            for ex2 in exchanges[i+1:]:
                price1 = self.prices[pair][ex1]
                price2 = self.prices[pair][ex2]
                
                # Check ex1 buy -> ex2 sell
                opp1 = self._calculate_opportunity(pair, price1, price2)
                if opp1:
                    new_opportunities.append(opp1)
                
                # Check ex2 buy -> ex1 sell
                opp2 = self._calculate_opportunity(pair, price2, price1)
                if opp2:
                    new_opportunities.append(opp2)
        
        # Update opportunities list for this pair
        # Remove old opportunities for this pair
        self.opportunities = [o for o in self.opportunities if o.pair != pair]
        self.opportunities.extend(new_opportunities)
        
        # Sort by profit
        self.opportunities.sort(key=lambda x: x.profit_percent, reverse=True)
        
        # Notify listeners of new opportunities
        for opp in new_opportunities:
            logger.info(
                f"🎯 ARBITRAGE: {opp.pair} | "
                f"Buy@{opp.buy_exchange} ${opp.buy_price:.2f} → "
                f"Sell@{opp.sell_exchange} ${opp.sell_price:.2f} | "
                f"Profit: {opp.profit_percent:.3f}%"
            )
            
            # Add to history
            self.history.append(opp)
            if len(self.history) > 100:
                self.history.pop(0)
            
            for callback in self._on_opportunity_callbacks:
                try:
                    callback(opp)
                except Exception as e:
                    logger.error(f"Opportunity callback error: {e}")
    
    def _calculate_opportunity(
        self, 
        pair: str, 
        buy_exchange: ExchangePrice, 
        sell_exchange: ExchangePrice
    ) -> Optional[ArbitrageOpportunity]:
        """
        Calculate if buying on one exchange and selling on another is profitable.
        
        Buy at ask price (what sellers want)
        Sell at bid price (what buyers offer)
        """
        buy_price = buy_exchange.ask  # We pay the ask to buy
        sell_price = sell_exchange.bid  # We receive the bid to sell
        
        if buy_price <= 0:
            return None
        
        # Calculate profit percentage
        profit_percent = ((sell_price - buy_price) / buy_price) * 100
        
        if profit_percent >= self.min_profit_threshold:
            return ArbitrageOpportunity(
                pair=pair,
                buy_exchange=buy_exchange.exchange,
                sell_exchange=sell_exchange.exchange,
                buy_price=buy_price,
                sell_price=sell_price,
                profit_percent=profit_percent,
                timestamp=datetime.now()
            )
        
        return None
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "prices": {
                pair: {
                    ex: price.to_dict() 
                    for ex, price in exchanges.items()
                }
                for pair, exchanges in self.prices.items()
            },
            "opportunities": [o.to_dict() for o in self.opportunities],
            "history": [o.to_dict() for o in self.history[-20:]],  # Last 20
            "config": {
                "min_profit_threshold": self.min_profit_threshold,
                "pairs": TRADING_PAIRS,
            }
        }
