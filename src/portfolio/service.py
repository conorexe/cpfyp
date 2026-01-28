"""
Portfolio management service.
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict
from collections import defaultdict

from .models import (
    Portfolio, PortfolioCreate, PortfolioUpdate, PortfolioSummary,
    Position, PositionCreate,
    Trade, TradeCreate, TradeSide, TradeType,
    ExecuteArbitrageRequest, ExecuteArbitrageResponse,
)

logger = logging.getLogger(__name__)


class PortfolioService:
    """
    Portfolio management service for paper trading.
    
    Provides:
    - Portfolio CRUD operations
    - Position management
    - Trade execution simulation
    - P&L calculation
    """
    
    def __init__(self):
        # In-memory storage (replace with database in production)
        self._portfolios: Dict[int, Dict] = {}
        self._positions: Dict[int, List[Dict]] = defaultdict(list)
        self._trades: Dict[int, List[Dict]] = defaultdict(list)
        
        self._portfolio_id_counter = 1
        self._position_id_counter = 1
        self._trade_id_counter = 1
        
        # Current prices (updated by price feeds)
        self._current_prices: Dict[str, float] = {
            "USDT": 1.0,
            "BTC": 65000.0,
            "ETH": 3500.0,
            "SOL": 150.0,
            "XRP": 0.55,
        }
    
    def update_price(self, asset: str, price: float):
        """Update current price for an asset"""
        self._current_prices[asset.upper()] = price
    
    def get_price(self, asset: str) -> float:
        """Get current price for an asset"""
        return self._current_prices.get(asset.upper(), 0.0)
    
    # Portfolio operations
    
    def create_portfolio(self, user_id: int, data: PortfolioCreate) -> Portfolio:
        """Create a new portfolio for a user"""
        portfolio_id = self._portfolio_id_counter
        self._portfolio_id_counter += 1
        
        # Check if this is the user's first portfolio
        user_portfolios = [p for p in self._portfolios.values() if p["user_id"] == user_id]
        is_default = len(user_portfolios) == 0
        
        portfolio_data = {
            "id": portfolio_id,
            "user_id": user_id,
            "name": data.name,
            "description": data.description,
            "initial_balance": data.initial_balance,
            "current_balance": data.initial_balance,
            "is_default": is_default,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }
        
        self._portfolios[portfolio_id] = portfolio_data
        
        # Initialize with USDT position
        self._add_position(portfolio_id, "USDT", data.initial_balance, 1.0)
        
        logger.info(f"Created portfolio '{data.name}' for user {user_id}")
        
        return Portfolio(**portfolio_data)
    
    def get_portfolio(self, portfolio_id: int, user_id: int) -> Optional[Portfolio]:
        """Get a portfolio by ID (with ownership check)"""
        portfolio = self._portfolios.get(portfolio_id)
        if portfolio and portfolio["user_id"] == user_id:
            return Portfolio(**portfolio)
        return None
    
    def get_user_portfolios(self, user_id: int) -> List[Portfolio]:
        """Get all portfolios for a user"""
        return [
            Portfolio(**p)
            for p in self._portfolios.values()
            if p["user_id"] == user_id
        ]
    
    def get_default_portfolio(self, user_id: int) -> Optional[Portfolio]:
        """Get user's default portfolio"""
        for p in self._portfolios.values():
            if p["user_id"] == user_id and p["is_default"]:
                return Portfolio(**p)
        
        # If no default, return first portfolio
        user_portfolios = self.get_user_portfolios(user_id)
        return user_portfolios[0] if user_portfolios else None
    
    def update_portfolio(
        self, 
        portfolio_id: int, 
        user_id: int, 
        data: PortfolioUpdate
    ) -> Optional[Portfolio]:
        """Update portfolio settings"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio["user_id"] != user_id:
            return None
        
        if data.name is not None:
            portfolio["name"] = data.name
        if data.description is not None:
            portfolio["description"] = data.description
        
        portfolio["updated_at"] = datetime.now()
        
        return Portfolio(**portfolio)
    
    def delete_portfolio(self, portfolio_id: int, user_id: int) -> bool:
        """Delete a portfolio"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio["user_id"] != user_id:
            return False
        
        del self._portfolios[portfolio_id]
        
        if portfolio_id in self._positions:
            del self._positions[portfolio_id]
        if portfolio_id in self._trades:
            del self._trades[portfolio_id]
        
        logger.info(f"Deleted portfolio {portfolio_id}")
        return True
    
    # Position operations
    
    def _add_position(
        self, 
        portfolio_id: int, 
        asset: str, 
        quantity: float, 
        price: float
    ) -> Dict:
        """Internal: Add or update a position"""
        positions = self._positions[portfolio_id]
        
        # Check if position already exists
        for pos in positions:
            if pos["asset"] == asset.upper():
                # Update existing position
                total_value = (pos["quantity"] * pos["avg_entry_price"]) + (quantity * price)
                total_quantity = pos["quantity"] + quantity
                
                if total_quantity > 0:
                    pos["avg_entry_price"] = total_value / total_quantity
                pos["quantity"] = total_quantity
                pos["updated_at"] = datetime.now()
                return pos
        
        # Create new position
        position_data = {
            "id": self._position_id_counter,
            "portfolio_id": portfolio_id,
            "asset": asset.upper(),
            "quantity": quantity,
            "avg_entry_price": price,
            "current_price": self.get_price(asset),
            "updated_at": datetime.now(),
        }
        self._position_id_counter += 1
        positions.append(position_data)
        return position_data
    
    def _reduce_position(
        self, 
        portfolio_id: int, 
        asset: str, 
        quantity: float
    ) -> bool:
        """Internal: Reduce a position"""
        positions = self._positions[portfolio_id]
        
        for pos in positions:
            if pos["asset"] == asset.upper():
                if pos["quantity"] >= quantity:
                    pos["quantity"] -= quantity
                    pos["updated_at"] = datetime.now()
                    return True
        return False
    
    def get_positions(self, portfolio_id: int) -> List[Position]:
        """Get all positions for a portfolio"""
        positions = self._positions.get(portfolio_id, [])
        result = []
        
        for pos in positions:
            if pos["quantity"] <= 0:
                continue
            
            current_price = self.get_price(pos["asset"])
            value = pos["quantity"] * current_price
            cost = pos["quantity"] * pos["avg_entry_price"]
            pnl = value - cost
            pnl_percent = (pnl / cost * 100) if cost > 0 else 0
            
            result.append(Position(
                id=pos["id"],
                portfolio_id=pos["portfolio_id"],
                asset=pos["asset"],
                quantity=pos["quantity"],
                avg_entry_price=pos["avg_entry_price"],
                current_price=current_price,
                unrealized_pnl=pnl,
                unrealized_pnl_percent=pnl_percent,
                value_usd=value,
                updated_at=pos["updated_at"],
            ))
        
        return result
    
    def get_position(self, portfolio_id: int, asset: str) -> Optional[Position]:
        """Get a specific position"""
        positions = self.get_positions(portfolio_id)
        for pos in positions:
            if pos.asset == asset.upper():
                return pos
        return None
    
    # Trade operations
    
    def execute_trade(
        self, 
        portfolio_id: int, 
        user_id: int,
        trade_data: TradeCreate,
        fee_percent: float = 0.1,
    ) -> Optional[Trade]:
        """Execute a simulated trade"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio["user_id"] != user_id:
            return None
        
        # Parse pair to get assets (e.g., "BTC/USDT" -> base="BTC", quote="USDT")
        parts = trade_data.pair.upper().split("/")
        if len(parts) != 2:
            return None
        
        base_asset, quote_asset = parts
        
        # Calculate trade value and fee
        trade_value = trade_data.quantity * trade_data.price
        fee = trade_value * (fee_percent / 100)
        
        if trade_data.side == TradeSide.BUY:
            # Buying: need quote asset, get base asset
            quote_position = self.get_position(portfolio_id, quote_asset)
            if not quote_position or quote_position.quantity < (trade_value + fee):
                logger.warning(f"Insufficient {quote_asset} balance for buy")
                return None
            
            # Reduce quote asset, add base asset
            self._reduce_position(portfolio_id, quote_asset, trade_value + fee)
            self._add_position(portfolio_id, base_asset, trade_data.quantity, trade_data.price)
            
        else:  # SELL
            # Selling: need base asset, get quote asset
            base_position = self.get_position(portfolio_id, base_asset)
            if not base_position or base_position.quantity < trade_data.quantity:
                logger.warning(f"Insufficient {base_asset} balance for sell")
                return None
            
            # Reduce base asset, add quote asset (minus fee)
            self._reduce_position(portfolio_id, base_asset, trade_data.quantity)
            self._add_position(portfolio_id, quote_asset, trade_value - fee, 1.0)
        
        # Record trade
        trade_record = {
            "id": self._trade_id_counter,
            "portfolio_id": portfolio_id,
            "opportunity_id": None,
            "pair": trade_data.pair.upper(),
            "side": trade_data.side.value,
            "quantity": trade_data.quantity,
            "price": trade_data.price,
            "value_usd": trade_value,
            "fee": fee,
            "exchange": trade_data.exchange,
            "trade_type": trade_data.trade_type.value,
            "notes": trade_data.notes,
            "timestamp": datetime.now(),
        }
        
        self._trade_id_counter += 1
        self._trades[portfolio_id].append(trade_record)
        
        # Update portfolio balance
        self._update_portfolio_balance(portfolio_id)
        
        logger.info(f"Executed {trade_data.side.value} trade: {trade_data.quantity} {base_asset} @ {trade_data.price}")
        
        return Trade(**trade_record)
    
    def execute_arbitrage(
        self,
        portfolio_id: int,
        user_id: int,
        request: ExecuteArbitrageRequest,
    ) -> ExecuteArbitrageResponse:
        """Execute an arbitrage opportunity (buy + sell simulation)"""
        portfolio = self._portfolios.get(portfolio_id)
        if not portfolio or portfolio["user_id"] != user_id:
            return ExecuteArbitrageResponse(
                success=False,
                message="Portfolio not found",
                gross_profit=0, total_fees=0, net_profit=0,
                net_profit_percent=0, new_balance=0,
            )
        
        # Parse pair
        parts = request.pair.upper().split("/")
        if len(parts) != 2:
            return ExecuteArbitrageResponse(
                success=False,
                message="Invalid pair format",
                gross_profit=0, total_fees=0, net_profit=0,
                net_profit_percent=0, new_balance=0,
            )
        
        base_asset, quote_asset = parts
        
        # Calculate values
        buy_value = request.quantity * request.buy_price
        sell_value = request.quantity * request.sell_price
        buy_fee = buy_value * (request.buy_fee_percent / 100)
        sell_fee = sell_value * (request.sell_fee_percent / 100)
        
        gross_profit = sell_value - buy_value
        total_fees = buy_fee + sell_fee
        net_profit = gross_profit - total_fees
        net_profit_percent = (net_profit / buy_value * 100) if buy_value > 0 else 0
        
        # Check if profitable
        if net_profit <= 0:
            return ExecuteArbitrageResponse(
                success=False,
                message=f"Trade would result in loss: ${net_profit:.2f}",
                gross_profit=gross_profit, total_fees=total_fees,
                net_profit=net_profit, net_profit_percent=net_profit_percent,
                new_balance=portfolio["current_balance"],
            )
        
        # Check quote asset balance
        total_needed = buy_value + buy_fee
        quote_position = self.get_position(portfolio_id, quote_asset)
        if not quote_position or quote_position.quantity < total_needed:
            return ExecuteArbitrageResponse(
                success=False,
                message=f"Insufficient {quote_asset} balance. Need ${total_needed:.2f}",
                gross_profit=gross_profit, total_fees=total_fees,
                net_profit=net_profit, net_profit_percent=net_profit_percent,
                new_balance=portfolio["current_balance"],
            )
        
        # Execute buy trade
        buy_trade = self.execute_trade(
            portfolio_id, user_id,
            TradeCreate(
                pair=request.pair,
                side=TradeSide.BUY,
                quantity=request.quantity,
                price=request.buy_price,
                exchange=request.buy_exchange,
                trade_type=TradeType.ARBITRAGE,
                notes=f"Arbitrage buy: {request.buy_exchange}",
            ),
            fee_percent=request.buy_fee_percent,
        )
        
        if not buy_trade:
            return ExecuteArbitrageResponse(
                success=False,
                message="Buy trade failed",
                gross_profit=0, total_fees=0, net_profit=0,
                net_profit_percent=0, new_balance=portfolio["current_balance"],
            )
        
        # Execute sell trade
        sell_trade = self.execute_trade(
            portfolio_id, user_id,
            TradeCreate(
                pair=request.pair,
                side=TradeSide.SELL,
                quantity=request.quantity,
                price=request.sell_price,
                exchange=request.sell_exchange,
                trade_type=TradeType.ARBITRAGE,
                notes=f"Arbitrage sell: {request.sell_exchange}",
            ),
            fee_percent=request.sell_fee_percent,
        )
        
        if not sell_trade:
            return ExecuteArbitrageResponse(
                success=False,
                message="Sell trade failed (position may be inconsistent)",
                buy_trade=buy_trade,
                gross_profit=gross_profit, total_fees=total_fees,
                net_profit=net_profit, net_profit_percent=net_profit_percent,
                new_balance=portfolio["current_balance"],
            )
        
        # Update portfolio
        self._update_portfolio_balance(portfolio_id)
        
        return ExecuteArbitrageResponse(
            success=True,
            message=f"Arbitrage executed successfully! Profit: ${net_profit:.2f}",
            buy_trade=buy_trade,
            sell_trade=sell_trade,
            gross_profit=gross_profit,
            total_fees=total_fees,
            net_profit=net_profit,
            net_profit_percent=net_profit_percent,
            new_balance=portfolio["current_balance"],
        )
    
    def get_trades(
        self, 
        portfolio_id: int, 
        limit: int = 50
    ) -> List[Trade]:
        """Get trade history for a portfolio"""
        trades = self._trades.get(portfolio_id, [])
        sorted_trades = sorted(trades, key=lambda x: x["timestamp"], reverse=True)
        return [Trade(**t) for t in sorted_trades[:limit]]
    
    def _update_portfolio_balance(self, portfolio_id: int):
        """Update portfolio's current balance based on positions"""
        positions = self.get_positions(portfolio_id)
        total_value = sum(pos.value_usd for pos in positions)
        
        portfolio = self._portfolios.get(portfolio_id)
        if portfolio:
            portfolio["current_balance"] = total_value
            portfolio["updated_at"] = datetime.now()
    
    # Portfolio summary
    
    def get_portfolio_summary(
        self, 
        portfolio_id: int, 
        user_id: int
    ) -> Optional[PortfolioSummary]:
        """Get comprehensive portfolio summary with statistics"""
        portfolio = self.get_portfolio(portfolio_id, user_id)
        if not portfolio:
            return None
        
        positions = self.get_positions(portfolio_id)
        trades = self.get_trades(portfolio_id, limit=20)
        all_trades = self._trades.get(portfolio_id, [])
        
        # Calculate values
        total_value = sum(pos.value_usd for pos in positions)
        cash_position = next((p for p in positions if p.asset == "USDT"), None)
        cash_balance = cash_position.value_usd if cash_position else 0
        invested_value = total_value - cash_balance
        
        total_pnl = total_value - portfolio.initial_balance
        total_pnl_percent = (total_pnl / portfolio.initial_balance * 100) if portfolio.initial_balance > 0 else 0
        
        # Trade statistics
        total_trades = len(all_trades)
        
        # Calculate P&L per trade (simplified)
        trade_pnls = []
        for i in range(0, len(all_trades) - 1, 2):  # Pair buy/sell trades
            if i + 1 < len(all_trades):
                buy_trade = all_trades[i]
                sell_trade = all_trades[i + 1]
                if buy_trade["side"] == "buy" and sell_trade["side"] == "sell":
                    pnl = sell_trade["value_usd"] - sell_trade["fee"] - buy_trade["value_usd"] - buy_trade["fee"]
                    trade_pnls.append(pnl)
        
        winning_trades = len([p for p in trade_pnls if p > 0])
        losing_trades = len([p for p in trade_pnls if p < 0])
        win_rate = (winning_trades / len(trade_pnls) * 100) if trade_pnls else 0
        
        return PortfolioSummary(
            portfolio=portfolio,
            positions=positions,
            recent_trades=trades,
            total_value=total_value,
            cash_balance=cash_balance,
            invested_value=invested_value,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            best_trade_pnl=max(trade_pnls) if trade_pnls else None,
            worst_trade_pnl=min(trade_pnls) if trade_pnls else None,
            avg_trade_pnl=sum(trade_pnls) / len(trade_pnls) if trade_pnls else None,
        )


# Global portfolio service instance
portfolio_service = PortfolioService()
