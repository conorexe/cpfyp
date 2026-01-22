"""Coinbase WebSocket client"""
import json
import logging
from datetime import datetime
from typing import Optional

from .base import BaseExchange, PriceUpdate
from config import EXCHANGE_WS_URLS, PAIR_MAPPINGS, TRADING_PAIRS

logger = logging.getLogger(__name__)


class CoinbaseExchange(BaseExchange):
    """Coinbase Advanced Trade WebSocket client for real-time price feeds"""
    
    def __init__(self):
        super().__init__(
            name="Coinbase",
            ws_url=EXCHANGE_WS_URLS["coinbase"],
            pairs=TRADING_PAIRS,
            pair_mapping=PAIR_MAPPINGS["coinbase"]
        )
        self._current_prices: dict[str, dict] = {}  # Track bid/ask separately
    
    async def _subscribe(self):
        """Subscribe to Coinbase Advanced Trade ticker feed"""
        product_ids = [self.pair_mapping.get(p) for p in self.pairs if p in self.pair_mapping]
        
        # Advanced Trade API subscription format
        subscribe_msg = {
            "type": "subscribe",
            "product_ids": product_ids,
            "channel": "ticker"
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[{self.name}] Subscription sent for {len(product_ids)} pairs")
    
    def _parse_message(self, data: dict) -> Optional[PriceUpdate]:
        """Parse Coinbase Advanced Trade ticker message"""
        try:
            # Handle different message types
            msg_type = data.get("type") or data.get("channel")
            
            # Advanced Trade API format: 
            # {"channel":"ticker","events":[{"type":"update","tickers":[{"product_id":"BTC-USD",...}]}]}
            if msg_type == "ticker" and "events" in data:
                for event in data.get("events", []):
                    for ticker in event.get("tickers", []):
                        product_id = ticker.get("product_id")
                        if not product_id:
                            continue
                        
                        normalized_pair = self.reverse_mapping.get(product_id)
                        if not normalized_pair:
                            continue
                        
                        # Advanced Trade uses best_bid_quantity, best_ask_quantity, price
                        bid = ticker.get("best_bid") or ticker.get("price")
                        ask = ticker.get("best_ask") or ticker.get("price")
                        
                        if bid and ask:
                            return PriceUpdate(
                                exchange=self.name,
                                pair=normalized_pair,
                                bid=float(bid),
                                ask=float(ask),
                                timestamp=datetime.now()
                            )
            
            # Legacy Exchange API format (fallback)
            if data.get("type") == "ticker":
                product_id = data.get("product_id")
                if not product_id:
                    return None
                
                normalized_pair = self.reverse_mapping.get(product_id)
                if not normalized_pair:
                    return None
                
                bid = data.get("best_bid")
                ask = data.get("best_ask")
                
                if not bid or not ask:
                    return None
                
                return PriceUpdate(
                    exchange=self.name,
                    pair=normalized_pair,
                    bid=float(bid),
                    ask=float(ask),
                    timestamp=datetime.now()
                )
            
            return None
            
        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"[{self.name}] Parse error: {e}")
            return None
