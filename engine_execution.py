"""
Execution Simulation Engine

Provides realistic trade execution simulation including:
- Order book-aware slippage modeling
- Exchange-specific fee structures (maker/taker)
- Transfer time simulation between exchanges
- Partial fill simulation
- Order book impact estimation
- Network latency modeling

This is critical for backtesting and evaluating real profitability
of detected arbitrage opportunities.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Callable
from collections import defaultdict
from enum import Enum
import math
import random

logger = logging.getLogger(__name__)


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    IOC = "immediate_or_cancel"
    FOK = "fill_or_kill"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class ExchangeFeeStructure:
    """Fee structure for an exchange"""
    exchange: str
    maker_fee: float  # Fee for limit orders that add liquidity
    taker_fee: float  # Fee for market orders that remove liquidity
    withdrawal_fees: Dict[str, float]  # currency -> fee amount
    min_order_sizes: Dict[str, float]  # pair -> minimum order size
    
    def get_fee(self, is_maker: bool) -> float:
        return self.maker_fee if is_maker else self.taker_fee


@dataclass
class SlippageModel:
    """
    Models slippage based on order size and market conditions.
    
    Slippage factors:
    1. Order book depth - larger orders move through more levels
    2. Volatility - higher volatility = more slippage
    3. Order type - market orders have more slippage than limits
    4. Time of day - low liquidity periods have more slippage
    """
    base_slippage_bps: float = 1.0  # Base slippage in basis points
    size_impact_factor: float = 0.5  # How much size affects slippage
    volatility_factor: float = 2.0  # How much volatility affects slippage
    
    def calculate_slippage(
        self,
        order_size_usd: float,
        avg_daily_volume_usd: float,
        current_volatility: float,  # Standard deviation of returns
        order_book_depth_usd: float,  # Liquidity at best price
        is_market_order: bool = True
    ) -> float:
        """
        Calculate expected slippage as a percentage.
        
        Returns:
            Slippage as decimal (0.001 = 0.1%)
        """
        # Base slippage
        slippage = self.base_slippage_bps / 10000
        
        # Size impact: larger orders relative to volume = more slippage
        if avg_daily_volume_usd > 0:
            size_ratio = order_size_usd / avg_daily_volume_usd
            slippage += self.size_impact_factor * size_ratio * 0.01
        
        # Volatility impact
        slippage += self.volatility_factor * current_volatility
        
        # Order book depth impact
        if order_book_depth_usd > 0:
            depth_ratio = order_size_usd / order_book_depth_usd
            if depth_ratio > 1:
                # Order exceeds top of book
                slippage += (depth_ratio - 1) * 0.001
        
        # Market orders have more slippage than limits
        if is_market_order:
            slippage *= 1.5
        
        # Add randomness (market microstructure noise)
        noise = random.gauss(0, slippage * 0.1)
        slippage += noise
        
        return max(0, slippage)


@dataclass
class TransferSimulator:
    """
    Simulates cryptocurrency transfers between exchanges.
    
    Factors:
    - Blockchain confirmation times
    - Exchange deposit processing
    - Network congestion
    """
    # Average transfer times (seconds) by blockchain
    BLOCKCHAIN_TIMES = {
        "BTC": 600,     # ~10 min (1 confirmation)
        "ETH": 180,     # ~3 min (12 confirmations)
        "SOL": 5,       # ~5 sec
        "XRP": 4,       # ~4 sec
        "USDT_ERC20": 180,
        "USDT_TRC20": 60,
        "USDC": 180,
    }
    
    # Exchange-specific deposit processing times (seconds)
    EXCHANGE_PROCESSING = {
        "Binance": 60,
        "Kraken": 300,
        "Coinbase": 120,
        "Bybit": 60,
        "OKX": 60,
    }
    
    def estimate_transfer_time(
        self,
        currency: str,
        from_exchange: str,
        to_exchange: str,
        network_congestion: float = 1.0  # 1.0 = normal, 2.0 = congested
    ) -> int:
        """
        Estimate transfer time in seconds.
        
        Args:
            currency: Currency being transferred
            from_exchange: Source exchange
            to_exchange: Destination exchange
            network_congestion: Multiplier for blockchain time
        
        Returns:
            Estimated transfer time in seconds
        """
        # Blockchain confirmation time
        blockchain_time = self.BLOCKCHAIN_TIMES.get(currency, 180)
        blockchain_time *= network_congestion
        
        # Exchange processing times
        from_processing = self.EXCHANGE_PROCESSING.get(from_exchange, 120)
        to_processing = self.EXCHANGE_PROCESSING.get(to_exchange, 120)
        
        # Add some variance
        variance = random.gauss(0, 0.1 * blockchain_time)
        
        total_time = blockchain_time + from_processing + to_processing + variance
        return max(10, int(total_time))


@dataclass
class OrderExecution:
    """Result of an order execution simulation"""
    success: bool
    executed_quantity: float
    executed_price: float  # Average fill price
    slippage_percent: float
    fees_paid: float
    fee_currency: str
    execution_time_ms: int
    partial_fill: bool
    fill_ratio: float  # 0-1
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "executed_quantity": round(self.executed_quantity, 8),
            "executed_price": round(self.executed_price, 8),
            "slippage_percent": round(self.slippage_percent * 100, 4),
            "fees_paid": round(self.fees_paid, 8),
            "fee_currency": self.fee_currency,
            "execution_time_ms": self.execution_time_ms,
            "partial_fill": self.partial_fill,
            "fill_ratio": round(self.fill_ratio, 4),
            "error_message": self.error_message,
        }


@dataclass
class ArbitrageExecutionPlan:
    """Plan for executing an arbitrage opportunity"""
    opportunity_id: str
    legs: List[Dict]  # List of order legs
    total_investment: float
    expected_profit: float
    expected_profit_after_fees: float
    expected_slippage_cost: float
    total_fees: float
    estimated_execution_time_ms: int
    requires_transfer: bool
    transfer_time_s: Optional[int]
    risk_score: float
    confidence: float
    
    def to_dict(self) -> dict:
        return {
            "opportunity_id": self.opportunity_id,
            "legs": self.legs,
            "total_investment": round(self.total_investment, 2),
            "expected_profit": round(self.expected_profit, 4),
            "expected_profit_after_fees": round(self.expected_profit_after_fees, 4),
            "expected_slippage_cost": round(self.expected_slippage_cost, 4),
            "total_fees": round(self.total_fees, 4),
            "estimated_execution_time_ms": self.estimated_execution_time_ms,
            "requires_transfer": self.requires_transfer,
            "transfer_time_s": self.transfer_time_s,
            "risk_score": round(self.risk_score, 2),
            "confidence": round(self.confidence, 2),
            "net_profitable": self.expected_profit_after_fees > 0,
        }


class ExecutionSimulator:
    """
    Simulates realistic trade execution for arbitrage strategies.
    
    This is essential for:
    1. Evaluating if detected opportunities are actually profitable
    2. Backtesting strategies on historical data
    3. Optimizing execution parameters
    4. Risk assessment
    """
    
    # Default fee structures for major exchanges
    DEFAULT_FEE_STRUCTURES = {
        "Binance": ExchangeFeeStructure(
            exchange="Binance",
            maker_fee=0.001,  # 0.1%
            taker_fee=0.001,
            withdrawal_fees={"BTC": 0.0002, "ETH": 0.001, "USDT": 1.0},
            min_order_sizes={"BTC/USDT": 10, "ETH/USDT": 10}
        ),
        "Kraken": ExchangeFeeStructure(
            exchange="Kraken",
            maker_fee=0.0016,  # 0.16%
            taker_fee=0.0026,  # 0.26%
            withdrawal_fees={"BTC": 0.0001, "ETH": 0.0025, "USDT": 2.5},
            min_order_sizes={"BTC/USDT": 10, "ETH/USDT": 10}
        ),
        "Coinbase": ExchangeFeeStructure(
            exchange="Coinbase",
            maker_fee=0.004,  # 0.4%
            taker_fee=0.006,  # 0.6%
            withdrawal_fees={"BTC": 0.0, "ETH": 0.0, "USDT": 0.0},  # Free
            min_order_sizes={"BTC/USDT": 1, "ETH/USDT": 1}
        ),
        "Bybit": ExchangeFeeStructure(
            exchange="Bybit",
            maker_fee=0.001,
            taker_fee=0.001,
            withdrawal_fees={"BTC": 0.0002, "ETH": 0.001, "USDT": 1.0},
            min_order_sizes={"BTC/USDT": 1, "ETH/USDT": 1}
        ),
        "OKX": ExchangeFeeStructure(
            exchange="OKX",
            maker_fee=0.0008,  # 0.08%
            taker_fee=0.001,   # 0.1%
            withdrawal_fees={"BTC": 0.0001, "ETH": 0.001, "USDT": 1.0},
            min_order_sizes={"BTC/USDT": 1, "ETH/USDT": 1}
        ),
    }
    
    def __init__(self):
        self.fee_structures = self.DEFAULT_FEE_STRUCTURES.copy()
        self.slippage_model = SlippageModel()
        self.transfer_simulator = TransferSimulator()
        
        # Market data for slippage calculation
        self.daily_volumes: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.order_book_depths: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.volatilities: Dict[str, float] = {}
        
        # Execution history for analysis
        self.execution_history: List[OrderExecution] = []
    
    def update_market_data(
        self,
        exchange: str,
        pair: str,
        daily_volume_usd: float,
        order_book_depth_usd: float,
        volatility: float
    ):
        """Update market data used for slippage calculation"""
        self.daily_volumes[exchange][pair] = daily_volume_usd
        self.order_book_depths[exchange][pair] = order_book_depth_usd
        self.volatilities[pair] = volatility
    
    def simulate_order(
        self,
        exchange: str,
        pair: str,
        side: OrderSide,
        quantity: float,
        price: float,  # Current market price
        order_type: OrderType = OrderType.MARKET
    ) -> OrderExecution:
        """
        Simulate execution of a single order.
        
        Args:
            exchange: Exchange name
            pair: Trading pair
            side: Buy or sell
            quantity: Order quantity in base currency
            price: Current market price
            order_type: Type of order
        
        Returns:
            OrderExecution with simulation results
        """
        order_value_usd = quantity * price
        
        # Get fee structure
        fee_struct = self.fee_structures.get(exchange)
        if not fee_struct:
            fee_struct = ExchangeFeeStructure(
                exchange=exchange,
                maker_fee=0.001,
                taker_fee=0.001,
                withdrawal_fees={},
                min_order_sizes={}
            )
        
        # Check minimum order size
        min_size = fee_struct.min_order_sizes.get(pair, 1.0)
        if order_value_usd < min_size:
            return OrderExecution(
                success=False,
                executed_quantity=0,
                executed_price=0,
                slippage_percent=0,
                fees_paid=0,
                fee_currency="",
                execution_time_ms=0,
                partial_fill=False,
                fill_ratio=0,
                error_message=f"Order below minimum size: ${order_value_usd:.2f} < ${min_size:.2f}"
            )
        
        # Calculate slippage
        daily_vol = self.daily_volumes.get(exchange, {}).get(pair, 10000000)  # Default $10M
        book_depth = self.order_book_depths.get(exchange, {}).get(pair, 100000)  # Default $100K
        volatility = self.volatilities.get(pair, 0.02)  # Default 2%
        
        slippage = self.slippage_model.calculate_slippage(
            order_size_usd=order_value_usd,
            avg_daily_volume_usd=daily_vol,
            current_volatility=volatility,
            order_book_depth_usd=book_depth,
            is_market_order=(order_type == OrderType.MARKET)
        )
        
        # Calculate execution price with slippage
        if side == OrderSide.BUY:
            executed_price = price * (1 + slippage)
        else:
            executed_price = price * (1 - slippage)
        
        # Calculate fees
        is_maker = order_type == OrderType.LIMIT
        fee_rate = fee_struct.get_fee(is_maker)
        fees_paid = order_value_usd * fee_rate
        
        # Simulate partial fills (rare for market orders)
        fill_ratio = 1.0
        partial_fill = False
        if order_type == OrderType.LIMIT:
            # Limit orders might not fill completely
            if random.random() < 0.1:  # 10% chance of partial fill
                fill_ratio = random.uniform(0.5, 0.99)
                partial_fill = True
        
        executed_quantity = quantity * fill_ratio
        
        # Simulate execution time
        base_latency = {
            "Binance": 50,
            "Bybit": 60,
            "OKX": 70,
            "Kraken": 200,
            "Coinbase": 150,
        }
        latency = base_latency.get(exchange, 100)
        execution_time_ms = int(latency + random.gauss(0, latency * 0.2))
        
        execution = OrderExecution(
            success=True,
            executed_quantity=executed_quantity,
            executed_price=executed_price,
            slippage_percent=slippage,
            fees_paid=fees_paid,
            fee_currency="USD",
            execution_time_ms=max(10, execution_time_ms),
            partial_fill=partial_fill,
            fill_ratio=fill_ratio
        )
        
        self.execution_history.append(execution)
        
        return execution
    
    def simulate_arbitrage_execution(
        self,
        buy_exchange: str,
        sell_exchange: str,
        pair: str,
        buy_price: float,
        sell_price: float,
        quantity: float,
        requires_transfer: bool = True
    ) -> ArbitrageExecutionPlan:
        """
        Simulate full arbitrage execution including both legs.
        
        This evaluates whether the opportunity is actually profitable
        after accounting for all costs.
        """
        opportunity_id = f"arb_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        total_investment = quantity * buy_price
        
        # Simulate buy leg
        buy_execution = self.simulate_order(
            exchange=buy_exchange,
            pair=pair,
            side=OrderSide.BUY,
            quantity=quantity,
            price=buy_price,
            order_type=OrderType.MARKET
        )
        
        # Simulate sell leg
        sell_execution = self.simulate_order(
            exchange=sell_exchange,
            pair=pair,
            side=OrderSide.SELL,
            quantity=quantity,
            price=sell_price,
            order_type=OrderType.MARKET
        )
        
        # Calculate transfer time if needed
        transfer_time_s = None
        transfer_fee = 0
        if requires_transfer and buy_exchange != sell_exchange:
            base_currency = pair.split('/')[0]
            transfer_time_s = self.transfer_simulator.estimate_transfer_time(
                currency=base_currency,
                from_exchange=buy_exchange,
                to_exchange=sell_exchange
            )
            # Get withdrawal fee
            buy_fee_struct = self.fee_structures.get(buy_exchange)
            if buy_fee_struct:
                transfer_fee = buy_fee_struct.withdrawal_fees.get(base_currency, 0) * buy_price
        
        # Calculate expected profit
        gross_profit = (sell_execution.executed_price - buy_execution.executed_price) * quantity
        
        # Total costs
        total_fees = buy_execution.fees_paid + sell_execution.fees_paid + transfer_fee
        slippage_cost = (
            buy_execution.slippage_percent * total_investment +
            sell_execution.slippage_percent * (quantity * sell_price)
        )
        
        net_profit = gross_profit - total_fees - slippage_cost
        
        # Calculate execution time
        exec_time_ms = buy_execution.execution_time_ms + sell_execution.execution_time_ms
        
        # Risk assessment
        risk_factors = []
        if requires_transfer:
            risk_factors.append(0.3)  # Transfer risk
        if slippage_cost > gross_profit * 0.1:
            risk_factors.append(0.2)  # High slippage risk
        if total_fees > gross_profit * 0.2:
            risk_factors.append(0.2)  # High fee risk
        
        risk_score = sum(risk_factors)
        confidence = 1.0 - risk_score
        
        # Build execution plan
        plan = ArbitrageExecutionPlan(
            opportunity_id=opportunity_id,
            legs=[
                {
                    "type": "buy",
                    "exchange": buy_exchange,
                    "pair": pair,
                    "price": buy_execution.executed_price,
                    "quantity": buy_execution.executed_quantity,
                    "fees": buy_execution.fees_paid,
                    "slippage": buy_execution.slippage_percent,
                },
                {
                    "type": "sell",
                    "exchange": sell_exchange,
                    "pair": pair,
                    "price": sell_execution.executed_price,
                    "quantity": sell_execution.executed_quantity,
                    "fees": sell_execution.fees_paid,
                    "slippage": sell_execution.slippage_percent,
                }
            ],
            total_investment=total_investment,
            expected_profit=gross_profit,
            expected_profit_after_fees=net_profit,
            expected_slippage_cost=slippage_cost,
            total_fees=total_fees,
            estimated_execution_time_ms=exec_time_ms,
            requires_transfer=requires_transfer,
            transfer_time_s=transfer_time_s,
            risk_score=min(1.0, risk_score),
            confidence=max(0.0, confidence)
        )
        
        return plan
    
    def simulate_triangular_execution(
        self,
        exchange: str,
        path: List[Tuple[str, str, float]],  # [(pair, side, price), ...]
        start_amount: float
    ) -> ArbitrageExecutionPlan:
        """
        Simulate triangular arbitrage execution on a single exchange.
        
        Args:
            exchange: Exchange name
            path: List of (pair, side, price) tuples
            start_amount: Starting amount in base currency (e.g., USDT)
        """
        opportunity_id = f"tri_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        legs = []
        current_amount = start_amount
        total_fees = 0
        total_slippage_cost = 0
        total_exec_time = 0
        
        for pair, side, price in path:
            # Determine quantity based on current holdings
            if side == "buy":
                quantity = current_amount / price
            else:
                quantity = current_amount
            
            execution = self.simulate_order(
                exchange=exchange,
                pair=pair,
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                quantity=quantity,
                price=price,
                order_type=OrderType.MARKET
            )
            
            if not execution.success:
                # Execution failed
                return ArbitrageExecutionPlan(
                    opportunity_id=opportunity_id,
                    legs=legs,
                    total_investment=start_amount,
                    expected_profit=0,
                    expected_profit_after_fees=0,
                    expected_slippage_cost=0,
                    total_fees=total_fees,
                    estimated_execution_time_ms=total_exec_time,
                    requires_transfer=False,
                    transfer_time_s=None,
                    risk_score=1.0,
                    confidence=0.0
                )
            
            legs.append({
                "type": side,
                "exchange": exchange,
                "pair": pair,
                "price": execution.executed_price,
                "quantity": execution.executed_quantity,
                "fees": execution.fees_paid,
                "slippage": execution.slippage_percent,
            })
            
            # Update amounts
            if side == "buy":
                current_amount = execution.executed_quantity
            else:
                current_amount = execution.executed_quantity * execution.executed_price
            
            current_amount -= execution.fees_paid
            total_fees += execution.fees_paid
            total_slippage_cost += execution.slippage_percent * (quantity * price)
            total_exec_time += execution.execution_time_ms
        
        # Calculate profit
        profit = current_amount - start_amount
        
        # Risk score based on number of legs and slippage
        risk_score = min(1.0, len(path) * 0.1 + total_slippage_cost / start_amount)
        
        return ArbitrageExecutionPlan(
            opportunity_id=opportunity_id,
            legs=legs,
            total_investment=start_amount,
            expected_profit=profit + total_fees + total_slippage_cost,  # Gross
            expected_profit_after_fees=profit,  # Net
            expected_slippage_cost=total_slippage_cost,
            total_fees=total_fees,
            estimated_execution_time_ms=total_exec_time,
            requires_transfer=False,
            transfer_time_s=None,
            risk_score=risk_score,
            confidence=1.0 - risk_score
        )
    
    def get_execution_statistics(self) -> dict:
        """Get statistics from execution history"""
        if not self.execution_history:
            return {"total_executions": 0}
        
        successful = [e for e in self.execution_history if e.success]
        
        return {
            "total_executions": len(self.execution_history),
            "successful_executions": len(successful),
            "success_rate": len(successful) / len(self.execution_history),
            "avg_slippage_percent": sum(e.slippage_percent for e in successful) / len(successful) * 100 if successful else 0,
            "avg_execution_time_ms": sum(e.execution_time_ms for e in successful) / len(successful) if successful else 0,
            "partial_fill_rate": sum(1 for e in successful if e.partial_fill) / len(successful) if successful else 0,
            "total_fees_paid": sum(e.fees_paid for e in successful),
        }
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "execution_statistics": self.get_execution_statistics(),
            "supported_exchanges": list(self.fee_structures.keys()),
            "recent_executions": [e.to_dict() for e in self.execution_history[-20:]],
            "slippage_model": {
                "base_slippage_bps": self.slippage_model.base_slippage_bps,
                "size_impact_factor": self.slippage_model.size_impact_factor,
                "volatility_factor": self.slippage_model.volatility_factor,
            }
        }


# Global instance
execution_simulator = ExecutionSimulator()
