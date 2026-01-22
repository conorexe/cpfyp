"""Binance WebSocket client"""
import json
import logging
from datetime import datetime
from typing import Optional

from .base import BaseExchange, PriceUpdate
from config import EXCHANGE_WS_URLS, PAIR_MAPPINGS, TRADING_PAIRS

logger = logging.getLogger(__name__)


class BinanceExchange(BaseExchange):
    """Binance WebSocket client for real-time price feeds"""
    
    def __init__(self):
        # Build combined stream URL for all pairs
        pairs = [PAIR_MAPPINGS["binance"].get(p) for p in TRADING_PAIRS if p in PAIR_MAPPINGS["binance"]]
        streams = "/".join([f"{p}@bookTicker" for p in pairs])
        ws_url = f"{EXCHANGE_WS_URLS['binance']}/{streams}"
        
        super().__init__(
            name="Binance",
            ws_url=ws_url,
            pairs=TRADING_PAIRS,
            pair_mapping=PAIR_MAPPINGS["binance"]
        )
    
    async def _subscribe(self):
        """Binance uses URL-based subscription, no message needed"""
        logger.info(f"[{self.name}] Subscribed via URL stream")
    
    def _parse_message(self, data: dict) -> Optional[PriceUpdate]:
        """Parse Binance bookTicker message"""
        try:
            # Binance bookTicker format:
            # {"u":12345,"s":"BTCUSDT","b":"50000.00","B":"1.5","a":"50001.00","A":"2.0"}
            if "s" not in data or "b" not in data or "a" not in data:
                return None
            
            symbol = data["s"].lower()
            normalized_pair = self.reverse_mapping.get(symbol)
            
            if not normalized_pair:
                return None
            
            return PriceUpdate(
                exchange=self.name,
                pair=normalized_pair,
                bid=float(data["b"]),
                ask=float(data["a"]),
                timestamp=datetime.now()
            )
        except (KeyError, ValueError) as e:
            logger.debug(f"[{self.name}] Parse error: {e}")
            return None
