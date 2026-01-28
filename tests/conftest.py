"""
Pytest configuration and fixtures for MarketScout tests.
"""

import pytest
import asyncio
from datetime import datetime
from typing import Generator, AsyncGenerator

from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import application
import sys
sys.path.insert(0, '.')

from dashboard import app
from src.auth.service import auth_service, AuthService
from src.auth.models import UserCreate
from src.portfolio.service import portfolio_service, PortfolioService
from src.portfolio.models import PortfolioCreate


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create synchronous test client"""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create asynchronous test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def fresh_auth_service() -> AuthService:
    """Create a fresh auth service for isolated tests"""
    return AuthService()


@pytest.fixture
def fresh_portfolio_service() -> PortfolioService:
    """Create a fresh portfolio service for isolated tests"""
    return PortfolioService()


@pytest.fixture
def test_user(fresh_auth_service: AuthService):
    """Create a test user and return credentials"""
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        password="TestPass123",
    )
    user = fresh_auth_service.create_user(user_data)
    return {
        "user": user,
        "password": "TestPass123",
        "auth_service": fresh_auth_service,
    }


@pytest.fixture
def auth_headers(test_user):
    """Get authentication headers for test user"""
    auth_service = test_user["auth_service"]
    user_db = auth_service.get_user(test_user["user"].username)
    token = auth_service.create_access_token(user_db)
    return {"Authorization": f"Bearer {token.access_token}"}


@pytest.fixture
def test_portfolio(fresh_portfolio_service: PortfolioService, test_user):
    """Create a test portfolio"""
    portfolio = fresh_portfolio_service.create_portfolio(
        user_id=test_user["user"].id,
        data=PortfolioCreate(
            name="Test Portfolio",
            description="Portfolio for testing",
            initial_balance=10000,
        ),
    )
    return {
        "portfolio": portfolio,
        "service": fresh_portfolio_service,
        "user": test_user["user"],
    }


# Sample data fixtures

@pytest.fixture
def sample_price_update():
    """Sample price update data"""
    return {
        "exchange": "binance",
        "pair": "BTC/USDT",
        "bid": 65000.0,
        "ask": 65010.0,
        "timestamp": datetime.now(),
    }


@pytest.fixture
def sample_opportunity():
    """Sample arbitrage opportunity data"""
    return {
        "pair": "BTC/USDT",
        "buy_exchange": "binance",
        "sell_exchange": "coinbase",
        "buy_price": 65000.0,
        "sell_price": 65100.0,
        "profit_percent": 0.154,
        "timestamp": datetime.now(),
    }


@pytest.fixture
def sample_triangular_opportunity():
    """Sample triangular arbitrage opportunity"""
    return {
        "exchange": "binance",
        "base_currency": "USDT",
        "pairs": ["BTC/USDT", "ETH/BTC", "ETH/USDT"],
        "sides": ["buy", "buy", "sell"],
        "profit_percent": 0.25,
        "start_amount": 10000,
        "end_amount": 10025,
    }
