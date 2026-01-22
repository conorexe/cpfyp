"""Simulated exchange for testing when real connections are blocked"""
import asyncio
import logging
import random
from datetime import datetime
from typing import Callable, Optional

from .base import PriceUpdate
from config import TRADING_PAIRS

logger = logging.getLogger(__name__)


# Realistic base prices for simulation
BASE_PRICES = {
    "BTC/USDT": 97500.0,
    "ETH/USDT": 3250.0,
    "SOL/USDT": 245.0,
    "XRP/USDT": 3.15,
    "ETH/BTC": 0.0333,  # ETH price in BTC
    "SOL/BTC": 0.00251,  # SOL price in BTC
    "XRP/BTC": 0.0000323,  # XRP price in BTC
}


class SimulatedExchange:
    """
    Simulates an exchange with realistic price movements.
    Useful when network restrictions block real exchange connections.
    """
    
    def __init__(self, name: str, price_offset_percent: float = 0.0):
        """
        Args:
            name: Exchange name for display
            price_offset_percent: Base price offset to simulate different exchange prices
                                  e.g., 0.05 means prices are 0.05% higher than base
        """
        self.name = name
        self.price_offset = price_offset_percent / 100
        self.running = False
        self.on_price_update: Optional[Callable[[PriceUpdate], None]] = None
        self.current_prices = {pair: price for pair, price in BASE_PRICES.items()}
        
    def set_callback(self, callback: Callable[[PriceUpdate], None]):
        """Set callback for price updates"""
        self.on_price_update = callback
    
    async def connect(self):
        """Start generating simulated price updates"""
        self.running = True
        logger.info(f"[{self.name}] 🎮 SIMULATION MODE - Generating mock prices")
        
        while self.running:
            for pair in TRADING_PAIRS:
                if pair not in self.current_prices:
                    continue
                    
                # Simulate realistic price movement (random walk)
                base_price = self.current_prices[pair]
                
                # Small random movement (-0.1% to +0.1%)
                movement = random.uniform(-0.001, 0.001)
                new_price = base_price * (1 + movement)
                self.current_prices[pair] = new_price
                
                # Apply exchange-specific offset
                adjusted_price = new_price * (1 + self.price_offset)
                
                # Create realistic spread (0.01% to 0.05%)
                spread_percent = random.uniform(0.0001, 0.0005)
                half_spread = adjusted_price * spread_percent / 2
                
                bid = adjusted_price - half_spread
                ask = adjusted_price + half_spread
                
                update = PriceUpdate(
                    exchange=self.name,
                    pair=pair,
                    bid=bid,
                    ask=ask,
                    timestamp=datetime.now()
                )
                
                if self.on_price_update:
                    self.on_price_update(update)
            
            # Update every 100-500ms for realistic feel
            await asyncio.sleep(random.uniform(0.1, 0.5))
    
    async def disconnect(self):
        """Stop simulation"""
        self.running = False
        logger.info(f"[{self.name}] Simulation stopped")


def create_simulated_exchanges() -> list[SimulatedExchange]:
    """
    Create a set of simulated exchanges with slight price differences.
    The offsets create opportunities for the arbitrage engine to detect.
    """
    return [
        SimulatedExchange("Binance-SIM", price_offset_percent=0.0),
        SimulatedExchange("Kraken-SIM", price_offset_percent=0.02),   # Slightly higher
        SimulatedExchange("Coinbase-SIM", price_offset_percent=-0.03), # Slightly lower
    ]
