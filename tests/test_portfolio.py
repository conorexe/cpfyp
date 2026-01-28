"""
Tests for portfolio management module.
"""

import pytest
from src.portfolio.service import PortfolioService
from src.portfolio.models import (
    PortfolioCreate, PortfolioUpdate,
    TradeCreate, TradeSide, TradeType,
    ExecuteArbitrageRequest,
)


class TestPortfolioService:
    """Tests for PortfolioService"""
    
    def test_create_portfolio(self, fresh_portfolio_service: PortfolioService):
        """Test portfolio creation"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(
                name="Test Portfolio",
                description="For testing",
                initial_balance=5000,
            ),
        )
        
        assert portfolio.name == "Test Portfolio"
        assert portfolio.initial_balance == 5000
        assert portfolio.current_balance == 5000
        assert portfolio.is_default  # First portfolio is default
    
    def test_get_default_portfolio(self, fresh_portfolio_service: PortfolioService):
        """Test getting user's default portfolio"""
        # Create portfolio
        fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="First"),
        )
        
        fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Second"),
        )
        
        default = fresh_portfolio_service.get_default_portfolio(1)
        
        assert default is not None
        assert default.name == "First"  # First one should be default
    
    def test_initial_position(self, fresh_portfolio_service: PortfolioService):
        """Test that portfolio starts with USDT position"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Test", initial_balance=10000),
        )
        
        positions = fresh_portfolio_service.get_positions(portfolio.id)
        
        assert len(positions) == 1
        assert positions[0].asset == "USDT"
        assert positions[0].quantity == 10000
    
    def test_execute_trade_buy(self, fresh_portfolio_service: PortfolioService):
        """Test executing a buy trade"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Trade Test", initial_balance=10000),
        )
        
        trade = fresh_portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            user_id=1,
            trade_data=TradeCreate(
                pair="BTC/USDT",
                side=TradeSide.BUY,
                quantity=0.1,
                price=65000,
                exchange="binance",
                trade_type=TradeType.MANUAL,
            ),
            fee_percent=0.1,
        )
        
        assert trade is not None
        assert trade.side == TradeSide.BUY
        assert trade.quantity == 0.1
        
        # Check positions
        positions = fresh_portfolio_service.get_positions(portfolio.id)
        btc_position = next((p for p in positions if p.asset == "BTC"), None)
        usdt_position = next((p for p in positions if p.asset == "USDT"), None)
        
        assert btc_position is not None
        assert btc_position.quantity == 0.1
        
        # USDT should be reduced by trade value + fee
        assert usdt_position.quantity < 10000
    
    def test_execute_trade_insufficient_balance(self, fresh_portfolio_service: PortfolioService):
        """Test that trades fail with insufficient balance"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Low Balance", initial_balance=100),
        )
        
        trade = fresh_portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            user_id=1,
            trade_data=TradeCreate(
                pair="BTC/USDT",
                side=TradeSide.BUY,
                quantity=1,  # Would cost ~$65000
                price=65000,
                exchange="binance",
            ),
        )
        
        assert trade is None
    
    def test_execute_arbitrage(self, fresh_portfolio_service: PortfolioService):
        """Test executing an arbitrage opportunity"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Arb Test", initial_balance=100000),
        )
        
        result = fresh_portfolio_service.execute_arbitrage(
            portfolio_id=portfolio.id,
            user_id=1,
            request=ExecuteArbitrageRequest(
                buy_exchange="binance",
                sell_exchange="coinbase",
                pair="BTC/USDT",
                quantity=0.1,
                buy_price=65000,
                sell_price=65200,
                buy_fee_percent=0.1,
                sell_fee_percent=0.1,
            ),
        )
        
        assert result.success
        assert result.net_profit > 0
        assert result.buy_trade is not None
        assert result.sell_trade is not None
    
    def test_execute_unprofitable_arbitrage(self, fresh_portfolio_service: PortfolioService):
        """Test that unprofitable arbitrage is rejected"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Fail Arb", initial_balance=100000),
        )
        
        result = fresh_portfolio_service.execute_arbitrage(
            portfolio_id=portfolio.id,
            user_id=1,
            request=ExecuteArbitrageRequest(
                buy_exchange="binance",
                sell_exchange="coinbase",
                pair="BTC/USDT",
                quantity=0.1,
                buy_price=65200,  # Buying higher than selling
                sell_price=65000,
                buy_fee_percent=0.1,
                sell_fee_percent=0.1,
            ),
        )
        
        assert not result.success
        assert result.net_profit < 0
    
    def test_portfolio_summary(self, fresh_portfolio_service: PortfolioService):
        """Test portfolio summary calculation"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="Summary Test", initial_balance=10000),
        )
        
        # Execute some trades
        fresh_portfolio_service.execute_trade(
            portfolio_id=portfolio.id,
            user_id=1,
            trade_data=TradeCreate(
                pair="BTC/USDT",
                side=TradeSide.BUY,
                quantity=0.01,
                price=65000,
                exchange="binance",
            ),
        )
        
        summary = fresh_portfolio_service.get_portfolio_summary(
            portfolio_id=portfolio.id,
            user_id=1,
        )
        
        assert summary is not None
        assert summary.total_value > 0
        assert len(summary.positions) > 0
        assert summary.total_trades > 0
    
    def test_trade_history(self, fresh_portfolio_service: PortfolioService):
        """Test trade history retrieval"""
        portfolio = fresh_portfolio_service.create_portfolio(
            user_id=1,
            data=PortfolioCreate(name="History Test", initial_balance=100000),
        )
        
        # Execute multiple trades
        for i in range(5):
            fresh_portfolio_service.execute_trade(
                portfolio_id=portfolio.id,
                user_id=1,
                trade_data=TradeCreate(
                    pair="BTC/USDT",
                    side=TradeSide.BUY,
                    quantity=0.01,
                    price=65000 + i * 100,
                    exchange="binance",
                ),
            )
        
        trades = fresh_portfolio_service.get_trades(portfolio.id, limit=10)
        
        assert len(trades) == 5
        # Should be sorted by timestamp descending
        assert trades[0].timestamp >= trades[-1].timestamp


class TestPortfolioEndpoints:
    """Tests for portfolio API endpoints"""
    
    def test_list_portfolios_requires_auth(self, client):
        """Test that portfolio endpoints require authentication"""
        response = client.get("/api/portfolio")
        assert response.status_code == 401
    
    def test_create_portfolio_requires_auth(self, client):
        """Test that creating portfolio requires authentication"""
        response = client.post(
            "/api/portfolio",
            json={"name": "Test", "initial_balance": 10000},
        )
        assert response.status_code == 401
