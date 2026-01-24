"""Web dashboard for the arbitrage bot"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from engine import ArbitrageEngine

logger = logging.getLogger(__name__)

app = FastAPI(title="Crypto Arbitrage Bot", version="1.0.0")


class DashboardManager:
    """Manages WebSocket connections to dashboard clients"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.engine: Optional[ArbitrageEngine] = None
        self.triangular_engine = None
        self.orderbook_engine = None
        self.statistical_engine = None
        self.ml_engine = None
        self.tick_storage = None
        # New arbitrage engines
        self.cross_triangular_engine = None
        self.futures_spot_engine = None
        self.dex_cex_engine = None
        self.latency_engine = None
        
    def set_engine(self, engine: ArbitrageEngine):
        """Set the arbitrage engine and register callbacks"""
        self.engine = engine
        engine.on_price_update(self._on_price_update)
        engine.on_opportunity(self._on_opportunity)
    
    def set_triangular_engine(self, engine):
        """Set the triangular arbitrage engine and register callbacks"""
        self.triangular_engine = engine
        engine.on_opportunity(self._on_triangular_opportunity)
    
    def set_advanced_engines(self, orderbook=None, statistical=None, ml=None, storage=None):
        """Set advanced engines"""
        self.orderbook_engine = orderbook
        self.statistical_engine = statistical
        self.ml_engine = ml
        self.tick_storage = storage
        
        # Register callbacks for advanced engines
        if statistical:
            statistical.on_signal(self._on_stat_arb_signal)
        if ml:
            ml.on_prediction(self._on_ml_prediction)
            ml.on_anomaly(self._on_anomaly)
    
    def set_new_arb_engines(self, cross_triangular=None, futures_spot=None, dex_cex=None, latency=None):
        """Set new arbitrage engines"""
        self.cross_triangular_engine = cross_triangular
        self.futures_spot_engine = futures_spot
        self.dex_cex_engine = dex_cex
        self.latency_engine = latency
        
        # Register callbacks for new engines
        if cross_triangular:
            cross_triangular.on_opportunity(self._on_cross_triangular_opportunity)
        if futures_spot:
            futures_spot.on_opportunity(self._on_futures_spot_opportunity)
        if dex_cex:
            dex_cex.on_opportunity(self._on_dex_cex_opportunity)
        if latency:
            latency.on_opportunity(self._on_latency_opportunity)
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Dashboard client connected. Total: {len(self.active_connections)}")
        
        # Send current state
        if self.engine:
            await websocket.send_json({
                "type": "state",
                "data": self.engine.get_state()
            })
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
    
    def _on_price_update(self, update):
        """Handle price update from engine"""
        asyncio.create_task(self.broadcast({
            "type": "price",
            "data": {
                "exchange": update.exchange,
                "pair": update.pair,
                "bid": update.bid,
                "ask": update.ask,
                "mid": update.mid,
                "timestamp": update.timestamp.isoformat()
            }
        }))
    
    def _on_opportunity(self, opportunity):
        """Handle new opportunity from engine"""
        asyncio.create_task(self.broadcast({
            "type": "opportunity",
            "data": opportunity.to_dict()
        }))
    
    def _on_triangular_opportunity(self, opportunity):
        """Handle new triangular opportunity from engine"""
        asyncio.create_task(self.broadcast({
            "type": "triangular_opportunity",
            "data": opportunity.to_dict()
        }))
    
    def _on_stat_arb_signal(self, signal):
        """Handle statistical arbitrage signal"""
        asyncio.create_task(self.broadcast({
            "type": "stat_arb_signal",
            "data": signal.to_dict()
        }))
    
    def _on_ml_prediction(self, prediction):
        """Handle ML prediction"""
        asyncio.create_task(self.broadcast({
            "type": "ml_prediction",
            "data": prediction.to_dict()
        }))
    
    def _on_anomaly(self, anomaly):
        """Handle detected anomaly"""
        asyncio.create_task(self.broadcast({
            "type": "anomaly",
            "data": anomaly.to_dict()
        }))
    
    def _on_cross_triangular_opportunity(self, opportunity):
        """Handle cross-exchange triangular opportunity"""
        asyncio.create_task(self.broadcast({
            "type": "cross_triangular_opportunity",
            "data": opportunity.to_dict()
        }))
    
    def _on_futures_spot_opportunity(self, opportunity):
        """Handle futures-spot basis opportunity"""
        asyncio.create_task(self.broadcast({
            "type": "futures_spot_opportunity",
            "data": opportunity.to_dict()
        }))
    
    def _on_dex_cex_opportunity(self, opportunity):
        """Handle DEX/CEX arbitrage opportunity"""
        asyncio.create_task(self.broadcast({
            "type": "dex_cex_opportunity",
            "data": opportunity.to_dict()
        }))
    
    def _on_latency_opportunity(self, opportunity):
        """Handle latency arbitrage opportunity"""
        asyncio.create_task(self.broadcast({
            "type": "latency_opportunity",
            "data": opportunity.to_dict()
        }))


manager = DashboardManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/api/state")
async def get_state():
    """Get current arbitrage state"""
    if not manager.engine:
        return {"error": "Engine not initialized"}
    
    state = manager.engine.get_state()
    
    # Add triangular arbitrage data
    if manager.triangular_engine:
        state.update(manager.triangular_engine.get_state())
    
    # Add advanced engine data
    if manager.orderbook_engine:
        state["orderbook"] = manager.orderbook_engine.get_state()
    
    if manager.statistical_engine:
        state["statistical"] = manager.statistical_engine.get_state()
    
    if manager.ml_engine:
        state["ml"] = manager.ml_engine.get_state()
    
    if manager.tick_storage:
        state["storage"] = manager.tick_storage.get_state()
    
    # Add new arbitrage engine data
    if manager.cross_triangular_engine:
        state["cross_triangular"] = manager.cross_triangular_engine.get_state()
    
    if manager.futures_spot_engine:
        state["futures_spot"] = manager.futures_spot_engine.get_state()
    
    if manager.dex_cex_engine:
        state["dex_cex"] = manager.dex_cex_engine.get_state()
    
    if manager.latency_engine:
        state["latency"] = manager.latency_engine.get_state()
    
    return state


@app.get("/api/orderbook/{pair}")
async def get_orderbook(pair: str):
    """Get aggregated order book for a pair"""
    if not manager.orderbook_engine:
        return {"error": "Order book engine not initialized"}
    pair = pair.replace("-", "/")
    return manager.orderbook_engine.get_aggregated_book(pair).to_dict()


@app.get("/api/ml/predictions")
async def get_ml_predictions():
    """Get ML predictions"""
    if not manager.ml_engine:
        return {"error": "ML engine not initialized"}
    return manager.ml_engine.get_state()


@app.get("/api/storage/stats")
async def get_storage_stats():
    """Get tick storage statistics"""
    if not manager.tick_storage:
        return {"error": "Storage not initialized"}
    return manager.tick_storage.get_statistics()


@app.get("/api/cross-triangular")
async def get_cross_triangular():
    """Get cross-exchange triangular arbitrage opportunities"""
    if not manager.cross_triangular_engine:
        return {"error": "Cross-triangular engine not initialized"}
    return manager.cross_triangular_engine.get_state()


@app.get("/api/futures-spot")
async def get_futures_spot():
    """Get futures-spot basis arbitrage opportunities"""
    if not manager.futures_spot_engine:
        return {"error": "Futures-spot engine not initialized"}
    return manager.futures_spot_engine.get_state()


@app.get("/api/dex-cex")
async def get_dex_cex():
    """Get DEX/CEX arbitrage opportunities"""
    if not manager.dex_cex_engine:
        return {"error": "DEX/CEX engine not initialized"}
    return manager.dex_cex_engine.get_state()


@app.get("/api/latency")
async def get_latency():
    """Get latency arbitrage opportunities"""
    if not manager.latency_engine:
        return {"error": "Latency engine not initialized"}
    return manager.latency_engine.get_state()


@app.get("/api/latency/feed-health")
async def get_feed_health():
    """Get exchange feed health status"""
    if not manager.latency_engine:
        return {"error": "Latency engine not initialized"}
    return manager.latency_engine.get_feed_health()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML"""
    return DASHBOARD_HTML


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Arbitrage Bot</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0b0f;
            --bg-secondary: #12141a;
            --bg-tertiary: #1a1d26;
            --bg-card: #15171e;
            --border-color: #2a2d3a;
            --text-primary: #e8eaed;
            --text-secondary: #9aa0a6;
            --text-muted: #5f6368;
            --accent-green: #00d26a;
            --accent-green-dim: rgba(0, 210, 106, 0.15);
            --accent-red: #ff4757;
            --accent-red-dim: rgba(255, 71, 87, 0.15);
            --accent-blue: #00b4d8;
            --accent-yellow: #ffd43b;
            --accent-purple: #a855f7;
            --gradient-start: #00d26a;
            --gradient-end: #00b4d8;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Animated background */
        .bg-pattern {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 20%, rgba(0, 210, 106, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 180, 216, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.02) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }

        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0 40px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 32px;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--gradient-start), var(--gradient-end));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 4px 20px rgba(0, 210, 106, 0.3);
        }

        .logo h1 {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .status-indicator {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 20px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 100px;
        }

        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent-green);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .status-dot.disconnected {
            background: var(--accent-red);
            animation: none;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 210, 106, 0.4); }
            50% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(0, 210, 106, 0); }
        }

        /* Grid Layout */
        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 24px;
        }

        @media (max-width: 1200px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        /* Cards */
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
        }

        .card-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .card-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .card-title span {
            font-size: 18px;
        }

        .card-body {
            padding: 0;
        }

        /* Opportunities Section */
        .opportunities-section {
            margin-bottom: 24px;
        }

        .opportunity-card {
            background: linear-gradient(135deg, var(--accent-green-dim), transparent);
            border: 1px solid var(--accent-green);
            border-radius: 12px;
            padding: 20px;
            margin: 16px;
            animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .opportunity-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .opportunity-pair {
            font-family: 'JetBrains Mono', monospace;
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .opportunity-profit {
            font-family: 'JetBrains Mono', monospace;
            font-size: 24px;
            font-weight: 700;
            color: var(--accent-green);
            text-shadow: 0 0 20px rgba(0, 210, 106, 0.5);
        }

        .opportunity-flow {
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
        }

        .exchange-badge {
            padding: 8px 16px;
            background: var(--bg-secondary);
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
        }

        .exchange-badge.buy {
            border-left: 3px solid var(--accent-green);
        }

        .exchange-badge.sell {
            border-left: 3px solid var(--accent-blue);
        }

        .flow-arrow {
            color: var(--text-muted);
            font-size: 20px;
        }

        .no-opportunities {
            padding: 60px 24px;
            text-align: center;
            color: var(--text-muted);
        }

        .no-opportunities-icon {
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        /* Price Table */
        .price-table {
            width: 100%;
            border-collapse: collapse;
        }

        .price-table th {
            padding: 16px 20px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: var(--bg-tertiary);
        }

        .price-table td {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
        }

        .price-table tr:last-child td {
            border-bottom: none;
        }

        .price-table tr:hover td {
            background: var(--bg-tertiary);
        }

        .pair-cell {
            font-weight: 600;
            color: var(--text-primary);
        }

        .exchange-cell {
            color: var(--text-secondary);
        }

        .price-cell {
            color: var(--text-primary);
        }

        .price-cell.bid { color: var(--accent-green); }
        .price-cell.ask { color: var(--accent-red); }

        .spread-cell {
            font-size: 12px;
            padding: 4px 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            color: var(--text-secondary);
        }

        /* History Section */
        .history-item {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .history-item:last-child {
            border-bottom: none;
        }

        .history-details {
            display: flex;
            flex-direction: column;
            gap: 4px;
        }

        .history-pair {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 14px;
        }

        .history-route {
            font-size: 12px;
            color: var(--text-muted);
        }

        .history-profit {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--accent-green);
        }

        .history-time {
            font-size: 11px;
            color: var(--text-muted);
        }

        /* Stats Bar */
        .stats-bar {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }

        @media (max-width: 900px) {
            .stats-bar {
                grid-template-columns: repeat(2, 1fr);
            }
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
        }

        .stat-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 28px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .stat-value.green { color: var(--accent-green); }
        .stat-value.blue { color: var(--accent-blue); }
        .stat-value.purple { color: var(--accent-purple); }
        .stat-value.yellow { color: var(--accent-yellow); }

        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }

        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }

        ::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-muted);
        }

        .price-flash {
            animation: flash 0.5s ease-out;
        }

        @keyframes flash {
            0% { background: rgba(0, 210, 106, 0.3); }
            100% { background: transparent; }
        }

        /* Triangular Arbitrage Styles */
        .triangular-card {
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.15), transparent);
            border: 1px solid var(--accent-purple);
            border-radius: 12px;
            padding: 20px;
            margin: 16px;
            animation: slideIn 0.3s ease-out;
        }

        .triangular-path {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--bg-tertiary);
            border-radius: 8px;
            margin-top: 12px;
            overflow-x: auto;
        }

        .path-step {
            display: flex;
            flex-direction: column;
            align-items: center;
            min-width: 100px;
        }

        .path-action {
            font-size: 11px;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 4px;
        }

        .path-pair {
            font-family: 'JetBrains Mono', monospace;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
        }

        .path-price {
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
        }

        .path-arrow {
            color: var(--accent-purple);
            font-size: 24px;
        }
    </style>
</head>
<body>
    <div class="bg-pattern"></div>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">⚡</div>
                <h1>Crypto Arbitrage Bot</h1>
            </div>
            <div class="status-indicator">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Connecting...</span>
            </div>
        </header>

        <div class="stats-bar">
            <div class="stat-card">
                <div class="stat-label">Active Opportunities</div>
                <div class="stat-value green" id="statOpportunities">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Exchanges Connected</div>
                <div class="stat-value blue" id="statExchanges">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">ML Prediction</div>
                <div class="stat-value purple" id="statMLPrediction">--</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Market Regime</div>
                <div class="stat-value yellow" id="statRegime">--</div>
            </div>
        </div>

        <div class="stats-bar" style="margin-top: -8px;">
            <div class="stat-card">
                <div class="stat-label">Stat Arb Signals</div>
                <div class="stat-value" style="color: #f97316;" id="statStatArb">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Anomalies Detected</div>
                <div class="stat-value" style="color: #ef4444;" id="statAnomalies">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Ticks Stored</div>
                <div class="stat-value blue" id="statTicks">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Best Spread</div>
                <div class="stat-value green" id="statBestSpread">--%</div>
            </div>
        </div>

        <div class="stats-bar" style="margin-top: -8px;">
            <div class="stat-card">
                <div class="stat-label">New Strategies</div>
                <div class="stat-value" style="color: #3b82f6;" id="statNewEngines">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Cross-Exch Tri</div>
                <div class="stat-value" style="color: #3b82f6;" id="statCrossTri">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Futures-Spot</div>
                <div class="stat-value" style="color: #10b981;" id="statFuturesSpot">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">DEX/CEX + Latency</div>
                <div class="stat-value" style="color: #8b5cf6;" id="statDexLatency">0</div>
            </div>
        </div>

        <div class="dashboard-grid">
            <div class="main-content">
                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>🎯</span> Simple Arbitrage (Cross-Exchange)</div>
                    </div>
                    <div class="card-body" id="opportunitiesContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">📊</div>
                            <p>Scanning for arbitrage opportunities...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Waiting for price data from exchanges</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>🔺</span> Triangular Arbitrage (Single Exchange)</div>
                    </div>
                    <div class="card-body" id="triangularOpportunitiesContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">📐</div>
                            <p>Computing triangular paths...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Finding cycles within single exchanges</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>📊</span> Statistical Arbitrage (Mean Reversion)</div>
                    </div>
                    <div class="card-body" id="statArbContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">📈</div>
                            <p>Analyzing pair correlations...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Computing z-scores for mean reversion</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>🤖</span> ML Predictions & Regime Analysis</div>
                    </div>
                    <div class="card-body" id="mlContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">🧠</div>
                            <p>Training ML models...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Predicting opportunities & market regime</p>
                        </div>
                    </div>
                </div>

                <!-- NEW ARBITRAGE STRATEGIES -->
                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>🔀</span> Cross-Exchange Triangular</div>
                    </div>
                    <div class="card-body" id="crossTriangularContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">🔀</div>
                            <p>Scanning cross-exchange paths...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Finding multi-exchange triangular cycles</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>📈</span> Futures-Spot Basis (Funding Rate)</div>
                    </div>
                    <div class="card-body" id="futuresSpotContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">📊</div>
                            <p>Analyzing funding rates...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Monitoring perpetual vs spot basis</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>🌐</span> DEX/CEX Arbitrage</div>
                    </div>
                    <div class="card-body" id="dexCexContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">🌐</div>
                            <p>Scanning DEX pools...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Comparing Uniswap/Curve vs CEX prices</p>
                        </div>
                    </div>
                </div>

                <div class="card opportunities-section">
                    <div class="card-header">
                        <div class="card-title"><span>⚡</span> Latency Arbitrage</div>
                    </div>
                    <div class="card-body" id="latencyContainer">
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">⚡</div>
                            <p>Monitoring feed latencies...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Detecting stale exchange quotes</p>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header">
                        <div class="card-title"><span>💹</span> Live Prices</div>
                    </div>
                    <div class="card-body">
                        <table class="price-table">
                            <thead>
                                <tr>
                                    <th>Pair</th>
                                    <th>Exchange</th>
                                    <th>Bid</th>
                                    <th>Ask</th>
                                    <th>Spread</th>
                                </tr>
                            </thead>
                            <tbody id="priceTableBody">
                                <tr>
                                    <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 40px;">
                                        Waiting for price data...
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="sidebar">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title"><span>📜</span> Recent Opportunities</div>
                    </div>
                    <div class="card-body" id="historyContainer" style="max-height: 600px; overflow-y: auto;">
                        <div class="no-opportunities" style="padding: 40px 20px;">
                            <p>No opportunities detected yet</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // State
        let prices = {};
        let opportunities = [];
        let triangularOpportunities = [];
        let statArbSignals = [];
        let mlPredictions = [];
        let anomalies = [];
        let regimes = {};
        let history = [];
        let triangularHistory = [];
        let ticksStored = 0;
        let ws = null;
        let exchanges = new Set();
        // New arbitrage states
        let crossTriangularOpps = [];
        let futuresSpotOpps = [];
        let dexCexOpps = [];
        let latencyOpps = [];

        // WebSocket connection
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                document.getElementById('statusDot').classList.remove('disconnected');
                document.getElementById('statusText').textContent = 'Connected';
            };
            
            ws.onclose = () => {
                document.getElementById('statusDot').classList.add('disconnected');
                document.getElementById('statusText').textContent = 'Disconnected';
                setTimeout(connect, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };
        }

        function handleMessage(message) {
            switch(message.type) {
                case 'state':
                    // Full state update
                    prices = message.data.prices || {};
                    opportunities = message.data.opportunities || [];
                    triangularOpportunities = message.data.triangular_opportunities || [];
                    history = message.data.history || [];
                    triangularHistory = message.data.triangular_history || [];
                    
                    // Advanced engine data
                    if (message.data.statistical) {
                        statArbSignals = message.data.statistical.stat_arb_signals || [];
                    }
                    if (message.data.ml) {
                        mlPredictions = message.data.ml.ml_predictions || [];
                        anomalies = message.data.ml.anomalies || [];
                        regimes = message.data.ml.market_regimes || {};
                    }
                    if (message.data.storage) {
                        ticksStored = message.data.storage.storage_statistics?.total_ticks_stored || 0;
                    }
                    
                    // New arbitrage engine data
                    if (message.data.cross_triangular) {
                        crossTriangularOpps = message.data.cross_triangular.cross_exchange_opportunities || [];
                    }
                    if (message.data.futures_spot) {
                        futuresSpotOpps = message.data.futures_spot.futures_spot_opportunities || [];
                    }
                    if (message.data.dex_cex) {
                        dexCexOpps = message.data.dex_cex.dex_cex_opportunities || [];
                    }
                    if (message.data.latency) {
                        latencyOpps = message.data.latency.latency_opportunities || [];
                    }
                    
                    updateUI();
                    break;
                case 'price':
                    // Single price update
                    const p = message.data;
                    if (!prices[p.pair]) prices[p.pair] = {};
                    prices[p.pair][p.exchange] = p;
                    exchanges.add(p.exchange);
                    updatePriceTable();
                    updateStats();
                    break;
                case 'opportunity':
                    // New simple opportunity
                    opportunities = opportunities.filter(o => 
                        !(o.pair === message.data.pair && 
                          o.buy_exchange === message.data.buy_exchange && 
                          o.sell_exchange === message.data.sell_exchange)
                    );
                    opportunities.unshift(message.data);
                    opportunities.sort((a, b) => b.profit_percent - a.profit_percent);
                    history.unshift(message.data);
                    if (history.length > 20) history.pop();
                    updateOpportunities();
                    updateHistory();
                    updateStats();
                    break;
                case 'triangular_opportunity':
                    // New triangular opportunity
                    triangularOpportunities.unshift(message.data);
                    triangularOpportunities.sort((a, b) => b.profit_percent - a.profit_percent);
                    if (triangularOpportunities.length > 10) triangularOpportunities.pop();
                    triangularHistory.unshift(message.data);
                    if (triangularHistory.length > 20) triangularHistory.pop();
                    updateTriangularOpportunities();
                    updateStats();
                    break;
                case 'stat_arb_signal':
                    // Statistical arbitrage signal
                    statArbSignals.unshift(message.data);
                    if (statArbSignals.length > 10) statArbSignals.pop();
                    updateStatArb();
                    updateStats();
                    break;
                case 'ml_prediction':
                    // ML prediction
                    mlPredictions.unshift(message.data);
                    if (mlPredictions.length > 10) mlPredictions.pop();
                    updateML();
                    updateStats();
                    break;
                case 'anomaly':
                    // Anomaly detected
                    anomalies.unshift(message.data);
                    if (anomalies.length > 10) anomalies.pop();
                    updateML();
                    updateStats();
                    break;
                case 'cross_triangular_opportunity':
                    // Cross-exchange triangular opportunity
                    crossTriangularOpps.unshift(message.data);
                    if (crossTriangularOpps.length > 10) crossTriangularOpps.pop();
                    updateNewArbitrageEngines();
                    updateStats();
                    break;
                case 'futures_spot_opportunity':
                    // Futures-spot basis opportunity
                    futuresSpotOpps.unshift(message.data);
                    if (futuresSpotOpps.length > 10) futuresSpotOpps.pop();
                    updateNewArbitrageEngines();
                    updateStats();
                    break;
                case 'dex_cex_opportunity':
                    // DEX/CEX arbitrage opportunity
                    dexCexOpps.unshift(message.data);
                    if (dexCexOpps.length > 10) dexCexOpps.pop();
                    updateNewArbitrageEngines();
                    updateStats();
                    break;
                case 'latency_opportunity':
                    // Latency arbitrage opportunity
                    latencyOpps.unshift(message.data);
                    if (latencyOpps.length > 10) latencyOpps.pop();
                    updateNewArbitrageEngines();
                    updateStats();
                    break;
            }
        }

        function updateUI() {
            updatePriceTable();
            updateOpportunities();
            updateTriangularOpportunities();
            updateStatArb();
            updateML();
            updateHistory();
            updateStats();
            updateNewArbitrageEngines();
        }

        function updateStats() {
            const totalOpps = opportunities.length + triangularOpportunities.length + statArbSignals.length + 
                              crossTriangularOpps.length + futuresSpotOpps.length + dexCexOpps.length + latencyOpps.length;
            document.getElementById('statOpportunities').textContent = totalOpps;
            document.getElementById('statExchanges').textContent = exchanges.size;
            document.getElementById('statStatArb').textContent = statArbSignals.length;
            document.getElementById('statAnomalies').textContent = anomalies.length;
            document.getElementById('statTicks').textContent = ticksStored.toLocaleString();
            document.getElementById('statNewEngines').textContent = crossTriangularOpps.length + futuresSpotOpps.length + dexCexOpps.length + latencyOpps.length;
            document.getElementById('statCrossTri').textContent = crossTriangularOpps.length;
            document.getElementById('statFuturesSpot').textContent = futuresSpotOpps.length;
            document.getElementById('statDexLatency').textContent = dexCexOpps.length + latencyOpps.length;
            
            // ML Prediction
            if (mlPredictions.length > 0) {
                const latest = mlPredictions[0];
                const prob = (latest.probability * 100).toFixed(0);
                document.getElementById('statMLPrediction').textContent = `${prob}%`;
                document.getElementById('statMLPrediction').style.color = prob > 50 ? '#00d26a' : '#9aa0a6';
            }
            
            // Market Regime
            const regimeKeys = Object.keys(regimes);
            if (regimeKeys.length > 0) {
                const regime = regimes[regimeKeys[0]];
                const regimeColors = {
                    'stable': '#00d26a',
                    'volatile': '#ef4444',
                    'trending_up': '#10b981',
                    'trending_down': '#f97316'
                };
                document.getElementById('statRegime').textContent = regime.regime.toUpperCase();
                document.getElementById('statRegime').style.color = regimeColors[regime.regime] || '#9aa0a6';
            }
            
            let bestProfit = 0;
            if (opportunities.length > 0) {
                bestProfit = Math.max(bestProfit, opportunities[0].profit_percent);
            }
            if (triangularOpportunities.length > 0) {
                bestProfit = Math.max(bestProfit, triangularOpportunities[0].profit_percent);
            }
            if (bestProfit > 0) {
                document.getElementById('statBestSpread').textContent = bestProfit.toFixed(3) + '%';
            }
        }

        function updateStatArb() {
            const container = document.getElementById('statArbContainer');
            
            if (statArbSignals.length === 0) {
                container.innerHTML = `
                    <div class="no-opportunities">
                        <div class="no-opportunities-icon">📈</div>
                        <p>Analyzing pair correlations...</p>
                        <p style="font-size: 12px; margin-top: 8px;">Waiting for sufficient data (100+ ticks)</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (const sig of statArbSignals) {
                const signalColor = sig.signal === 'long_spread' ? '#00d26a' : sig.signal === 'short_spread' ? '#ef4444' : '#9aa0a6';
                html += `
                    <div style="background: linear-gradient(135deg, rgba(249, 115, 22, 0.15), transparent); border: 1px solid #f97316; border-radius: 12px; padding: 16px; margin: 12px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${sig.pair_a} / ${sig.pair_b}</span>
                            <span style="color: ${signalColor}; font-weight: 700;">${sig.signal.replace('_', ' ').toUpperCase()}</span>
                        </div>
                        <div style="display: flex; gap: 16px; margin-top: 12px; font-size: 13px; color: var(--text-secondary);">
                            <span>Z-Score: <strong style="color: var(--text-primary);">${sig.z_score.toFixed(2)}</strong></span>
                            <span>Corr: <strong style="color: var(--text-primary);">${(sig.correlation * 100).toFixed(1)}%</strong></span>
                            <span>Conf: <strong style="color: var(--text-primary);">${(sig.confidence * 100).toFixed(0)}%</strong></span>
                        </div>
                        <div style="margin-top: 8px; font-size: 12px; color: var(--text-muted);">
                            Action: ${sig.action}
                        </div>
                    </div>
                `;
            }
            container.innerHTML = html;
        }

        function updateML() {
            const container = document.getElementById('mlContainer');
            
            let html = '';
            
            // Market Regimes
            const regimeKeys = Object.keys(regimes);
            if (regimeKeys.length > 0) {
                html += '<div style="padding: 12px;"><div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">MARKET REGIMES</div>';
                for (const pair of regimeKeys.slice(0, 4)) {
                    const r = regimes[pair];
                    const regimeIcons = {
                        'stable': '🟢',
                        'volatile': '🔴',
                        'trending_up': '📈',
                        'trending_down': '📉'
                    };
                    html += `
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="font-family: 'JetBrains Mono', monospace; font-size: 13px;">${pair}</span>
                            <span>${regimeIcons[r.regime] || '⚪'} ${r.regime.toUpperCase()} (${(r.confidence * 100).toFixed(0)}%)</span>
                        </div>
                    `;
                }
                html += '</div>';
            }
            
            // ML Predictions
            if (mlPredictions.length > 0) {
                html += '<div style="padding: 12px; border-top: 1px solid var(--border-color);"><div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">OPPORTUNITY PREDICTIONS</div>';
                for (const pred of mlPredictions.slice(0, 3)) {
                    const prob = (pred.probability * 100).toFixed(0);
                    const color = prob > 60 ? '#00d26a' : prob > 30 ? '#ffd43b' : '#9aa0a6';
                    html += `
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color);">
                            <span style="font-size: 13px;">${pred.details?.pair || 'Market'}</span>
                            <span style="color: ${color}; font-weight: 600;">${prob}% in ${pred.time_horizon_ms}ms</span>
                        </div>
                    `;
                }
                html += '</div>';
            }
            
            // Anomalies
            if (anomalies.length > 0) {
                html += '<div style="padding: 12px; border-top: 1px solid var(--border-color);"><div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">⚠️ ANOMALIES DETECTED</div>';
                for (const a of anomalies.slice(0, 3)) {
                    html += `
                        <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-color); color: #ef4444;">
                            <span style="font-size: 13px;">${a.exchange} - ${a.pair}</span>
                            <span>${a.type.toUpperCase()} (${(a.severity * 100).toFixed(0)}%)</span>
                        </div>
                    `;
                }
                html += '</div>';
            }
            
            if (!html) {
                html = `
                    <div class="no-opportunities">
                        <div class="no-opportunities-icon">🧠</div>
                        <p>Collecting data for ML analysis...</p>
                        <p style="font-size: 12px; margin-top: 8px;">Predictions available after 100+ price updates</p>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }

        function updateNewArbitrageEngines() {
            // Cross-Exchange Triangular
            const crossTriContainer = document.getElementById('crossTriangularContainer');
            if (crossTriContainer) {
                if (crossTriangularOpps.length === 0) {
                    crossTriContainer.innerHTML = `
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">🔀</div>
                            <p>Scanning cross-exchange paths...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Finding multi-exchange triangular cycles</p>
                        </div>
                    `;
                } else {
                    let html = '';
                    for (const opp of crossTriangularOpps.slice(0, 5)) {
                        html += `
                            <div style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), transparent); border: 1px solid #3b82f6; border-radius: 12px; padding: 16px; margin: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${opp.base_currency} Cycle</span>
                                    <span style="color: #00d26a; font-weight: 700;">+${opp.profit_percent.toFixed(3)}%</span>
                                </div>
                                <div style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">
                                    Exchanges: ${opp.exchanges.join(' → ')}
                                </div>
                                <div style="margin-top: 4px; font-size: 11px; color: var(--text-muted);">
                                    Risk: ${(opp.risk_score * 100).toFixed(0)}% | Est. Transfer: ${opp.estimated_transfer_time_ms}ms
                                </div>
                            </div>
                        `;
                    }
                    crossTriContainer.innerHTML = html;
                }
            }
            
            // Futures-Spot Basis
            const futuresContainer = document.getElementById('futuresSpotContainer');
            if (futuresContainer) {
                if (futuresSpotOpps.length === 0) {
                    futuresContainer.innerHTML = `
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">📊</div>
                            <p>Analyzing funding rates...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Monitoring perpetual vs spot basis</p>
                        </div>
                    `;
                } else {
                    let html = '';
                    for (const opp of futuresSpotOpps.slice(0, 5)) {
                        const dirColor = opp.direction === 'cash_and_carry' ? '#10b981' : '#f97316';
                        html += `
                            <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.15), transparent); border: 1px solid #10b981; border-radius: 12px; padding: 16px; margin: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${opp.exchange} ${opp.symbol}</span>
                                    <span style="color: ${dirColor}; font-weight: 600; font-size: 12px;">${opp.direction.replace('_', ' ').toUpperCase()}</span>
                                </div>
                                <div style="display: flex; gap: 16px; margin-top: 8px; font-size: 12px; color: var(--text-secondary);">
                                    <span>Funding: <strong style="color: var(--text-primary);">${(opp.funding_rate * 100).toFixed(4)}%</strong></span>
                                    <span>Annual: <strong style="color: #00d26a;">${opp.funding_rate_annualized.toFixed(1)}%</strong></span>
                                </div>
                                <div style="margin-top: 4px; font-size: 11px; color: var(--text-muted);">
                                    Basis: ${opp.basis_percent.toFixed(4)}% | Risk: ${opp.risk_level} | Conf: ${(opp.confidence * 100).toFixed(0)}%
                                </div>
                            </div>
                        `;
                    }
                    futuresContainer.innerHTML = html;
                }
            }
            
            // DEX/CEX Arbitrage
            const dexCexContainer = document.getElementById('dexCexContainer');
            if (dexCexContainer) {
                if (dexCexOpps.length === 0) {
                    dexCexContainer.innerHTML = `
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">🌐</div>
                            <p>Scanning DEX pools...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Comparing Uniswap/Curve vs CEX prices</p>
                        </div>
                    `;
                } else {
                    let html = '';
                    for (const opp of dexCexOpps.slice(0, 5)) {
                        const mevColor = opp.mev_risk === 'low' ? '#00d26a' : opp.mev_risk === 'medium' ? '#ffd43b' : '#ef4444';
                        html += `
                            <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), transparent); border: 1px solid #8b5cf6; border-radius: 12px; padding: 16px; margin: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${opp.dex} ↔ ${opp.cex}</span>
                                    <span style="color: #00d26a; font-weight: 700;">+$${opp.net_profit_usd.toFixed(2)}</span>
                                </div>
                                <div style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">
                                    ${opp.pair} | ${opp.direction.replace('_', ' ')} | Chain: ${opp.dex_chain}
                                </div>
                                <div style="display: flex; gap: 12px; margin-top: 4px; font-size: 11px; color: var(--text-muted);">
                                    <span>Profit: ${opp.net_profit_percent.toFixed(3)}%</span>
                                    <span>Gas: $${opp.gas_cost_usd.toFixed(2)}</span>
                                    <span style="color: ${mevColor};">MEV: ${opp.mev_risk}</span>
                                </div>
                            </div>
                        `;
                    }
                    dexCexContainer.innerHTML = html;
                }
            }
            
            // Latency Arbitrage
            const latencyContainer = document.getElementById('latencyContainer');
            if (latencyContainer) {
                if (latencyOpps.length === 0) {
                    latencyContainer.innerHTML = `
                        <div class="no-opportunities">
                            <div class="no-opportunities-icon">⚡</div>
                            <p>Monitoring feed latencies...</p>
                            <p style="font-size: 12px; margin-top: 8px;">Detecting stale exchange quotes</p>
                        </div>
                    `;
                } else {
                    let html = '';
                    for (const opp of latencyOpps.slice(0, 5)) {
                        const dirColor = opp.direction === 'long' ? '#00d26a' : '#ef4444';
                        html += `
                            <div style="background: linear-gradient(135deg, rgba(251, 191, 36, 0.15), transparent); border: 1px solid #fbbf24; border-radius: 12px; padding: 16px; margin: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">${opp.pair}</span>
                                    <span style="color: ${dirColor}; font-weight: 700;">${opp.direction.toUpperCase()} ${opp.predicted_move_percent.toFixed(3)}%</span>
                                </div>
                                <div style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">
                                    Stale: ${opp.stale_exchange} (${opp.staleness_ms}ms) → Fast: ${opp.fast_exchange}
                                </div>
                                <div style="display: flex; gap: 12px; margin-top: 4px; font-size: 11px; color: var(--text-muted);">
                                    <span>Window: ${opp.time_window_ms}ms</span>
                                    <span>Confidence: ${(opp.confidence * 100).toFixed(0)}%</span>
                                    <span>Risk: ${(opp.risk_score * 100).toFixed(0)}%</span>
                                </div>
                            </div>
                        `;
                    }
                    latencyContainer.innerHTML = html;
                }
            }
        }

        function updatePriceTable() {
            const tbody = document.getElementById('priceTableBody');
            let html = '';
            
            const sortedPairs = Object.keys(prices).sort();
            
            for (const pair of sortedPairs) {
                const exchangePrices = prices[pair];
                const sortedExchanges = Object.keys(exchangePrices).sort();
                
                for (const exchange of sortedExchanges) {
                    const p = exchangePrices[exchange];
                    const spread = ((p.ask - p.bid) / p.mid * 100).toFixed(3);
                    
                    html += `
                        <tr id="price-${pair}-${exchange}">
                            <td class="pair-cell">${pair}</td>
                            <td class="exchange-cell">${exchange}</td>
                            <td class="price-cell bid">$${formatPrice(p.bid)}</td>
                            <td class="price-cell ask">$${formatPrice(p.ask)}</td>
                            <td><span class="spread-cell">${spread}%</span></td>
                        </tr>
                    `;
                }
            }
            
            if (!html) {
                html = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 40px;">
                    Waiting for price data...</td></tr>`;
            }
            
            tbody.innerHTML = html;
        }

        function updateOpportunities() {
            const container = document.getElementById('opportunitiesContainer');
            
            if (opportunities.length === 0) {
                container.innerHTML = `
                    <div class="no-opportunities">
                        <div class="no-opportunities-icon">📊</div>
                        <p>No arbitrage opportunities detected</p>
                        <p style="font-size: 12px; margin-top: 8px;">Monitoring ${Object.keys(prices).length} pairs across ${exchanges.size} exchanges</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (const opp of opportunities) {
                html += `
                    <div class="opportunity-card">
                        <div class="opportunity-header">
                            <span class="opportunity-pair">${opp.pair}</span>
                            <span class="opportunity-profit">+${opp.profit_percent.toFixed(3)}%</span>
                        </div>
                        <div class="opportunity-flow">
                            <div class="exchange-badge buy">
                                <strong>BUY</strong> @ ${opp.buy_exchange}<br>
                                $${formatPrice(opp.buy_price)}
                            </div>
                            <span class="flow-arrow">→</span>
                            <div class="exchange-badge sell">
                                <strong>SELL</strong> @ ${opp.sell_exchange}<br>
                                $${formatPrice(opp.sell_price)}
                            </div>
                        </div>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }

        function updateTriangularOpportunities() {
            const container = document.getElementById('triangularOpportunitiesContainer');
            
            if (triangularOpportunities.length === 0) {
                container.innerHTML = `
                    <div class="no-opportunities">
                        <div class="no-opportunities-icon">📐</div>
                        <p>No triangular opportunities detected</p>
                        <p style="font-size: 12px; margin-top: 8px;">Monitoring for profitable cycles</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (const opp of triangularOpportunities) {
                // Build path visualization
                let pathHtml = '<div class="triangular-path">';
                for (let i = 0; i < opp.pairs.length; i++) {
                    const pair = opp.pairs[i];
                    const side = opp.sides[i];
                    const price = opp.prices[pair];
                    const priceValue = side === 'buy' ? price.ask : price.bid;
                    
                    pathHtml += `
                        <div class="path-step">
                            <div class="path-action">${side}</div>
                            <div class="path-pair">${pair}</div>
                            <div class="path-price">$${formatPrice(priceValue)}</div>
                        </div>
                    `;
                    
                    if (i < opp.pairs.length - 1) {
                        pathHtml += '<div class="path-arrow">→</div>';
                    }
                }
                pathHtml += '</div>';
                
                html += `
                    <div class="triangular-card">
                        <div class="opportunity-header">
                            <span class="opportunity-pair">${opp.exchange} - ${opp.base_currency}</span>
                            <span class="opportunity-profit">+${opp.profit_percent.toFixed(3)}%</span>
                        </div>
                        ${pathHtml}
                        <div style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">
                            Start: $${opp.start_amount.toLocaleString()} → End: $${opp.end_amount.toLocaleString()} 
                            | Profit: $${opp.profit_amount.toFixed(2)}
                        </div>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }

        function updateHistory() {
            const container = document.getElementById('historyContainer');
            
            // Combine both types of opportunities
            const allHistory = [
                ...history.map(o => ({...o, type: 'simple'})),
                ...triangularHistory.map(o => ({...o, type: 'triangular'}))
            ].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            
            if (allHistory.length === 0) {
                container.innerHTML = `
                    <div class="no-opportunities" style="padding: 40px 20px;">
                        <p>No opportunities detected yet</p>
                    </div>
                `;
                return;
            }
            
            let html = '';
            for (const opp of allHistory.slice(0, 20)) {
                const time = new Date(opp.timestamp).toLocaleTimeString();
                const icon = opp.type === 'triangular' ? '🔺' : '🎯';
                let route = '';
                
                if (opp.type === 'simple') {
                    route = `${opp.buy_exchange} → ${opp.sell_exchange}`;
                } else {
                    route = `${opp.exchange}: ${opp.pairs.join(' → ')}`;
                }
                
                html += `
                    <div class="history-item">
                        <div class="history-details">
                            <span class="history-pair">${icon} ${opp.pair || opp.base_currency}</span>
                            <span class="history-route">${route}</span>
                            <span class="history-time">${time}</span>
                        </div>
                        <span class="history-profit">+${opp.profit_percent.toFixed(3)}%</span>
                    </div>
                `;
            }
            
            container.innerHTML = html;
        }

        function formatPrice(price) {
            if (price >= 1000) {
                return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else if (price >= 1) {
                return price.toFixed(4);
            } else {
                return price.toFixed(6);
            }
        }

        // Start connection
        connect();
        
        // Ping to keep connection alive
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 30000);
    </script>
</body>
</html>
"""
