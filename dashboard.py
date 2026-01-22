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
        
    def set_engine(self, engine: ArbitrageEngine):
        """Set the arbitrage engine and register callbacks"""
        self.engine = engine
        engine.on_price_update(self._on_price_update)
        engine.on_opportunity(self._on_opportunity)
    
    def set_triangular_engine(self, engine):
        """Set the triangular arbitrage engine and register callbacks"""
        self.triangular_engine = engine
        engine.on_opportunity(self._on_triangular_opportunity)
    
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
    
    # Add triangular arbitrage data if enabled
    if manager.triangular_engine:
        state.update(manager.triangular_engine.get_state())
    
    return state


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
                <div class="stat-label">Pairs Monitored</div>
                <div class="stat-value purple" id="statPairs">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Best Spread</div>
                <div class="stat-value yellow" id="statBestSpread">--%</div>
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
        let history = [];
        let triangularHistory = [];
        let ws = null;
        let exchanges = new Set();

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
            }
        }

        function updateUI() {
            updatePriceTable();
            updateOpportunities();
            updateTriangularOpportunities();
            updateHistory();
            updateStats();
        }

        function updateStats() {
            const totalOpps = opportunities.length + triangularOpportunities.length;
            document.getElementById('statOpportunities').textContent = totalOpps;
            document.getElementById('statExchanges').textContent = exchanges.size;
            
            const pairs = new Set(Object.keys(prices));
            document.getElementById('statPairs').textContent = pairs.size;
            
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
