"""
Portfolio data models.
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeType(str, Enum):
    ARBITRAGE = "arbitrage"
    TRIANGULAR = "triangular"
    MANUAL = "manual"
    SIMULATION = "simulation"


class PositionCreate(BaseModel):
    """Create a new position"""
    asset: str = Field(..., min_length=1, max_length=20)
    quantity: float = Field(..., gt=0)
    avg_entry_price: Optional[float] = None


class Position(BaseModel):
    """Portfolio position"""
    id: int
    portfolio_id: int
    asset: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    value_usd: float
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TradeCreate(BaseModel):
    """Create a new trade"""
    pair: str
    side: TradeSide
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    exchange: str
    trade_type: TradeType = TradeType.MANUAL
    notes: Optional[str] = None


class Trade(BaseModel):
    """Executed trade record"""
    id: int
    portfolio_id: int
    opportunity_id: Optional[int] = None
    pair: str
    side: TradeSide
    quantity: float
    price: float
    value_usd: float
    fee: float
    exchange: str
    trade_type: TradeType
    notes: Optional[str] = None
    timestamp: datetime
    
    class Config:
        from_attributes = True


class PortfolioCreate(BaseModel):
    """Create a new portfolio"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    initial_balance: float = Field(default=10000, gt=0)


class PortfolioUpdate(BaseModel):
    """Update portfolio settings"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None


class Portfolio(BaseModel):
    """User portfolio"""
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    initial_balance: float
    current_balance: float
    is_default: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PortfolioSummary(BaseModel):
    """Portfolio with computed statistics"""
    portfolio: Portfolio
    positions: List[Position]
    recent_trades: List[Trade]
    
    # Computed statistics
    total_value: float
    cash_balance: float
    invested_value: float
    total_pnl: float
    total_pnl_percent: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    best_trade_pnl: Optional[float] = None
    worst_trade_pnl: Optional[float] = None
    avg_trade_pnl: Optional[float] = None


class ExecuteArbitrageRequest(BaseModel):
    """Request to execute an arbitrage opportunity (simulation)"""
    buy_exchange: str
    sell_exchange: str
    pair: str
    quantity: float = Field(..., gt=0)
    buy_price: float = Field(..., gt=0)
    sell_price: float = Field(..., gt=0)
    
    # Optional fee override
    buy_fee_percent: float = Field(default=0.1, ge=0)
    sell_fee_percent: float = Field(default=0.1, ge=0)


class ExecuteArbitrageResponse(BaseModel):
    """Response from arbitrage execution"""
    success: bool
    message: str
    
    # Trade details
    buy_trade: Optional[Trade] = None
    sell_trade: Optional[Trade] = None
    
    # P&L calculation
    gross_profit: float
    total_fees: float
    net_profit: float
    net_profit_percent: float
    
    # Updated portfolio
    new_balance: float
