"""
Portfolio API routes.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from src.auth.dependencies import get_current_active_user
from src.auth.models import User

from .models import (
    Portfolio, PortfolioCreate, PortfolioUpdate, PortfolioSummary,
    Position, Trade, TradeCreate,
    ExecuteArbitrageRequest, ExecuteArbitrageResponse,
)
from .service import portfolio_service

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


# Portfolio endpoints

@router.get("", response_model=List[Portfolio])
async def list_portfolios(
    current_user: User = Depends(get_current_active_user),
):
    """
    List all portfolios for the current user.
    """
    return portfolio_service.get_user_portfolios(current_user.id)


@router.post("", response_model=Portfolio, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    data: PortfolioCreate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a new portfolio.
    
    Initial balance defaults to $10,000 USD.
    """
    return portfolio_service.create_portfolio(current_user.id, data)


@router.get("/default", response_model=PortfolioSummary)
async def get_default_portfolio(
    current_user: User = Depends(get_current_active_user),
):
    """
    Get the user's default portfolio with summary statistics.
    """
    portfolio = portfolio_service.get_default_portfolio(current_user.id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No portfolio found. Create one first.",
        )
    
    summary = portfolio_service.get_portfolio_summary(portfolio.id, current_user.id)
    return summary


@router.get("/{portfolio_id}", response_model=PortfolioSummary)
async def get_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific portfolio with full summary.
    """
    summary = portfolio_service.get_portfolio_summary(portfolio_id, current_user.id)
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    return summary


@router.put("/{portfolio_id}", response_model=Portfolio)
async def update_portfolio(
    portfolio_id: int,
    data: PortfolioUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Update portfolio settings.
    """
    portfolio = portfolio_service.update_portfolio(portfolio_id, current_user.id, data)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    return portfolio


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """
    Delete a portfolio and all its data.
    """
    success = portfolio_service.delete_portfolio(portfolio_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )


# Position endpoints

@router.get("/{portfolio_id}/positions", response_model=List[Position])
async def list_positions(
    portfolio_id: int,
    current_user: User = Depends(get_current_active_user),
):
    """
    List all positions in a portfolio.
    """
    portfolio = portfolio_service.get_portfolio(portfolio_id, current_user.id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return portfolio_service.get_positions(portfolio_id)


@router.get("/{portfolio_id}/positions/{asset}", response_model=Position)
async def get_position(
    portfolio_id: int,
    asset: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    Get a specific position by asset.
    """
    portfolio = portfolio_service.get_portfolio(portfolio_id, current_user.id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    position = portfolio_service.get_position(portfolio_id, asset)
    if not position:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No position in {asset}",
        )
    
    return position


# Trade endpoints

@router.get("/{portfolio_id}/trades", response_model=List[Trade])
async def list_trades(
    portfolio_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_active_user),
):
    """
    List trade history for a portfolio.
    """
    portfolio = portfolio_service.get_portfolio(portfolio_id, current_user.id)
    if not portfolio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio not found",
        )
    
    return portfolio_service.get_trades(portfolio_id, limit=limit)


@router.post("/{portfolio_id}/trades", response_model=Trade, status_code=status.HTTP_201_CREATED)
async def create_trade(
    portfolio_id: int,
    trade_data: TradeCreate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Execute a manual trade (paper trading).
    """
    trade = portfolio_service.execute_trade(portfolio_id, current_user.id, trade_data)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trade failed. Check balance and position.",
        )
    return trade


@router.post("/{portfolio_id}/arbitrage", response_model=ExecuteArbitrageResponse)
async def execute_arbitrage(
    portfolio_id: int,
    request: ExecuteArbitrageRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Execute an arbitrage opportunity (buy + sell simulation).
    
    This simulates:
    1. Buy on the lower-priced exchange
    2. Sell on the higher-priced exchange
    3. Account for fees on both sides
    """
    result = portfolio_service.execute_arbitrage(portfolio_id, current_user.id, request)
    return result
