# Usage Guide

## Quick Mode Selection

Edit `config.py` and change the `MODE` variable:

```python
MODE = "cpp"         # High-performance C++ engine (recommended for production)
MODE = "python"      # Python WebSocket clients (easy setup)
MODE = "simulation"  # Mock data for testing
```

## Running the Bot

### Python Mode
```bash
python main.py
```
Open http://localhost:8000

### C++ Mode
```bash
# Terminal 1 - Start C++ engine
cd cpp/build
./arb_bot          # Linux/Mac
.\arb_bot.exe      # Windows

# Terminal 2 - Start Python dashboard
python main.py
```
Open http://localhost:8000

### Simulation Mode
```bash
# Set MODE = "simulation" in config.py
python main.py
```
Open http://localhost:8000

## Dashboard Features

### Statistics Bar
- **Active Opportunities**: Current arbitrage opportunities detected
- **Exchanges Connected**: Number of exchanges streaming data
- **Pairs Monitored**: Trading pairs being watched
- **Best Spread**: Highest profit percentage currently available

### Live Opportunities
Shows real-time arbitrage opportunities with:
- Trading pair (e.g., BTC/USDT)
- Profit percentage
- Buy exchange and price
- Sell exchange and price

### Live Prices
Table showing:
- All monitored pairs
- Bid/Ask prices per exchange
- Current spread

### Recent Opportunities
History of detected opportunities with timestamps

## Customizing Configuration

### config.py Options

```python
# Operation mode
MODE = "cpp"  # or "python" or "simulation"

# Trading pairs to monitor
TRADING_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
]

# Minimum profit to flag as opportunity (percentage)
MIN_PROFIT_THRESHOLD = 0.01  # 0.01% = 1 basis point

# WebSocket reconnection
RECONNECT_DELAY = 5              # seconds
MAX_RECONNECT_ATTEMPTS = 10      # before giving up

# Web server
WEB_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_PORT = 8000       # Dashboard port
```

### Adding More Pairs

1. Edit `config.py`:
```python
TRADING_PAIRS = [
    "BTC/USDT",
    "ETH/USDT",
    "DOGE/USDT",  # Add new pair
]
```

2. Update pair mappings for each exchange in `config.py`:
```python
PAIR_MAPPINGS = {
    "binance": {
        "DOGE/USDT": "dogeusdt",
    },
    "kraken": {
        "DOGE/USDT": "DOGE/USDT",
    },
    # etc...
}
```

3. Restart the bot

## Performance Tuning

### Python Mode
- Handles ~1,000 updates/second
- Good for monitoring and development
- Easy to modify and debug

### C++ Mode
- Handles ~10,000+ updates/second
- Sub-millisecond latency
- Recommended for production trading
- Requires compilation

### Adjusting Threshold

Lower threshold = More opportunities (but smaller profits):
```python
MIN_PROFIT_THRESHOLD = 0.01  # Very sensitive
```

Higher threshold = Fewer but more significant opportunities:
```python
MIN_PROFIT_THRESHOLD = 0.5   # Only show good opportunities
```

## Understanding Arbitrage Calculations

The bot detects simple arbitrage:

```
Opportunity exists when:
  Exchange A's ASK price < Exchange B's BID price

Profit % = ((Sell_Bid - Buy_Ask) / Buy_Ask) × 100
```

**Example:**
- Binance: BTC/USDT Ask = $50,000 (you pay this to buy)
- Kraken: BTC/USDT Bid = $50,100 (you receive this when selling)
- Profit = (50,100 - 50,000) / 50,000 × 100 = 0.2%

**Important Notes:**
- This is BEFORE fees (trading + withdrawal)
- Does NOT account for transfer time between exchanges
- Does NOT consider slippage on large orders
- Requires capital on multiple exchanges simultaneously

## Monitoring and Logging

### Console Output

The bot logs:
- Connection status to each exchange
- Detected opportunities with details
- Errors and reconnection attempts

### Log Levels

Adjust in `main.py`:
```python
logging.basicConfig(
    level=logging.INFO,    # Change to DEBUG for more detail
    # level=logging.WARNING,  # Or WARNING for less noise
)
```

## API Endpoints

The dashboard exposes a REST API:

### GET /api/state
Returns current bot state:
```json
{
  "prices": {
    "BTC/USDT": {
      "Binance": {"bid": 50000, "ask": 50001, ...},
      "Kraken": {"bid": 50100, "ask": 50101, ...}
    }
  },
  "opportunities": [...],
  "history": [...],
  "config": {...}
}
```

Usage:
```bash
curl http://localhost:8000/api/state
```

## Best Practices

### Development
1. Start with **simulation mode** to understand the system
2. Test with **Python mode** for real data without compilation
3. Move to **C++ mode** when latency matters

### Production (If Trading Real Money)
1. **Always use C++ mode** for best performance
2. **Monitor exchange fees** - they often exceed arbitrage profits
3. **Account for withdrawal times** - BTC transfers take 30-60 minutes
4. **Start with small amounts** to test the full cycle
5. **Keep funds on multiple exchanges** to act quickly
6. **Monitor API rate limits** - exchanges may block you
7. **Use testnet first** if exchanges offer it

### Security
- Never commit API keys to git
- Use environment variables for sensitive data
- Run on a secure, dedicated server
- Keep dependencies updated

## Troubleshooting

### No opportunities showing
- Lower `MIN_PROFIT_THRESHOLD` in `config.py`
- Verify exchanges are connected (check console logs)
- Real arbitrage is rare - spreads are usually <0.1%

### High CPU usage
- Normal in Python mode with many updates
- C++ mode uses significantly less CPU
- Reduce number of monitored pairs if needed

### Connection errors
- Check internet connectivity
- Verify exchanges aren't blocked (firewall, VPN, DNS)
- Try simulation mode to rule out network issues

### Dashboard not updating
- Check WebSocket connection in browser console (F12)
- Verify bot is running and connected
- Try refreshing the page (Ctrl+R)

## Next Steps

Ready to trade? **DON'T YET!**

Real arbitrage trading requires:
1. ✅ Fast execution (<100ms to catch opportunities)
2. ✅ Exchange accounts with sufficient balances
3. ✅ Understanding of trading fees (typically 0.1-0.2%)
4. ✅ Understanding of withdrawal fees (can be significant)
5. ✅ Risk management strategy
6. ✅ Testing with small amounts first

This bot is an **educational MVP**. For production use:
- Add automated order execution
- Implement proper error handling and retries
- Add position tracking
- Monitor exchange balances
- Calculate fees in real-time
- Implement circuit breakers
- Add alerting and monitoring

Happy hunting! 🎯
