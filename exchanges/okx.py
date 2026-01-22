"""OKX WebSocket client"""
import json
import logging
from datetime import datetime
from typing import Optional

from .base import BaseExchange, PriceUpdate
from config import TRADING_PAIRS

logger = logging.getLogger(__name__)

# OKX-specific configuration
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"
OKX_PAIR_MAPPING = {
    "BTC/USDT": "BTC-USDT",
    "ETH/USDT": "ETH-USDT",
    "SOL/USDT": "SOL-USDT",
    "XRP/USDT": "XRP-USDT",
}


class OKXExchange(BaseExchange):
    """OKX WebSocket client for real-time price feeds"""
    
    def __init__(self):
        super().__init__(
            name="OKX",
            ws_url=OKX_WS_URL,
            pairs=TRADING_PAIRS,
            pair_mapping=OKX_PAIR_MAPPING
        )
    
    async def _subscribe(self):
        """Subscribe to OKX ticker feed"""
        inst_ids = [self.pair_mapping.get(p) for p in self.pairs if p in self.pair_mapping]
        
        # OKX subscription format
        subscribe_msg = {
            "op": "subscribe",
            "args": [{"channel": "tickers", "instId": inst_id} for inst_id in inst_ids]
        }
        
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"[{self.name}] Subscription sent for {len(inst_ids)} pairs")
    
    def _parse_message(self, data: dict) -> Optional[PriceUpdate]:
        """Parse OKX ticker message"""
        try:
            # OKX ticker format:
            # {"arg":{"channel":"tickers","instId":"BTC-USDT"},"data":[{"instId":"BTC-USDT","bidPx":"50000","askPx":"50001",...}]}
            
            if "data" not in data:
                return None
            
            for ticker in data.get("data", []):
                inst_id = ticker.get("instId")
                if not inst_id:
                    continue
                
                normalized_pair = self.reverse_mapping.get(inst_id)
                if not normalized_pair:
                    continue
                
                bid = ticker.get("bidPx")
                ask = ticker.get("askPx")
                
                if not bid or not ask:
                    continue
                
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
