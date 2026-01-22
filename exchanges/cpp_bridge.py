"""Bridge to receive price feeds from C++ engine"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Optional

from .base import PriceUpdate

logger = logging.getLogger(__name__)


class CppBridgeClient:
    """
    Receives price updates from C++ engine via TCP.
    The C++ engine runs as a separate process and streams
    price updates over a TCP connection on port 5555.
    """
    
    def __init__(self, host: str = "localhost", port: int = 5555):
        self.name = "C++ Bridge"
        self.host = host
        self.port = port
        self.running = False
        self.on_price_update: Optional[Callable[[PriceUpdate], None]] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
    def set_callback(self, callback: Callable[[PriceUpdate], None]):
        """Set callback for price updates"""
        self.on_price_update = callback
    
    async def connect(self):
        """Connect to C++ engine and start receiving price updates"""
        self.running = True
        reconnect_delay = 1
        max_reconnect_delay = 30
        
        while self.running:
            try:
                logger.info(f"[C++ Bridge] Connecting to C++ engine at {self.host}:{self.port}...")
                self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
                logger.info("[C++ Bridge] ✅ Connected to C++ engine")
                reconnect_delay = 1  # Reset delay on successful connection
                
                # Read price updates line by line
                while self.running:
                    line = await self.reader.readline()
                    if not line:
                        logger.warning("[C++ Bridge] Connection closed by C++ engine")
                        break
                    
                    try:
                        data = json.loads(line.decode('utf-8'))
                        update = self._parse_update(data)
                        if update and self.on_price_update:
                            self.on_price_update(update)
                    except json.JSONDecodeError as e:
                        logger.debug(f"[C++ Bridge] JSON parse error: {e}")
                    except Exception as e:
                        logger.error(f"[C++ Bridge] Error processing update: {e}")
                
            except ConnectionRefusedError:
                logger.warning(f"[C++ Bridge] Connection refused. Is the C++ engine running?")
            except Exception as e:
                logger.error(f"[C++ Bridge] Connection error: {e}")
            
            if self.running:
                logger.info(f"[C++ Bridge] Reconnecting in {reconnect_delay}s...")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    def _parse_update(self, data: dict) -> Optional[PriceUpdate]:
        """Parse JSON data from C++ engine to PriceUpdate"""
        try:
            return PriceUpdate(
                exchange=data["exchange"],
                pair=data["pair"],
                bid=float(data["bid"]),
                ask=float(data["ask"]),
                timestamp=datetime.fromtimestamp(data["timestamp"] / 1000.0)
            )
        except (KeyError, ValueError) as e:
            logger.debug(f"[C++ Bridge] Parse error: {e}")
            return None
    
    async def disconnect(self):
        """Disconnect from C++ engine"""
        self.running = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        logger.info("[C++ Bridge] Disconnected from C++ engine")


def create_cpp_bridge_client() -> CppBridgeClient:
    """Create a single bridge client that receives from all C++ exchange clients"""
    return CppBridgeClient()
