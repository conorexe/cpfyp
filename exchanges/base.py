"""Base exchange WebSocket client"""
import asyncio
import json
import logging
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

from config import RECONNECT_DELAY, MAX_RECONNECT_ATTEMPTS, SKIP_SSL_VERIFY

logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """Standardized price update from any exchange"""
    exchange: str
    pair: str  # Normalized pair format (e.g., "BTC/USDT")
    bid: float  # Best bid price
    ask: float  # Best ask price
    timestamp: datetime
    
    @property
    def mid(self) -> float:
        """Mid-market price"""
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        """Bid-ask spread percentage"""
        return ((self.ask - self.bid) / self.mid) * 100


class BaseExchange(ABC):
    """Base class for exchange WebSocket connections"""
    
    def __init__(self, name: str, ws_url: str, pairs: list[str], pair_mapping: dict[str, str]):
        self.name = name
        self.ws_url = ws_url
        self.pairs = pairs
        self.pair_mapping = pair_mapping
        self.reverse_mapping = {v: k for k, v in pair_mapping.items()}
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.on_price_update: Optional[Callable[[PriceUpdate], None]] = None
        self._reconnect_attempts = 0
        
    def set_callback(self, callback: Callable[[PriceUpdate], None]):
        """Set callback for price updates"""
        self.on_price_update = callback
        
    @abstractmethod
    async def _subscribe(self):
        """Subscribe to price feeds - exchange specific"""
        pass
    
    @abstractmethod
    def _parse_message(self, data: dict) -> Optional[PriceUpdate]:
        """Parse exchange-specific message to PriceUpdate"""
        pass
    
    async def connect(self):
        """Connect to WebSocket and handle messages"""
        self.running = True
        
        # SSL context for handling certificate issues
        ssl_context = None
        if SKIP_SSL_VERIFY:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        while self.running and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                logger.info(f"[{self.name}] Connecting to WebSocket...")
                async with websockets.connect(self.ws_url, ssl=ssl_context) as ws:
                    self.ws = ws
                    self._reconnect_attempts = 0
                    logger.info(f"[{self.name}] Connected! Subscribing to feeds...")
                    
                    await self._subscribe()
                    
                    async for message in ws:
                        if not self.running:
                            break
                        try:
                            data = json.loads(message)
                            update = self._parse_message(data)
                            if update and self.on_price_update:
                                self.on_price_update(update)
                        except json.JSONDecodeError:
                            logger.warning(f"[{self.name}] Invalid JSON: {message[:100]}")
                        except Exception as e:
                            logger.error(f"[{self.name}] Parse error: {e}")
                            
            except ConnectionClosed as e:
                logger.warning(f"[{self.name}] Connection closed: {e}")
            except Exception as e:
                logger.error(f"[{self.name}] Connection error: {e}")
            
            if self.running:
                self._reconnect_attempts += 1
                logger.info(f"[{self.name}] Reconnecting in {RECONNECT_DELAY}s (attempt {self._reconnect_attempts})...")
                await asyncio.sleep(RECONNECT_DELAY)
        
        if self._reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            logger.error(f"[{self.name}] Max reconnection attempts reached")
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()
            self.ws = None
        logger.info(f"[{self.name}] Disconnected")
