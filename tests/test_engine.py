"""
Tests for arbitrage engine.
"""

import pytest
from datetime import datetime

from engine import ArbitrageEngine
from exchanges.base import PriceUpdate


class TestArbitrageEngine:
    """Tests for ArbitrageEngine"""
    
    @pytest.fixture
    def engine(self):
        """Create a fresh engine instance"""
        return ArbitrageEngine(min_profit_threshold=0.01)
    
    def test_process_price_update(self, engine):
        """Test processing price updates"""
        update = PriceUpdate(
            exchange="binance",
            pair="BTC/USDT",
            bid=65000.0,
            ask=65010.0,
            timestamp=datetime.now(),
        )
        
        engine.process_price_update(update)
        
        assert "BTC/USDT" in engine.prices
        assert "binance" in engine.prices["BTC/USDT"]
        assert engine.prices["BTC/USDT"]["binance"].bid == 65000.0
    
    def test_detect_arbitrage_opportunity(self, engine):
        """Test arbitrage detection between two exchanges"""
        # Binance price
        engine.process_price_update(PriceUpdate(
            exchange="binance",
            pair="BTC/USDT",
            bid=65000.0,
            ask=65010.0,
            timestamp=datetime.now(),
        ))
        
        # Coinbase price (higher)
        engine.process_price_update(PriceUpdate(
            exchange="coinbase",
            pair="BTC/USDT",
            bid=65150.0,  # Higher bid than binance ask
            ask=65160.0,
            timestamp=datetime.now(),
        ))
        
        # Should detect opportunity: buy @ binance ask, sell @ coinbase bid
        assert len(engine.opportunities) > 0
        
        opp = engine.opportunities[0]
        assert opp.pair == "BTC/USDT"
        assert opp.buy_exchange == "binance"
        assert opp.sell_exchange == "coinbase"
        assert opp.profit_percent > 0
    
    def test_no_opportunity_when_spread_too_small(self, engine):
        """Test that small spreads don't trigger opportunities"""
        # Set high threshold
        engine.min_profit_threshold = 1.0  # 1%
        
        # Similar prices
        engine.process_price_update(PriceUpdate(
            exchange="binance",
            pair="BTC/USDT",
            bid=65000.0,
            ask=65010.0,
            timestamp=datetime.now(),
        ))
        
        engine.process_price_update(PriceUpdate(
            exchange="coinbase",
            pair="BTC/USDT",
            bid=65005.0,
            ask=65015.0,
            timestamp=datetime.now(),
        ))
        
        # Spread is too small
        assert len(engine.opportunities) == 0
    
    def test_opportunity_callback(self, engine):
        """Test that opportunity callback is called"""
        opportunities_received = []
        
        def callback(opp):
            opportunities_received.append(opp)
        
        engine.on_opportunity(callback)
        
        # Create opportunity
        engine.process_price_update(PriceUpdate(
            exchange="binance",
            pair="BTC/USDT",
            bid=65000.0,
            ask=65010.0,
            timestamp=datetime.now(),
        ))
        
        engine.process_price_update(PriceUpdate(
            exchange="coinbase",
            pair="BTC/USDT",
            bid=65200.0,
            ask=65210.0,
            timestamp=datetime.now(),
        ))
        
        assert len(opportunities_received) > 0
    
    def test_history_limit(self, engine):
        """Test that history is limited to 100 entries"""
        # Create many opportunities
        for i in range(150):
            engine.process_price_update(PriceUpdate(
                exchange="binance",
                pair="BTC/USDT",
                bid=65000.0,
                ask=65010.0 + i * 10,
                timestamp=datetime.now(),
            ))
            
            engine.process_price_update(PriceUpdate(
                exchange="coinbase",
                pair="BTC/USDT",
                bid=65200.0 + i * 10,
                ask=65210.0 + i * 10,
                timestamp=datetime.now(),
            ))
        
        # History should be capped
        assert len(engine.history) <= 100
    
    def test_get_state(self, engine):
        """Test state serialization"""
        engine.process_price_update(PriceUpdate(
            exchange="binance",
            pair="BTC/USDT",
            bid=65000.0,
            ask=65010.0,
            timestamp=datetime.now(),
        ))
        
        state = engine.get_state()
        
        assert "prices" in state
        assert "opportunities" in state
        assert "history" in state
        assert "config" in state
    
    def test_multiple_pairs(self, engine):
        """Test handling multiple trading pairs"""
        pairs = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        for pair in pairs:
            engine.process_price_update(PriceUpdate(
                exchange="binance",
                pair=pair,
                bid=100.0,
                ask=100.1,
                timestamp=datetime.now(),
            ))
        
        assert len(engine.prices) == 3
        for pair in pairs:
            assert pair in engine.prices
