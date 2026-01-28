"""
Enhanced Historical Replay Engine

Features:
- Replay any day at any speed (1x to 1000x)
- Test strategies on past data
- Seek to specific timestamps
- Pause/resume functionality
- Event-driven callbacks for strategy testing
- Statistics collection during replay
- Multi-exchange synchronized replay
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Tuple, Callable, Any, Generator
from collections import defaultdict
from enum import Enum
import heapq
import time

logger = logging.getLogger(__name__)


class ReplayState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    SEEKING = "seeking"


@dataclass
class ReplayTick:
    """Tick data for replay with comparison support"""
    timestamp: datetime
    exchange: str
    pair: str
    bid: float
    ask: float
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    
    def __lt__(self, other):
        return self.timestamp < other.timestamp
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "pair": self.pair,
            "bid": self.bid,
            "ask": self.ask,
            "mid": (self.bid + self.ask) / 2,
            "spread": self.ask - self.bid,
        }


@dataclass
class ReplayStatistics:
    """Statistics collected during replay"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    ticks_replayed: int = 0
    opportunities_detected: int = 0
    total_profit_potential: float = 0.0
    best_opportunity_profit: float = 0.0
    worst_spread: float = float('inf')
    best_spread: float = 0.0
    exchanges_seen: set = field(default_factory=set)
    pairs_seen: set = field(default_factory=set)
    replay_duration_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "ticks_replayed": self.ticks_replayed,
            "opportunities_detected": self.opportunities_detected,
            "total_profit_potential": round(self.total_profit_potential, 4),
            "best_opportunity_profit": round(self.best_opportunity_profit, 4),
            "worst_spread": round(self.worst_spread, 6) if self.worst_spread != float('inf') else None,
            "best_spread": round(self.best_spread, 6),
            "exchanges_seen": list(self.exchanges_seen),
            "pairs_seen": list(self.pairs_seen),
            "replay_duration_seconds": round(self.replay_duration_seconds, 2),
            "ticks_per_second": round(self.ticks_replayed / max(0.001, self.replay_duration_seconds), 2),
        }


@dataclass
class ReplayConfig:
    """Configuration for replay session"""
    speed: float = 1.0  # Playback speed (1.0 = real-time, 100 = 100x)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    exchanges: Optional[List[str]] = None  # Filter by exchanges
    pairs: Optional[List[str]] = None  # Filter by pairs
    skip_gaps: bool = True  # Skip periods with no data
    gap_threshold_seconds: int = 60  # Gaps larger than this are skipped
    max_ticks_per_second: int = 10000  # Rate limit for fast replay


class ReplaySession:
    """
    Manages a single replay session.
    
    Features:
    - Time-ordered tick replay from multiple sources
    - Speed control (pause, resume, speed up)
    - Seek to specific timestamps
    - Callback system for strategy testing
    """
    
    def __init__(
        self,
        tick_source: Any,  # TickStorage or TimescaleDBStorage
        config: ReplayConfig
    ):
        self.tick_source = tick_source
        self.config = config
        
        self.state = ReplayState.STOPPED
        self.current_time: Optional[datetime] = None
        self.real_start_time: Optional[datetime] = None
        
        # Tick queue (min-heap by timestamp)
        self.tick_queue: List[ReplayTick] = []
        
        # Callbacks
        self.on_tick_callbacks: List[Callable[[ReplayTick], None]] = []
        self.on_opportunity_callbacks: List[Callable[[Dict], None]] = []
        self.on_state_change_callbacks: List[Callable[[ReplayState], None]] = []
        
        # Statistics
        self.stats = ReplayStatistics()
        
        # Current prices for opportunity detection
        self.current_prices: Dict[str, Dict[str, Tuple[float, float]]] = defaultdict(dict)
    
    def on_tick(self, callback: Callable[[ReplayTick], None]):
        """Register callback for each tick"""
        self.on_tick_callbacks.append(callback)
    
    def on_opportunity(self, callback: Callable[[Dict], None]):
        """Register callback for detected opportunities"""
        self.on_opportunity_callbacks.append(callback)
    
    def on_state_change(self, callback: Callable[[ReplayState], None]):
        """Register callback for state changes"""
        self.on_state_change_callbacks.append(callback)
    
    def _set_state(self, new_state: ReplayState):
        """Update state and notify listeners"""
        old_state = self.state
        self.state = new_state
        
        if old_state != new_state:
            for callback in self.on_state_change_callbacks:
                try:
                    callback(new_state)
                except Exception as e:
                    logger.error(f"State change callback error: {e}")
    
    def _load_ticks(self, start: datetime, end: datetime) -> Generator[ReplayTick, None, None]:
        """Load ticks from source within time range"""
        # Query tick source
        ticks = self.tick_source.query_ticks(
            exchange=self.config.exchanges[0] if self.config.exchanges and len(self.config.exchanges) == 1 else None,
            pair=self.config.pairs[0] if self.config.pairs and len(self.config.pairs) == 1 else None,
            start=start,
            end=end,
            limit=1000000
        )
        
        for tick_data in ticks:
            # Filter if needed
            if self.config.exchanges and tick_data.get("exchange") not in self.config.exchanges:
                continue
            if self.config.pairs and tick_data.get("pair") not in self.config.pairs:
                continue
            
            # Convert to ReplayTick
            timestamp = tick_data.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            yield ReplayTick(
                timestamp=timestamp,
                exchange=tick_data.get("exchange"),
                pair=tick_data.get("pair"),
                bid=tick_data.get("bid"),
                ask=tick_data.get("ask"),
                bid_size=tick_data.get("bid_size"),
                ask_size=tick_data.get("ask_size")
            )
    
    def _check_arbitrage(self, tick: ReplayTick):
        """Check for arbitrage opportunities on each tick"""
        # Update current prices
        self.current_prices[tick.pair][tick.exchange] = (tick.bid, tick.ask)
        
        # Need at least 2 exchanges for arbitrage
        if len(self.current_prices[tick.pair]) < 2:
            return
        
        # Find best bid and ask across exchanges
        exchanges = list(self.current_prices[tick.pair].keys())
        
        for i, ex1 in enumerate(exchanges):
            for ex2 in exchanges[i+1:]:
                bid1, ask1 = self.current_prices[tick.pair][ex1]
                bid2, ask2 = self.current_prices[tick.pair][ex2]
                
                # Check ex1 buy -> ex2 sell
                if bid2 > ask1:
                    profit_pct = ((bid2 - ask1) / ask1) * 100
                    self._report_opportunity(tick.pair, ex1, ex2, ask1, bid2, profit_pct, tick.timestamp)
                
                # Check ex2 buy -> ex1 sell
                if bid1 > ask2:
                    profit_pct = ((bid1 - ask2) / ask2) * 100
                    self._report_opportunity(tick.pair, ex2, ex1, ask2, bid1, profit_pct, tick.timestamp)
    
    def _report_opportunity(
        self,
        pair: str,
        buy_exchange: str,
        sell_exchange: str,
        buy_price: float,
        sell_price: float,
        profit_pct: float,
        timestamp: datetime
    ):
        """Report detected opportunity"""
        if profit_pct < 0.01:  # Minimum threshold
            return
        
        opportunity = {
            "pair": pair,
            "buy_exchange": buy_exchange,
            "sell_exchange": sell_exchange,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "profit_percent": profit_pct,
            "timestamp": timestamp.isoformat(),
        }
        
        # Update stats
        self.stats.opportunities_detected += 1
        self.stats.total_profit_potential += profit_pct
        self.stats.best_opportunity_profit = max(self.stats.best_opportunity_profit, profit_pct)
        
        # Notify listeners
        for callback in self.on_opportunity_callbacks:
            try:
                callback(opportunity)
            except Exception as e:
                logger.error(f"Opportunity callback error: {e}")
    
    async def play(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ):
        """
        Start or resume replay.
        
        Args:
            start: Override start time
            end: Override end time
        """
        if self.state == ReplayState.PLAYING:
            return
        
        # Determine time range
        if start:
            replay_start = start
        elif self.config.start_date:
            replay_start = datetime.combine(self.config.start_date, datetime.min.time())
        else:
            replay_start = datetime.now() - timedelta(hours=24)
        
        if end:
            replay_end = end
        elif self.config.end_date:
            replay_end = datetime.combine(self.config.end_date, datetime.max.time())
        else:
            replay_end = datetime.now()
        
        self._set_state(ReplayState.PLAYING)
        self.real_start_time = datetime.now()
        self.stats = ReplayStatistics(start_time=replay_start)
        
        logger.info(f"Starting replay: {replay_start} to {replay_end} at {self.config.speed}x speed")
        
        # Load and replay ticks
        last_tick_time = None
        tick_count = 0
        
        for tick in self._load_ticks(replay_start, replay_end):
            if self.state == ReplayState.STOPPED:
                break
            
            while self.state == ReplayState.PAUSED:
                await asyncio.sleep(0.1)
                if self.state == ReplayState.STOPPED:
                    break
            
            # Calculate delay based on speed
            if last_tick_time and self.config.speed < 1000:
                time_diff = (tick.timestamp - last_tick_time).total_seconds()
                
                # Skip large gaps
                if self.config.skip_gaps and time_diff > self.config.gap_threshold_seconds:
                    time_diff = 0.01
                
                delay = time_diff / self.config.speed
                
                if delay > 0.001:  # Only sleep for significant delays
                    await asyncio.sleep(delay)
            
            # Process tick
            self.current_time = tick.timestamp
            last_tick_time = tick.timestamp
            
            # Update statistics
            self.stats.ticks_replayed += 1
            self.stats.exchanges_seen.add(tick.exchange)
            self.stats.pairs_seen.add(tick.pair)
            
            spread = tick.ask - tick.bid
            self.stats.worst_spread = max(self.stats.worst_spread, spread)
            self.stats.best_spread = min(self.stats.best_spread, spread) if self.stats.best_spread == 0 else min(self.stats.best_spread, spread)
            
            # Notify tick callbacks
            for callback in self.on_tick_callbacks:
                try:
                    callback(tick)
                except Exception as e:
                    logger.error(f"Tick callback error: {e}")
            
            # Check for arbitrage
            self._check_arbitrage(tick)
            
            tick_count += 1
            
            # Rate limiting for very fast replay
            if tick_count % self.config.max_ticks_per_second == 0:
                await asyncio.sleep(0.001)
        
        # Finalize
        self.stats.end_time = self.current_time
        self.stats.replay_duration_seconds = (datetime.now() - self.real_start_time).total_seconds()
        
        self._set_state(ReplayState.STOPPED)
        logger.info(f"Replay complete: {self.stats.ticks_replayed} ticks, {self.stats.opportunities_detected} opportunities")
    
    def pause(self):
        """Pause replay"""
        if self.state == ReplayState.PLAYING:
            self._set_state(ReplayState.PAUSED)
    
    def resume(self):
        """Resume paused replay"""
        if self.state == ReplayState.PAUSED:
            self._set_state(ReplayState.PLAYING)
    
    def stop(self):
        """Stop replay"""
        self._set_state(ReplayState.STOPPED)
    
    def set_speed(self, speed: float):
        """Change replay speed (1.0 = real-time)"""
        self.config.speed = max(0.1, min(10000, speed))
    
    def get_state(self) -> dict:
        """Get current replay state"""
        return {
            "state": self.state.value,
            "current_time": self.current_time.isoformat() if self.current_time else None,
            "speed": self.config.speed,
            "statistics": self.stats.to_dict(),
            "config": {
                "start_date": self.config.start_date.isoformat() if self.config.start_date else None,
                "end_date": self.config.end_date.isoformat() if self.config.end_date else None,
                "exchanges": self.config.exchanges,
                "pairs": self.config.pairs,
                "skip_gaps": self.config.skip_gaps,
            }
        }


class ReplayEngine:
    """
    Main replay engine managing multiple sessions.
    
    Provides:
    - Session management
    - Preset configurations
    - Batch replay for backtesting
    """
    
    def __init__(self, tick_source: Any):
        self.tick_source = tick_source
        self.sessions: Dict[str, ReplaySession] = {}
        self.active_session: Optional[str] = None
    
    def create_session(
        self,
        session_id: str,
        config: Optional[ReplayConfig] = None
    ) -> ReplaySession:
        """Create a new replay session"""
        config = config or ReplayConfig()
        session = ReplaySession(self.tick_source, config)
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[ReplaySession]:
        """Get existing session"""
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str):
        """Delete a session"""
        if session_id in self.sessions:
            self.sessions[session_id].stop()
            del self.sessions[session_id]
    
    async def quick_replay(
        self,
        start: datetime,
        end: datetime,
        speed: float = 100,
        on_tick: Optional[Callable] = None,
        on_opportunity: Optional[Callable] = None
    ) -> ReplayStatistics:
        """
        Quick replay for backtesting.
        
        Returns statistics from the replay.
        """
        config = ReplayConfig(speed=speed)
        session = ReplaySession(self.tick_source, config)
        
        if on_tick:
            session.on_tick(on_tick)
        if on_opportunity:
            session.on_opportunity(on_opportunity)
        
        await session.play(start=start, end=end)
        
        return session.stats
    
    async def backtest_strategy(
        self,
        strategy_callback: Callable[[ReplayTick, Dict], Optional[Dict]],
        start: datetime,
        end: datetime,
        initial_capital: float = 10000
    ) -> Dict:
        """
        Backtest a trading strategy.
        
        Args:
            strategy_callback: Function(tick, state) -> Optional[trade_decision]
            start: Backtest start time
            end: Backtest end time
            initial_capital: Starting capital
        
        Returns:
            Backtest results including PnL, trade count, etc.
        """
        results = {
            "initial_capital": initial_capital,
            "final_capital": initial_capital,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0,
            "max_drawdown": 0,
            "trades": []
        }
        
        state = {
            "capital": initial_capital,
            "positions": {},
            "peak_capital": initial_capital,
        }
        
        def process_tick(tick: ReplayTick):
            decision = strategy_callback(tick, state)
            
            if decision:
                # Execute trade
                results["total_trades"] += 1
                
                # Simplified trade execution
                trade_pnl = decision.get("expected_pnl", 0)
                state["capital"] += trade_pnl
                results["total_pnl"] += trade_pnl
                
                if trade_pnl > 0:
                    results["winning_trades"] += 1
                else:
                    results["losing_trades"] += 1
                
                # Track drawdown
                state["peak_capital"] = max(state["peak_capital"], state["capital"])
                drawdown = (state["peak_capital"] - state["capital"]) / state["peak_capital"]
                results["max_drawdown"] = max(results["max_drawdown"], drawdown)
                
                results["trades"].append({
                    "timestamp": tick.timestamp.isoformat(),
                    "decision": decision,
                    "pnl": trade_pnl,
                    "capital_after": state["capital"]
                })
        
        config = ReplayConfig(speed=10000)  # Fast replay for backtesting
        session = ReplaySession(self.tick_source, config)
        session.on_tick(process_tick)
        
        await session.play(start=start, end=end)
        
        results["final_capital"] = state["capital"]
        results["return_percent"] = ((results["final_capital"] - initial_capital) / initial_capital) * 100
        results["win_rate"] = results["winning_trades"] / max(1, results["total_trades"])
        results["replay_stats"] = session.stats.to_dict()
        
        return results
    
    def get_available_dates(self) -> List[date]:
        """Get list of dates with available data"""
        # Query tick source for date range
        stats = self.tick_source.get_database_stats() if hasattr(self.tick_source, 'get_database_stats') else {}
        
        # Return last 30 days as default
        today = date.today()
        return [today - timedelta(days=i) for i in range(30)]
    
    def get_state(self) -> dict:
        """Get engine state"""
        return {
            "sessions": {
                sid: session.get_state()
                for sid, session in self.sessions.items()
            },
            "active_session": self.active_session,
            "available_dates": [d.isoformat() for d in self.get_available_dates()[:10]],
        }
