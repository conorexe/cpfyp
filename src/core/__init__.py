"""
Core arbitrage detection engines and data structures.
"""

from .opportunity import ArbitrageOpportunity, ExchangePrice, TriangularOpportunity
from .engine import ArbitrageEngine

__all__ = [
    "ArbitrageOpportunity",
    "ExchangePrice", 
    "TriangularOpportunity",
    "ArbitrageEngine",
]
