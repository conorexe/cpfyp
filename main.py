"""
Crypto Arbitrage Bot - Main Entry Point

This bot connects to multiple cryptocurrency exchanges via WebSocket,
monitors real-time price feeds, and identifies arbitrage opportunities.
"""
import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from config import WEB_HOST, WEB_PORT, TRADING_PAIRS, MODE, ENABLE_TRIANGULAR_ARBITRAGE
from exchanges import (
    BinanceExchange, KrakenExchange, CoinbaseExchange, 
    BybitExchange, OKXExchange, 
    create_simulated_exchanges, create_cpp_bridge_client
)
from engine import ArbitrageEngine
from engine_triangular import TriangularArbitrageEngine
from dashboard import app, manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Reduce noise from libraries
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('uvicorn.access').setLevel(logging.WARNING)


class ArbitrageBot:
    """Main bot orchestrator"""
    
    def __init__(self, mode: str = "python"):
        self.engine = ArbitrageEngine()
        self.triangular_engine = TriangularArbitrageEngine() if ENABLE_TRIANGULAR_ARBITRAGE else None
        self.mode = mode
        
        if mode == "simulation":
            # Use simulated exchanges when network is restricted
            self.exchanges = create_simulated_exchanges()
            logger.info("🎮 Running in SIMULATION MODE with mock data")
        elif mode == "cpp":
            # Use C++ engine via bridge (high performance)
            self.exchanges = [create_cpp_bridge_client()]
            logger.info("⚡ Running with C++ ENGINE (high performance mode)")
        else:
            # Use Python WebSocket clients
            self.exchanges = [
                BybitExchange(),
                OKXExchange(),
                BinanceExchange(),
            ]
            logger.info("🐍 Running with Python WebSocket clients")
        
        self.tasks: list[asyncio.Task] = []
        self.running = False
        
    def setup(self):
        """Setup exchange callbacks and dashboard"""
        # Connect engines to dashboard
        manager.set_engine(self.engine)
        if self.triangular_engine:
            manager.set_triangular_engine(self.triangular_engine)
        
        # Set callback for each exchange
        for exchange in self.exchanges:
            exchange.set_callback(self._process_price_update)
            
        logger.info(f"Bot configured with {len(self.exchanges)} exchanges")
        logger.info(f"Monitoring pairs: {', '.join(TRADING_PAIRS)}")
        if self.triangular_engine:
            logger.info(f"🔺 Triangular arbitrage enabled")
    
    def _process_price_update(self, update):
        """Process price update and send to all engines"""
        # Send to simple arbitrage engine
        self.engine.process_price_update(update)
        
        # Send to triangular arbitrage engine
        if self.triangular_engine:
            self.triangular_engine.update_price(
                update.exchange,
                update.pair,
                update.bid,
                update.ask
            )
    
    async def start(self):
        """Start all exchange connections"""
        self.running = True
        self.setup()
        
        logger.info("=" * 60)
        logger.info("🚀 CRYPTO ARBITRAGE BOT STARTING")
        if self.mode == "cpp":
            logger.info("⚡ HIGH PERFORMANCE MODE - Using C++ engine")
            logger.info("⚠️  Make sure to start the C++ engine first:")
            logger.info("   cd cpp/build && ./arb_bot")
        elif self.mode == "simulation":
            logger.info("🎮 SIMULATION MODE - Using mock price data")
        logger.info("=" * 60)
        
        # Start exchange connections
        for exchange in self.exchanges:
            task = asyncio.create_task(exchange.connect())
            self.tasks.append(task)
            logger.info(f"Started {exchange.name} connection task")
        
        logger.info(f"Dashboard available at http://localhost:{WEB_PORT}")
        logger.info("=" * 60)
    
    async def stop(self):
        """Stop all exchange connections"""
        self.running = False
        logger.info("Shutting down...")
        
        # Disconnect exchanges
        for exchange in self.exchanges:
            await exchange.disconnect()
        
        # Cancel tasks
        for task in self.tasks:
            task.cancel()
        
        logger.info("Bot stopped")


# Global bot instance
bot = ArbitrageBot(mode=MODE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler"""
    await bot.start()
    yield
    await bot.stop()


# Update app lifespan
app.router.lifespan_context = lifespan


def handle_sigint(sig, frame):
    """Handle Ctrl+C gracefully"""
    logger.info("Received SIGINT, shutting down...")
    sys.exit(0)


def main():
    """Main entry point"""
    # Handle Ctrl+C
    signal.signal(signal.SIGINT, handle_sigint)
    
    mode_descriptions = {
        "cpp": ("C++ ENGINE (High Performance)", "Binance, Kraken, Coinbase via C++"),
        "python": ("Python WebSockets", "Bybit, OKX, Binance"),
        "simulation": ("SIMULATION (Mock Data)", "Simulated Exchanges"),
    }
    
    mode_text, exch_text = mode_descriptions.get(MODE, ("UNKNOWN", "N/A"))
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     ⚡ CRYPTO ARBITRAGE BOT MVP ⚡                        ║
    ║                                                           ║
    ║     Mode: {mode_text:<47} ║
    ║     Exchanges: {exch_text:<42} ║
    ║                                                           ║
    ║     Dashboard: http://localhost:8000                      ║
    ║                                                           ║
    ║     Edit MODE in config.py to switch modes                ║
    ║     Options: "cpp", "python", "simulation"                ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # Run FastAPI server (which starts bot via lifespan)
    uvicorn.run(
        app,
        host=WEB_HOST,
        port=WEB_PORT,
        log_level="warning"
    )


if __name__ == "__main__":
    main()
