"""Bybit WebSocket client"""
import json
import logging
from datetime import datetime
from typing import Optional

from .base import BaseExchange, PriceUpdate
from config import TRADING_PAIRS

logger = logging.getLogger(__name__)

# Bybit-specific configuration
BYBIT_WS_URL = "wss://stream.bybit.com/v5/public/spot"
BYBIT_PAIR_MAPPING = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "SOL/USDT": "SOLUSDT",
    "XRP/USDT": "XRPUSDT",
}


class BybitExchange(BaseExchange):
    """Bybit WebSocket client for real-time price feeds"""
    
    def __init__(self):
        super().__init__(
            name="Bybit",
            ws_url=BYBIT_WS_URL,
            pairs=TRADING_PAIRS,
            pair_mapping=BYBIT_PAIR_MAPPING
        )
    
    async def _subscribe(self):
        """Subscribe to Bybit ticker feed"""
        symbols = [self.pair_mapping.get(p) for p in self.pairs if p in self.pair_mapping]
        
        # Bybit v5 subscription format
        subscribe_msg = {
            "op": "subscribe",
            "args": [f"tickers.{symbol}" for symbol in symbols]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[{self.name}] Subscription sent for {len(symbols)} pairs")
    
    def _parse_message(self, data: dict) -> Optional[PriceUpdate]:
        """Parse Bybit ticker message"""
        try:
            # Bybit v5 ticker format:
            # {"topic":"tickers.BTCUSDT","type":"snapshot","data":{"symbol":"BTCUSDT","bid1Price":"50000","ask1Price":"50001",...}}
            
            topic = data.get("topic", "")
            if not topic.startswith("tickers."):
                return None
            
            ticker_data = data.get("data")
            if not ticker_data:
                return None
            
            symbol = ticker_data.get("symbol")
            if not symbol:
                return None
            
            normalized_pair = self.reverse_mapping.get(symbol)
            if not normalized_pair:
                return None
            
            bid = ticker_data.get("bid1Price")
            ask = ticker_data.get("ask1Price")
            
            if not bid or not ask:
                return None
            
            return PriceUpdate(
                exchange=self.name,
                pair=normalized_pair,
                bid=float(bid),
                ask=float(ask),
                timestamp=datetime.now()
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"[{self.name}] Parse error: {e}")
            return None
