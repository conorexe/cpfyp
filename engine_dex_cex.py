"""
DEX/CEX Arbitrage Engine

Detects arbitrage opportunities between decentralized exchanges (DEX) and 
centralized exchanges (CEX).

Example:
  Uniswap ETH/USDC: $3,150
  Binance ETH/USDT: $3,155
  → Buy on Uniswap, Sell on Binance for 0.16% profit

Key considerations:
- Gas costs on DEX transactions
- Slippage on AMM pools
- Block confirmation times
- Bridge costs for cross-chain
- MEV (Maximal Extractable Value) competition
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from collections import defaultdict, deque
import math

logger = logging.getLogger(__name__)


@dataclass
class DEXPool:
    """Represents a liquidity pool on a DEX"""
    dex: str  # "Uniswap", "SushiSwap", "Curve", "PancakeSwap"
    chain: str  # "Ethereum", "BSC", "Polygon", "Arbitrum"
    pair: str
    token0_reserve: float
    token1_reserve: float
    fee_tier: float  # 0.003 for 0.3%
    liquidity_usd: float
    last_update: datetime
    
    def get_price(self) -> float:
        """Get spot price from reserves (x * y = k)"""
        if self.token0_reserve == 0:
            return 0
        return self.token1_reserve / self.token0_reserve
    
    def get_output_amount(self, input_amount: float, input_is_token0: bool) -> float:
        """Calculate output for a given input using constant product formula"""
        if input_is_token0:
            input_reserve = self.token0_reserve
            output_reserve = self.token1_reserve
        else:
            input_reserve = self.token1_reserve
            output_reserve = self.token0_reserve
        
        # Apply fee
        input_with_fee = input_amount * (1 - self.fee_tier)
        
        # Constant product formula: (x + dx) * (y - dy) = x * y
        # dy = y * dx / (x + dx)
        output_amount = (output_reserve * input_with_fee) / (input_reserve + input_with_fee)
        
        return output_amount
    
    def get_price_impact(self, input_amount: float, input_is_token0: bool) -> float:
        """Calculate price impact for a given trade size"""
        if input_is_token0:
            reserve = self.token0_reserve
        else:
            reserve = self.token1_reserve
        
        # Simplified price impact: trade_size / reserve
        return input_amount / reserve


@dataclass  
class GasEstimate:
    """Gas cost estimation for DEX operations"""
    chain: str
    gas_price_gwei: float
    swap_gas_units: int
    bridge_gas_units: int
    eth_price_usd: float
    
    def swap_cost_usd(self) -> float:
        gas_cost_eth = (self.swap_gas_units * self.gas_price_gwei) / 1e9
        return gas_cost_eth * self.eth_price_usd
    
    def bridge_cost_usd(self) -> float:
        gas_cost_eth = (self.bridge_gas_units * self.gas_price_gwei) / 1e9
        return gas_cost_eth * self.eth_price_usd


@dataclass
class DexCexOpportunity:
    """Represents a DEX/CEX arbitrage opportunity"""
    dex: str
    dex_chain: str
    cex: str
    pair: str
    direction: str  # "dex_to_cex" or "cex_to_dex"
    dex_price: float
    cex_price: float
    price_diff_percent: float
    trade_size_usd: float
    gross_profit_usd: float
    gas_cost_usd: float
    net_profit_usd: float
    net_profit_percent: float
    price_impact: float
    slippage_estimate: float
    liquidity_usd: float
    execution_time_estimate_s: int  # Seconds for execution
    mev_risk: str  # "low", "medium", "high"
    confidence: float
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "type": "dex_cex_arbitrage",
            "dex": self.dex,
            "dex_chain": self.dex_chain,
            "cex": self.cex,
            "pair": self.pair,
            "direction": self.direction,
            "action": self._get_action(),
            "dex_price": round(self.dex_price, 4),
            "cex_price": round(self.cex_price, 4),
            "price_diff_percent": round(self.price_diff_percent, 4),
            "trade_size_usd": round(self.trade_size_usd, 2),
            "gross_profit_usd": round(self.gross_profit_usd, 2),
            "gas_cost_usd": round(self.gas_cost_usd, 2),
            "net_profit_usd": round(self.net_profit_usd, 2),
            "net_profit_percent": round(self.net_profit_percent, 4),
            "price_impact": round(self.price_impact * 100, 4),
            "slippage_estimate": round(self.slippage_estimate * 100, 4),
            "liquidity_usd": round(self.liquidity_usd, 0),
            "execution_time_estimate_s": self.execution_time_estimate_s,
            "mev_risk": self.mev_risk,
            "confidence": round(self.confidence, 2),
            "timestamp": self.timestamp.isoformat(),
        }
    
    def _get_action(self) -> str:
        if self.direction == "dex_to_cex":
            return f"BUY on {self.dex} ({self.dex_chain}), SELL on {self.cex}"
        else:
            return f"BUY on {self.cex}, SELL on {self.dex} ({self.dex_chain})"


class DexCexArbitrageEngine:
    """
    Detects arbitrage opportunities between DEXs and CEXs.
    
    Challenges:
    1. Gas costs can eat into profits
    2. DEX prices have slippage based on trade size
    3. Block times introduce delay risk
    4. MEV bots compete for the same opportunities
    5. Cross-chain bridges add complexity and cost
    
    Strategies:
    - Flash loans for capital efficiency
    - Backrunning strategies
    - Cross-chain arbitrage via bridges
    """
    
    # DEX configurations
    DEX_CONFIGS = {
        "Uniswap_V3": {"chain": "Ethereum", "fee_tiers": [0.0005, 0.003, 0.01], "gas_units": 150000},
        "Uniswap_V2": {"chain": "Ethereum", "fee_tiers": [0.003], "gas_units": 120000},
        "SushiSwap": {"chain": "Ethereum", "fee_tiers": [0.003], "gas_units": 120000},
        "PancakeSwap": {"chain": "BSC", "fee_tiers": [0.0025], "gas_units": 100000},
        "QuickSwap": {"chain": "Polygon", "fee_tiers": [0.003], "gas_units": 100000},
        "Curve": {"chain": "Ethereum", "fee_tiers": [0.0004], "gas_units": 200000},
    }
    
    # Chain configurations
    CHAIN_CONFIGS = {
        "Ethereum": {"block_time_s": 12, "gas_price_gwei": 30, "native_token": "ETH"},
        "BSC": {"block_time_s": 3, "gas_price_gwei": 5, "native_token": "BNB"},
        "Polygon": {"block_time_s": 2, "gas_price_gwei": 100, "native_token": "MATIC"},
        "Arbitrum": {"block_time_s": 0.25, "gas_price_gwei": 0.1, "native_token": "ETH"},
    }
    
    def __init__(
        self,
        min_profit_percent: float = 0.1,   # Minimum profit after gas
        max_trade_size_usd: float = 50000,  # Max trade size
        max_price_impact: float = 0.005,    # 0.5% max price impact
    ):
        self.min_profit_percent = min_profit_percent
        self.max_trade_size_usd = max_trade_size_usd
        self.max_price_impact = max_price_impact
        
        # CEX prices: exchange -> pair -> (bid, ask)
        self.cex_prices: Dict[str, Dict[str, Tuple[float, float]]] = defaultdict(dict)
        
        # Simulated DEX pools
        self.dex_pools: Dict[str, Dict[str, DEXPool]] = defaultdict(dict)
        
        # Gas estimates
        self.gas_estimates: Dict[str, GasEstimate] = {}
        
        # Current opportunities
        self.opportunities: List[DexCexOpportunity] = []
        
        # History
        self.history: List[DexCexOpportunity] = []
        
        # Price history for volatility estimation
        self.price_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Callbacks
        self._on_opportunity_callbacks: List = []
        
        # Initialize gas estimates
        self._initialize_gas_estimates()
    
    def on_opportunity(self, callback):
        """Register callback for new opportunities"""
        self._on_opportunity_callbacks.append(callback)
    
    def _initialize_gas_estimates(self):
        """Initialize gas cost estimates for each chain"""
        # Simulated ETH price
        eth_price = 3200  # Would come from actual price feed
        
        for chain, config in self.CHAIN_CONFIGS.items():
            self.gas_estimates[chain] = GasEstimate(
                chain=chain,
                gas_price_gwei=config["gas_price_gwei"],
                swap_gas_units=150000,
                bridge_gas_units=200000,
                eth_price_usd=eth_price if config["native_token"] == "ETH" else 300
            )
    
    def update_price(self, exchange: str, pair: str, bid: float, ask: float):
        """Update CEX price and simulate DEX pool data"""
        self.cex_prices[exchange][pair] = (bid, ask)
        mid_price = (bid + ask) / 2
        
        # Track price history
        self.price_history[f"{exchange}:{pair}"].append((mid_price, datetime.now()))
        
        # Simulate DEX pools for common DEXs
        self._simulate_dex_pools(pair, mid_price)
        
        # Check for opportunities
        self._check_opportunities(exchange, pair)
    
    def _simulate_dex_pools(self, pair: str, cex_price: float):
        """
        Simulate DEX pool states.
        In production, would fetch actual pool data from blockchain.
        """
        import random
        
        # Map CEX pairs to DEX tokens
        pair_mapping = {
            "BTC/USDT": ("WBTC", "USDC"),
            "ETH/USDT": ("WETH", "USDC"),
            "SOL/USDT": ("SOL", "USDC"),
            "XRP/USDT": ("XRP", "USDC"),
        }
        
        if pair not in pair_mapping:
            return
        
        token0, token1 = pair_mapping[pair]
        dex_pair = f"{token0}/{token1}"
        
        for dex_name, config in self.DEX_CONFIGS.items():
            # Simulate price deviation from CEX (DEXs often have slight differences)
            price_deviation = random.gauss(0, 0.002)  # ~0.2% std dev
            dex_price = cex_price * (1 + price_deviation)
            
            # Simulate liquidity (varies by DEX)
            base_liquidity = random.uniform(500000, 5000000)  # $500K - $5M
            
            # Calculate reserves from price and liquidity
            # liquidity ≈ 2 * sqrt(reserve0 * reserve1) * price
            # Simplified: reserve1 = liquidity / 2, reserve0 = reserve1 / price
            reserve1 = base_liquidity / 2
            reserve0 = reserve1 / dex_price if dex_price > 0 else 0
            
            pool = DEXPool(
                dex=dex_name,
                chain=config["chain"],
                pair=dex_pair,
                token0_reserve=reserve0,
                token1_reserve=reserve1,
                fee_tier=config["fee_tiers"][0],  # Use lowest fee tier
                liquidity_usd=base_liquidity,
                last_update=datetime.now()
            )
            
            self.dex_pools[dex_name][dex_pair] = pool
    
    def _check_opportunities(self, cex: str, cex_pair: str):
        """Check for DEX/CEX arbitrage opportunities"""
        if cex not in self.cex_prices or cex_pair not in self.cex_prices[cex]:
            return
        
        cex_bid, cex_ask = self.cex_prices[cex][cex_pair]
        cex_mid = (cex_bid + cex_ask) / 2
        
        # Map to DEX pair
        pair_mapping = {
            "BTC/USDT": "WBTC/USDC",
            "ETH/USDT": "WETH/USDC",
            "SOL/USDT": "SOL/USDC",
            "XRP/USDT": "XRP/USDC",
        }
        
        dex_pair = pair_mapping.get(cex_pair)
        if not dex_pair:
            return
        
        new_opportunities = []
        
        for dex_name, pools in self.dex_pools.items():
            if dex_pair not in pools:
                continue
            
            pool = pools[dex_pair]
            dex_price = pool.get_price()
            
            if dex_price == 0:
                continue
            
            config = self.DEX_CONFIGS.get(dex_name, {})
            chain = config.get("chain", "Ethereum")
            
            # Calculate price difference
            price_diff = ((dex_price - cex_mid) / cex_mid) * 100
            
            # Determine optimal trade size based on liquidity and price impact
            trade_size = self._calculate_optimal_trade_size(pool, cex_mid)
            
            if trade_size < 100:  # Minimum $100 trade
                continue
            
            # Calculate price impact
            price_impact = pool.get_price_impact(trade_size / cex_mid, True)
            
            if price_impact > self.max_price_impact:
                continue
            
            # Get gas estimate
            gas_estimate = self.gas_estimates.get(chain)
            gas_cost = gas_estimate.swap_cost_usd() if gas_estimate else 10
            
            # Calculate profits
            if dex_price < cex_mid:
                # DEX cheaper: Buy DEX, Sell CEX
                direction = "dex_to_cex"
                effective_dex_price = dex_price * (1 + pool.fee_tier + price_impact)
                gross_profit = trade_size * ((cex_bid / effective_dex_price) - 1)
            else:
                # CEX cheaper: Buy CEX, Sell DEX
                direction = "cex_to_dex"
                effective_dex_price = dex_price * (1 - pool.fee_tier - price_impact)
                gross_profit = trade_size * ((effective_dex_price / cex_ask) - 1)
            
            net_profit = gross_profit - gas_cost
            net_profit_percent = (net_profit / trade_size) * 100
            
            if net_profit_percent < self.min_profit_percent:
                continue
            
            # Estimate slippage based on volatility
            slippage = self._estimate_slippage(cex, cex_pair, chain)
            
            # Assess MEV risk
            mev_risk = self._assess_mev_risk(net_profit, chain, price_diff)
            
            # Calculate confidence
            confidence = self._calculate_confidence(
                net_profit_percent, price_impact, pool.liquidity_usd, mev_risk
            )
            
            opportunity = DexCexOpportunity(
                dex=dex_name,
                dex_chain=chain,
                cex=cex,
                pair=cex_pair,
                direction=direction,
                dex_price=dex_price,
                cex_price=cex_mid,
                price_diff_percent=abs(price_diff),
                trade_size_usd=trade_size,
                gross_profit_usd=gross_profit,
                gas_cost_usd=gas_cost,
                net_profit_usd=net_profit,
                net_profit_percent=net_profit_percent,
                price_impact=price_impact,
                slippage_estimate=slippage,
                liquidity_usd=pool.liquidity_usd,
                execution_time_estimate_s=self.CHAIN_CONFIGS[chain]["block_time_s"] * 2,
                mev_risk=mev_risk,
                confidence=confidence,
                timestamp=datetime.now()
            )
            
            new_opportunities.append(opportunity)
        
        # Update opportunities
        if new_opportunities:
            # Remove old opportunities for this CEX/pair
            self.opportunities = [
                o for o in self.opportunities 
                if not (o.cex == cex and o.pair == cex_pair)
            ]
            self.opportunities.extend(new_opportunities)
            self.opportunities.sort(key=lambda x: x.net_profit_percent, reverse=True)
            
            # Log best opportunity
            best = max(new_opportunities, key=lambda x: x.net_profit_percent)
            if best.net_profit_percent >= 0.2:
                logger.info(
                    f"🌐 DEX/CEX ARB: {best.dex}↔{best.cex} {best.pair} | "
                    f"{best.direction} | Net: ${best.net_profit_usd:.2f} ({best.net_profit_percent:.3f}%) | "
                    f"MEV Risk: {best.mev_risk}"
                )
            
            # Add to history
            for opp in new_opportunities:
                self.history.append(opp)
            if len(self.history) > 100:
                self.history = self.history[-100:]
            
            # Notify listeners
            for opp in new_opportunities:
                for callback in self._on_opportunity_callbacks:
                    try:
                        callback(opp)
                    except Exception as e:
                        logger.error(f"DEX/CEX callback error: {e}")
    
    def _calculate_optimal_trade_size(self, pool: DEXPool, price: float) -> float:
        """Calculate optimal trade size based on liquidity and price impact"""
        # Start with a fraction of pool liquidity
        max_from_liquidity = pool.liquidity_usd * 0.01  # 1% of liquidity
        
        # Limit by configured max
        trade_size = min(max_from_liquidity, self.max_trade_size_usd)
        
        # Ensure minimum viable size
        return max(100, trade_size)
    
    def _estimate_slippage(self, cex: str, pair: str, chain: str) -> float:
        """Estimate slippage based on recent price volatility"""
        key = f"{cex}:{pair}"
        history = self.price_history.get(key)
        
        if not history or len(history) < 10:
            return 0.005  # Default 0.5%
        
        prices = [h[0] for h in history]
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        
        if not returns:
            return 0.005
        
        volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5
        
        # Adjust for chain block time
        block_time = self.CHAIN_CONFIGS.get(chain, {}).get("block_time_s", 12)
        time_factor = block_time / 12  # Normalize to Ethereum
        
        return volatility * time_factor * 2  # 2x volatility as slippage estimate
    
    def _assess_mev_risk(self, profit: float, chain: str, price_diff: float) -> str:
        """Assess MEV (sandwich attack) risk"""
        # Higher profit = more attractive to MEV bots
        if profit > 500:
            return "high"
        
        # Ethereum mainnet has highest MEV competition
        if chain == "Ethereum":
            if profit > 100 or abs(price_diff) > 0.5:
                return "high"
            return "medium"
        
        # L2s and alt-L1s have less MEV
        if chain in ["Arbitrum", "Polygon"]:
            return "low" if profit < 200 else "medium"
        
        return "medium"
    
    def _calculate_confidence(
        self, 
        profit_percent: float,
        price_impact: float,
        liquidity: float,
        mev_risk: str
    ) -> float:
        """Calculate confidence score for opportunity"""
        # Profit factor
        profit_factor = min(1.0, profit_percent / 1.0)  # Max at 1%
        
        # Impact factor (lower is better)
        impact_factor = 1.0 - min(1.0, price_impact / self.max_price_impact)
        
        # Liquidity factor
        liquidity_factor = min(1.0, liquidity / 1000000)  # Max at $1M
        
        # MEV factor
        mev_factors = {"low": 1.0, "medium": 0.6, "high": 0.3}
        mev_factor = mev_factors.get(mev_risk, 0.5)
        
        confidence = (
            0.3 * profit_factor +
            0.2 * impact_factor +
            0.2 * liquidity_factor +
            0.3 * mev_factor
        )
        
        return max(0.0, min(1.0, confidence))
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "dex_cex_opportunities": [o.to_dict() for o in self.opportunities[:10]],
            "dex_cex_history": [o.to_dict() for o in self.history[-20:]],
            "active_dexs": list(self.dex_pools.keys()),
            "active_cexs": list(self.cex_prices.keys()),
            "gas_estimates": {
                chain: {
                    "swap_cost_usd": round(est.swap_cost_usd(), 2),
                    "gas_price_gwei": est.gas_price_gwei,
                }
                for chain, est in self.gas_estimates.items()
            },
            "config": {
                "min_profit_percent": self.min_profit_percent,
                "max_trade_size_usd": self.max_trade_size_usd,
                "max_price_impact": self.max_price_impact,
            }
        }
