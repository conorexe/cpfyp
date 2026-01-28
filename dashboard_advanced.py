"""
Advanced Visualization Dashboard

Features:
1. Order Book Heatmap - Depth visualization across exchanges with animated bid/ask changes
2. Opportunity Flow Diagram - Sankey diagram showing money movement paths
3. 3D Market Visualization - Interactive Three.js charts
4. Latency Globe - World map with exchange locations and real-time latency measurements

Uses:
- D3.js for Sankey diagrams
- Three.js for 3D visualization
- Plotly.js for heatmaps
- Globe.gl for latency globe
"""

# Advanced Dashboard HTML with all visualizations
ADVANCED_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crypto Arbitrage Bot - Advanced Analytics</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <!-- Plotly for heatmaps -->
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <!-- Three.js for 3D -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <!-- D3.js for Sankey -->
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3-sankey@0.12.3/dist/d3-sankey.min.js"></script>
    <!-- Globe.gl for latency globe -->
    <script src="https://unpkg.com/globe.gl"></script>
    
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
            --accent-red: #ff4757;
            --accent-blue: #00b4d8;
            --accent-yellow: #ffd43b;
            --accent-purple: #a855f7;
            --accent-orange: #f97316;
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

        .bg-pattern {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 20%, rgba(0, 210, 106, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 180, 216, 0.03) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        .container {
            max-width: 1800px;
            margin: 0 auto;
            padding: 24px;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0 30px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .logo-icon {
            width: 48px;
            height: 48px;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            box-shadow: 0 4px 20px rgba(168, 85, 247, 0.3);
        }

        .logo h1 {
            font-size: 24px;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary), var(--text-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .nav-tabs {
            display: flex;
            gap: 8px;
        }

        .nav-tab {
            padding: 10px 20px;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 14px;
        }

        .nav-tab:hover, .nav-tab.active {
            background: var(--bg-tertiary);
            border-color: var(--accent-blue);
            color: var(--text-primary);
        }

        .viz-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }

        @media (max-width: 1400px) {
            .viz-grid {
                grid-template-columns: 1fr;
            }
        }

        .viz-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            overflow: hidden;
        }

        .viz-card.full-width {
            grid-column: span 2;
        }

        @media (max-width: 1400px) {
            .viz-card.full-width {
                grid-column: span 1;
            }
        }

        .viz-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .viz-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .viz-title span {
            font-size: 20px;
        }

        .viz-controls {
            display: flex;
            gap: 8px;
        }

        .viz-btn {
            padding: 6px 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 12px;
            transition: all 0.2s;
        }

        .viz-btn:hover {
            background: var(--accent-blue);
            color: white;
        }

        .viz-body {
            padding: 16px;
            min-height: 400px;
        }

        #heatmap-container, #sankey-container, #globe-container, #threejs-container {
            width: 100%;
            height: 400px;
        }

        #globe-container {
            height: 500px;
        }

        #threejs-container {
            height: 500px;
        }

        /* Heatmap color scale legend */
        .heatmap-legend {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
            font-size: 12px;
            color: var(--text-muted);
        }

        .legend-gradient {
            width: 200px;
            height: 12px;
            background: linear-gradient(to right, #0d47a1, #00b4d8, #00d26a, #ffd43b, #ff4757);
            border-radius: 4px;
        }

        /* Sankey styles */
        .sankey-node rect {
            fill-opacity: 0.9;
            stroke-width: 1px;
        }

        .sankey-link {
            fill-opacity: 0.3;
            stroke-opacity: 0.3;
        }

        .sankey-link:hover {
            fill-opacity: 0.5;
            stroke-opacity: 0.5;
        }

        /* Stats overlay */
        .stats-overlay {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(21, 23, 30, 0.9);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 12px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            z-index: 10;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            gap: 20px;
            padding: 4px 0;
        }

        .stat-label {
            color: var(--text-muted);
        }

        .stat-value {
            color: var(--accent-green);
            font-weight: 600;
        }

        .loading {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-muted);
        }

        .loading::after {
            content: '';
            width: 24px;
            height: 24px;
            border: 2px solid var(--border-color);
            border-top-color: var(--accent-blue);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin-left: 12px;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* ML Probability Overlay */
        .ml-overlay {
            position: absolute;
            top: 60px;
            left: 20px;
            background: rgba(21, 23, 30, 0.95);
            border: 1px solid var(--accent-purple);
            border-radius: 12px;
            padding: 16px;
            min-width: 200px;
            z-index: 10;
        }

        .ml-title {
            font-size: 12px;
            color: var(--accent-purple);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 12px;
        }

        .ml-prob-bar {
            height: 8px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            margin: 8px 0;
        }

        .ml-prob-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-purple), var(--accent-blue));
            transition: width 0.3s ease;
        }

        .ml-signal {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
        }

        .signal-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        .signal-dot.high { background: var(--accent-green); }
        .signal-dot.medium { background: var(--accent-yellow); }
        .signal-dot.low { background: var(--text-muted); }
    </style>
</head>
<body>
    <div class="bg-pattern"></div>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">📊</div>
                <h1>Advanced Analytics</h1>
            </div>
            <div class="nav-tabs">
                <a href="/" class="nav-tab">Dashboard</a>
                <a href="/advanced" class="nav-tab active">Advanced</a>
                <a href="/api/state" class="nav-tab">API</a>
            </div>
        </header>

        <div class="viz-grid">
            <!-- Order Book Heatmap -->
            <div class="viz-card">
                <div class="viz-header">
                    <div class="viz-title"><span>🔥</span> Order Book Heatmap</div>
                    <div class="viz-controls">
                        <button class="viz-btn" onclick="toggleHeatmapPair()">BTC/USDT</button>
                        <button class="viz-btn" onclick="refreshHeatmap()">Refresh</button>
                    </div>
                </div>
                <div class="viz-body">
                    <div id="heatmap-container"><div class="loading">Loading heatmap</div></div>
                    <div class="heatmap-legend">
                        <span>Low Depth</span>
                        <div class="legend-gradient"></div>
                        <span>High Depth</span>
                    </div>
                </div>
            </div>

            <!-- Opportunity Flow Sankey -->
            <div class="viz-card">
                <div class="viz-header">
                    <div class="viz-title"><span>🌊</span> Opportunity Flow</div>
                    <div class="viz-controls">
                        <button class="viz-btn" onclick="toggleSankeyType()">Triangular</button>
                    </div>
                </div>
                <div class="viz-body">
                    <div id="sankey-container"><div class="loading">Loading flow diagram</div></div>
                </div>
            </div>

            <!-- Latency Globe -->
            <div class="viz-card">
                <div class="viz-header">
                    <div class="viz-title"><span>🌍</span> Exchange Latency Globe</div>
                    <div class="viz-controls">
                        <button class="viz-btn" onclick="toggleGlobeView()">Rotate</button>
                    </div>
                </div>
                <div class="viz-body" style="position: relative;">
                    <div id="globe-container"><div class="loading">Loading globe</div></div>
                    <div class="stats-overlay">
                        <div class="stat-row">
                            <span class="stat-label">Avg Latency:</span>
                            <span class="stat-value" id="avgLatency">--ms</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Fastest:</span>
                            <span class="stat-value" id="fastestExchange">--</span>
                        </div>
                        <div class="stat-row">
                            <span class="stat-label">Slowest:</span>
                            <span class="stat-value" id="slowestExchange">--</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3D Market Visualization -->
            <div class="viz-card">
                <div class="viz-header">
                    <div class="viz-title"><span>🎮</span> 3D Market Surface</div>
                    <div class="viz-controls">
                        <button class="viz-btn" onclick="toggle3DView()">Rotate</button>
                        <button class="viz-btn" onclick="reset3DCamera()">Reset</button>
                    </div>
                </div>
                <div class="viz-body" style="position: relative;">
                    <div id="threejs-container"><div class="loading">Loading 3D view</div></div>
                    <div class="ml-overlay">
                        <div class="ml-title">🤖 ML Prediction</div>
                        <div style="font-size: 24px; font-weight: 700; color: var(--text-primary);" id="mlProbability">--</div>
                        <div class="ml-prob-bar">
                            <div class="ml-prob-fill" id="mlProbBar" style="width: 0%"></div>
                        </div>
                        <div class="ml-signal">
                            <div class="signal-dot" id="mlSignalDot"></div>
                            <span id="mlSignalText" style="font-size: 12px; color: var(--text-secondary);">Waiting...</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // ==================== STATE ====================
        let wsConnection = null;
        let heatmapData = {};
        let sankeyData = { nodes: [], links: [] };
        let globeInstance = null;
        let threeScene = null;
        let currentPair = 'BTC/USDT';
        let mlPrediction = { probability: 0, signal: 'low' };

        // Exchange locations for globe
        const exchangeLocations = {
            'Binance': { lat: 1.3521, lng: 103.8198, city: 'Singapore' },
            'Coinbase': { lat: 37.7749, lng: -122.4194, city: 'San Francisco' },
            'Kraken': { lat: 37.7749, lng: -122.4194, city: 'San Francisco' },
            'Bybit': { lat: 1.3521, lng: 103.8198, city: 'Singapore' },
            'OKX': { lat: 22.3193, lng: 114.1694, city: 'Hong Kong' },
        };

        // ==================== WEBSOCKET ====================
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            wsConnection = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            wsConnection.onopen = () => console.log('Advanced dashboard connected');
            wsConnection.onclose = () => setTimeout(connectWebSocket, 3000);
            wsConnection.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleMessage(message);
            };
        }

        function handleMessage(message) {
            switch(message.type) {
                case 'price':
                    updateHeatmapData(message.data);
                    update3DVisualization(message.data);
                    break;
                case 'opportunity':
                case 'triangular_opportunity':
                    updateSankeyData(message.data);
                    break;
                case 'ml_prediction':
                    updateMLPrediction(message.data);
                    break;
            }
        }

        // ==================== HEATMAP ====================
        function updateHeatmapData(priceData) {
            const key = `${priceData.exchange}-${priceData.pair}`;
            if (!heatmapData[priceData.pair]) {
                heatmapData[priceData.pair] = {};
            }
            heatmapData[priceData.pair][priceData.exchange] = {
                bid: priceData.bid,
                ask: priceData.ask,
                timestamp: new Date()
            };
            
            if (priceData.pair === currentPair) {
                renderHeatmap();
            }
        }

        function renderHeatmap() {
            const container = document.getElementById('heatmap-container');
            const pairData = heatmapData[currentPair] || {};
            const exchanges = Object.keys(pairData);
            
            if (exchanges.length === 0) {
                container.innerHTML = '<div class="loading">Waiting for data</div>';
                return;
            }

            // Generate synthetic order book depth data
            const levels = 20;
            const zData = [];
            const xLabels = exchanges;
            const yLabels = [];
            
            // Create price levels
            const midPrices = exchanges.map(ex => (pairData[ex].bid + pairData[ex].ask) / 2);
            const avgMid = midPrices.reduce((a,b) => a+b, 0) / midPrices.length;
            
            for (let i = -levels/2; i < levels/2; i++) {
                const priceLevel = avgMid * (1 + i * 0.0005);
                yLabels.push(priceLevel.toFixed(2));
                
                const row = exchanges.map((ex, idx) => {
                    const bid = pairData[ex].bid;
                    const ask = pairData[ex].ask;
                    const mid = midPrices[idx];
                    
                    // Simulate depth (higher near mid price)
                    const distFromMid = Math.abs(priceLevel - mid) / mid;
                    let depth = Math.exp(-distFromMid * 200) * (1 + Math.random() * 0.3);
                    
                    // Bid side vs ask side
                    if (priceLevel < bid) {
                        depth *= 1.2; // More depth on bid side typically
                    } else if (priceLevel > ask) {
                        depth *= 0.8;
                    }
                    
                    return depth;
                });
                zData.push(row);
            }

            const trace = {
                z: zData,
                x: xLabels,
                y: yLabels,
                type: 'heatmap',
                colorscale: [
                    [0, '#0d47a1'],
                    [0.25, '#00b4d8'],
                    [0.5, '#00d26a'],
                    [0.75, '#ffd43b'],
                    [1, '#ff4757']
                ],
                showscale: false,
                hoverongaps: false,
            };

            const layout = {
                paper_bgcolor: 'transparent',
                plot_bgcolor: 'transparent',
                font: { color: '#9aa0a6', family: 'Outfit' },
                margin: { t: 20, r: 20, b: 40, l: 80 },
                xaxis: { title: 'Exchange', gridcolor: '#2a2d3a' },
                yaxis: { title: 'Price Level', gridcolor: '#2a2d3a' },
            };

            Plotly.newPlot('heatmap-container', [trace], layout, { responsive: true });
        }

        function toggleHeatmapPair() {
            const pairs = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'];
            const idx = pairs.indexOf(currentPair);
            currentPair = pairs[(idx + 1) % pairs.length];
            document.querySelector('.viz-controls .viz-btn').textContent = currentPair;
            renderHeatmap();
        }

        function refreshHeatmap() {
            renderHeatmap();
        }

        // ==================== SANKEY DIAGRAM ====================
        function updateSankeyData(oppData) {
            // Build Sankey data from opportunity
            const nodes = [];
            const links = [];
            const nodeMap = {};
            
            let nodeIdx = 0;
            const getNodeIdx = (name) => {
                if (!(name in nodeMap)) {
                    nodeMap[name] = nodeIdx++;
                    nodes.push({ name });
                }
                return nodeMap[name];
            };

            if (oppData.type === 'triangular' || oppData.pairs) {
                // Triangular arbitrage flow
                const baseCurrency = oppData.base_currency || 'USDT';
                const exchange = oppData.exchange || 'Exchange';
                
                const startIdx = getNodeIdx(`${baseCurrency} (Start)`);
                
                if (oppData.pairs) {
                    oppData.pairs.forEach((pair, i) => {
                        const [base, quote] = pair.split('/');
                        const side = oppData.sides ? oppData.sides[i] : 'trade';
                        
                        const sourceIdx = i === 0 ? startIdx : getNodeIdx(oppData.pairs[i-1].split('/')[0]);
                        const targetIdx = getNodeIdx(base);
                        
                        links.push({
                            source: sourceIdx,
                            target: targetIdx,
                            value: 10000 / (i + 1),
                        });
                    });
                    
                    // Complete the cycle
                    const lastPair = oppData.pairs[oppData.pairs.length - 1];
                    const lastBase = lastPair.split('/')[0];
                    links.push({
                        source: getNodeIdx(lastBase),
                        target: getNodeIdx(`${baseCurrency} (End)`),
                        value: 10000 * (1 + (oppData.profit_percent || 0) / 100),
                    });
                }
            } else {
                // Simple cross-exchange arbitrage
                const startIdx = getNodeIdx('Capital');
                const buyIdx = getNodeIdx(`Buy @ ${oppData.buy_exchange || 'Exchange A'}`);
                const sellIdx = getNodeIdx(`Sell @ ${oppData.sell_exchange || 'Exchange B'}`);
                const profitIdx = getNodeIdx('Profit');
                
                links.push(
                    { source: startIdx, target: buyIdx, value: 10000 },
                    { source: buyIdx, target: sellIdx, value: 10000 },
                    { source: sellIdx, target: profitIdx, value: 10000 * (1 + (oppData.profit_percent || 0) / 100) }
                );
            }

            sankeyData = { nodes, links };
            renderSankey();
        }

        function renderSankey() {
            const container = document.getElementById('sankey-container');
            
            if (sankeyData.nodes.length === 0) {
                // Generate sample data
                sankeyData = {
                    nodes: [
                        { name: 'USDT (Start)' },
                        { name: 'BTC' },
                        { name: 'ETH' },
                        { name: 'USDT (End)' },
                    ],
                    links: [
                        { source: 0, target: 1, value: 10000 },
                        { source: 1, target: 2, value: 9900 },
                        { source: 2, target: 3, value: 10050 },
                    ]
                };
            }

            container.innerHTML = '';
            
            const width = container.clientWidth;
            const height = 380;
            
            const svg = d3.select('#sankey-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            const sankey = d3.sankey()
                .nodeId(d => d.name)
                .nodeWidth(20)
                .nodePadding(20)
                .extent([[20, 20], [width - 20, height - 20]]);

            const { nodes, links } = sankey({
                nodes: sankeyData.nodes.map(d => Object.assign({}, d)),
                links: sankeyData.links.map(d => Object.assign({}, d))
            });

            // Color scale
            const colorScale = d3.scaleOrdinal()
                .domain(['USDT', 'BTC', 'ETH', 'SOL', 'XRP'])
                .range(['#00d26a', '#f7931a', '#627eea', '#9945ff', '#00aae4']);

            // Draw links
            svg.append('g')
                .selectAll('path')
                .data(links)
                .join('path')
                .attr('class', 'sankey-link')
                .attr('d', d3.sankeyLinkHorizontal())
                .attr('stroke', d => colorScale(d.source.name.split(' ')[0]))
                .attr('stroke-width', d => Math.max(1, d.width))
                .attr('fill', 'none')
                .style('mix-blend-mode', 'screen');

            // Draw nodes
            const node = svg.append('g')
                .selectAll('g')
                .data(nodes)
                .join('g');

            node.append('rect')
                .attr('class', 'sankey-node')
                .attr('x', d => d.x0)
                .attr('y', d => d.y0)
                .attr('height', d => d.y1 - d.y0)
                .attr('width', d => d.x1 - d.x0)
                .attr('fill', d => colorScale(d.name.split(' ')[0]))
                .attr('stroke', '#1a1d26');

            node.append('text')
                .attr('x', d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
                .attr('y', d => (d.y1 + d.y0) / 2)
                .attr('dy', '0.35em')
                .attr('text-anchor', d => d.x0 < width / 2 ? 'start' : 'end')
                .attr('fill', '#e8eaed')
                .attr('font-size', '12px')
                .text(d => d.name);
        }

        function toggleSankeyType() {
            // Toggle between different flow types
            renderSankey();
        }

        // ==================== LATENCY GLOBE ====================
        function initGlobe() {
            const container = document.getElementById('globe-container');
            container.innerHTML = '';
            
            // Exchange data with latencies
            const exchangeData = Object.entries(exchangeLocations).map(([name, loc]) => ({
                name,
                lat: loc.lat,
                lng: loc.lng,
                city: loc.city,
                latency: Math.random() * 100 + 20, // Simulated latency
                size: 0.5,
            }));

            // Connection arcs
            const arcsData = [];
            for (let i = 0; i < exchangeData.length; i++) {
                for (let j = i + 1; j < exchangeData.length; j++) {
                    arcsData.push({
                        startLat: exchangeData[i].lat,
                        startLng: exchangeData[i].lng,
                        endLat: exchangeData[j].lat,
                        endLng: exchangeData[j].lng,
                        color: `rgba(0, 180, 216, ${0.3 + Math.random() * 0.4})`,
                    });
                }
            }

            globeInstance = Globe()
                .globeImageUrl('//unpkg.com/three-globe/example/img/earth-night.jpg')
                .bumpImageUrl('//unpkg.com/three-globe/example/img/earth-topology.png')
                .backgroundImageUrl('//unpkg.com/three-globe/example/img/night-sky.png')
                .pointsData(exchangeData)
                .pointLat('lat')
                .pointLng('lng')
                .pointColor(() => '#00d26a')
                .pointAltitude(0.1)
                .pointRadius(0.5)
                .pointLabel(d => `<div style="background: rgba(21,23,30,0.9); padding: 8px; border-radius: 4px; font-family: JetBrains Mono, monospace; font-size: 12px;">
                    <strong>${d.name}</strong><br/>
                    ${d.city}<br/>
                    Latency: <span style="color: #00d26a">${d.latency.toFixed(0)}ms</span>
                </div>`)
                .arcsData(arcsData)
                .arcColor('color')
                .arcDashLength(0.4)
                .arcDashGap(0.2)
                .arcDashAnimateTime(2000)
                .arcStroke(0.5)
                .width(container.clientWidth)
                .height(450)
                (container);

            globeInstance.controls().autoRotate = true;
            globeInstance.controls().autoRotateSpeed = 0.5;

            // Update stats
            const latencies = exchangeData.map(e => e.latency);
            document.getElementById('avgLatency').textContent = (latencies.reduce((a,b) => a+b, 0) / latencies.length).toFixed(0) + 'ms';
            
            const fastest = exchangeData.reduce((a, b) => a.latency < b.latency ? a : b);
            const slowest = exchangeData.reduce((a, b) => a.latency > b.latency ? a : b);
            document.getElementById('fastestExchange').textContent = `${fastest.name} (${fastest.latency.toFixed(0)}ms)`;
            document.getElementById('slowestExchange').textContent = `${slowest.name} (${slowest.latency.toFixed(0)}ms)`;
        }

        function toggleGlobeView() {
            if (globeInstance) {
                globeInstance.controls().autoRotate = !globeInstance.controls().autoRotate;
            }
        }

        // ==================== 3D VISUALIZATION ====================
        let threejsRenderer, threejsCamera, threejsControls;
        let priceSurface;

        function init3DVisualization() {
            const container = document.getElementById('threejs-container');
            container.innerHTML = '';
            
            const width = container.clientWidth;
            const height = 450;

            // Scene setup
            threeScene = new THREE.Scene();
            threeScene.background = new THREE.Color(0x0a0b0f);

            // Camera
            threejsCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
            threejsCamera.position.set(5, 5, 5);
            threejsCamera.lookAt(0, 0, 0);

            // Renderer
            threejsRenderer = new THREE.WebGLRenderer({ antialias: true });
            threejsRenderer.setSize(width, height);
            threejsRenderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(threejsRenderer.domElement);

            // Lights
            const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
            threeScene.add(ambientLight);

            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(5, 10, 5);
            threeScene.add(directionalLight);

            // Create price surface
            createPriceSurface();

            // Grid helper
            const gridHelper = new THREE.GridHelper(10, 20, 0x2a2d3a, 0x1a1d26);
            gridHelper.position.y = -1;
            threeScene.add(gridHelper);

            // Axes labels (simplified)
            createAxisLabels();

            // Animation loop
            animate3D();
        }

        function createPriceSurface() {
            const size = 30;
            const geometry = new THREE.PlaneGeometry(4, 4, size - 1, size - 1);
            
            // Create height data
            const positions = geometry.attributes.position.array;
            const colors = new Float32Array(positions.length);
            
            for (let i = 0; i < positions.length; i += 3) {
                const x = positions[i];
                const z = positions[i + 1];
                
                // Create interesting surface (simulated price landscape)
                const height = Math.sin(x * 2) * Math.cos(z * 2) * 0.5 + 
                              Math.sin(x * 4 + z * 3) * 0.2 +
                              Math.random() * 0.1;
                positions[i + 2] = height;
                
                // Color based on height
                const t = (height + 0.7) / 1.4;
                colors[i] = t < 0.5 ? t * 2 : 1;
                colors[i + 1] = 0.8;
                colors[i + 2] = t > 0.5 ? (1 - t) * 2 : 1;
            }
            
            geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
            geometry.computeVertexNormals();

            const material = new THREE.MeshPhongMaterial({
                vertexColors: true,
                side: THREE.DoubleSide,
                shininess: 30,
                wireframe: false,
            });

            priceSurface = new THREE.Mesh(geometry, material);
            priceSurface.rotation.x = -Math.PI / 2;
            threeScene.add(priceSurface);

            // Add wireframe overlay
            const wireframeMaterial = new THREE.MeshBasicMaterial({
                color: 0x00b4d8,
                wireframe: true,
                transparent: true,
                opacity: 0.1,
            });
            const wireframe = new THREE.Mesh(geometry.clone(), wireframeMaterial);
            wireframe.rotation.x = -Math.PI / 2;
            threeScene.add(wireframe);
        }

        function createAxisLabels() {
            // This would use CSS2DRenderer in production
            // Simplified for demo
        }

        function update3DVisualization(priceData) {
            if (!priceSurface) return;
            
            // Update surface based on price data
            const positions = priceSurface.geometry.attributes.position.array;
            
            // Add subtle animation
            const time = Date.now() * 0.001;
            for (let i = 0; i < positions.length; i += 3) {
                const x = positions[i];
                const z = positions[i + 1];
                positions[i + 2] += Math.sin(time + x * 2 + z * 2) * 0.002;
            }
            
            priceSurface.geometry.attributes.position.needsUpdate = true;
            priceSurface.geometry.computeVertexNormals();
        }

        function animate3D() {
            requestAnimationFrame(animate3D);
            
            if (priceSurface) {
                priceSurface.rotation.z += 0.001;
            }
            
            threejsRenderer.render(threeScene, threejsCamera);
        }

        function toggle3DView() {
            if (priceSurface) {
                priceSurface.material.wireframe = !priceSurface.material.wireframe;
            }
        }

        function reset3DCamera() {
            threejsCamera.position.set(5, 5, 5);
            threejsCamera.lookAt(0, 0, 0);
        }

        // ==================== ML PREDICTION ====================
        function updateMLPrediction(predData) {
            mlPrediction = predData;
            
            const prob = (predData.probability * 100).toFixed(1);
            document.getElementById('mlProbability').textContent = prob + '%';
            document.getElementById('mlProbBar').style.width = prob + '%';
            
            const signalDot = document.getElementById('mlSignalDot');
            const signalText = document.getElementById('mlSignalText');
            
            signalDot.className = 'signal-dot ' + (predData.details?.signal || 'low').toLowerCase();
            signalText.textContent = `Signal: ${(predData.details?.signal || 'LOW').toUpperCase()}`;
        }

        // Simulate ML predictions
        function simulateMLPredictions() {
            setInterval(() => {
                const prob = 0.3 + Math.random() * 0.5;
                let signal = 'low';
                if (prob > 0.6) signal = 'high';
                else if (prob > 0.4) signal = 'medium';
                
                updateMLPrediction({
                    probability: prob,
                    details: { signal }
                });
            }, 2000);
        }

        // ==================== INITIALIZATION ====================
        document.addEventListener('DOMContentLoaded', () => {
            connectWebSocket();
            
            // Initialize visualizations after a short delay
            setTimeout(() => {
                renderHeatmap();
                renderSankey();
                initGlobe();
                init3DVisualization();
                simulateMLPredictions();
            }, 500);
            
            // Handle resize
            window.addEventListener('resize', () => {
                if (globeInstance) {
                    const container = document.getElementById('globe-container');
                    globeInstance.width(container.clientWidth);
                }
                
                if (threejsRenderer) {
                    const container = document.getElementById('threejs-container');
                    threejsRenderer.setSize(container.clientWidth, 450);
                    threejsCamera.aspect = container.clientWidth / 450;
                    threejsCamera.updateProjectionMatrix();
                }
            });
        });
    </script>
</body>
</html>
"""

# FastAPI route for advanced dashboard
def register_advanced_dashboard(app):
    """Register advanced dashboard routes with FastAPI app"""
    from fastapi.responses import HTMLResponse
    
    @app.get("/advanced", response_class=HTMLResponse)
    async def advanced_dashboard():
        """Serve the advanced analytics dashboard"""
        return ADVANCED_DASHBOARD_HTML
    
    @app.get("/api/heatmap/{pair}")
    async def get_heatmap_data(pair: str):
        """Get order book heatmap data for a pair"""
        # This would return actual order book depth data
        return {
            "pair": pair.replace("-", "/"),
            "exchanges": ["Binance", "Bybit", "OKX"],
            "data": []  # Would be populated from orderbook_engine
        }
    
    @app.get("/api/sankey")
    async def get_sankey_data():
        """Get Sankey flow diagram data"""
        return {
            "nodes": [],
            "links": []
        }
    
    @app.get("/api/globe/latencies")
    async def get_globe_latencies():
        """Get exchange latency data for globe"""
        return {
            "exchanges": [
                {"name": "Binance", "lat": 1.3521, "lng": 103.8198, "latency": 45},
                {"name": "Coinbase", "lat": 37.7749, "lng": -122.4194, "latency": 120},
                {"name": "Kraken", "lat": 37.7749, "lng": -122.4194, "latency": 150},
                {"name": "Bybit", "lat": 1.3521, "lng": 103.8198, "latency": 50},
                {"name": "OKX", "lat": 22.3193, "lng": 114.1694, "latency": 65},
            ]
        }
