"""
Portfolio management module for MarketScout.

Provides paper trading functionality:
- Portfolio creation and management
- Position tracking
- Trade simulation
- P&L calculation
"""

from .models import Portfolio, Position, Trade, PortfolioSummary
from .service import PortfolioService

__all__ = [
    "Portfolio",
    "Position",
    "Trade",
    "PortfolioSummary",
    "PortfolioService",
]
