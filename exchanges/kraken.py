"""Kraken WebSocket client"""
import json
import logging
from datetime import datetime
from typing import Optional

from .base import BaseExchange, PriceUpdate
from config import EXCHANGE_WS_URLS, PAIR_MAPPINGS, TRADING_PAIRS

logger = logging.getLogger(__name__)


class KrakenExchange(BaseExchange):
    """Kraken WebSocket client for real-time price feeds (v2 API)"""
    
    def __init__(self):
        super().__init__(
            name="Kraken",
            ws_url=EXCHANGE_WS_URLS["kraken"],
            pairs=TRADING_PAIRS,
            pair_mapping=PAIR_MAPPINGS["kraken"]
        )
    
    async def _subscribe(self):
        """Subscribe to Kraken ticker feed (v2 API)"""
        pairs = [self.pair_mapping.get(p) for p in self.pairs if p in self.pair_mapping]
        
        # Kraken v2 API subscription format
        subscribe_msg = {
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": pairs
            }
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[{self.name}] Subscription sent for {len(pairs)} pairs")
    
    def _parse_message(self, data) -> Optional[PriceUpdate]:
        """Parse Kraken v2 ticker message"""
        try:
            # Skip non-data messages (status, heartbeat, subscription confirmations)
            if not isinstance(data, dict):
                return None
            
            # v2 API format: {"channel":"ticker","type":"update","data":[{"symbol":"BTC/USD",...}]}
            channel = data.get("channel")
            msg_type = data.get("type")
            
            if channel != "ticker":
                return None
            
            # Skip snapshot, only process updates (or accept both)
            if msg_type not in ("update", "snapshot"):
                return None
            
            ticker_list = data.get("data", [])
            
            updates = []
            for ticker in ticker_list:
                symbol = ticker.get("symbol")
                if not symbol:
                    continue
                
                # Get normalized pair
                normalized_pair = self.reverse_mapping.get(symbol)
                if not normalized_pair:
                    continue
                
                # v2 API: bid/ask are direct values
                bid = ticker.get("bid")
                ask = ticker.get("ask")
                
                if bid is None or ask is None:
                    continue
                
                return PriceUpdate(
                    exchange=self.name,
                    pair=normalized_pair,
                    bid=float(bid),
                    ask=float(ask),
                    timestamp=datetime.now()
                )
            
            return None
            
        except (KeyError, ValueError, IndexError, TypeError) as e:
            logger.debug(f"[{self.name}] Parse error: {e}")
            return None
