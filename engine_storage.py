"""
Tick-by-Tick Price Storage Engine

Stores every price update for:
- Historical replay
- Backtesting strategies  
- ML model training
- Analytics and reporting

Uses efficient in-memory storage with optional persistence.
In production, would use TimescaleDB or ClickHouse.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Iterator
from collections import deque
import json
import gzip

logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Single price tick"""
    timestamp: datetime
    exchange: str
    pair: str
    bid: float
    ask: float
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "pair": self.pair,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread": self.spread,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Tick':
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            exchange=data["exchange"],
            pair=data["pair"],
            bid=data["bid"],
            ask=data["ask"],
        )


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume candle"""
    timestamp: datetime
    exchange: str
    pair: str
    open: float
    high: float
    low: float
    close: float
    volume: int  # Number of ticks
    vwap: float  # Volume-weighted average price
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "pair": self.pair,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": round(self.vwap, 8),
        }


class TickStorage:
    """
    In-memory tick storage with aggregation.
    
    Features:
    - Store millions of ticks efficiently
    - Aggregate to OHLCV candles
    - Query by time range
    - Export/import functionality
    
    In production, replace with TimescaleDB:
    ```sql
    CREATE TABLE ticks (
        time        TIMESTAMPTZ NOT NULL,
        exchange    TEXT NOT NULL,
        pair        TEXT NOT NULL,
        bid         DOUBLE PRECISION,
        ask         DOUBLE PRECISION
    );
    SELECT create_hypertable('ticks', 'time');
    ```
    """
    
    def __init__(self, max_ticks_per_key: int = 100000, retention_hours: int = 24):
        """
        Args:
            max_ticks_per_key: Max ticks to keep per exchange/pair combo
            retention_hours: Hours of data to retain
        """
        self.max_ticks = max_ticks_per_key
        self.retention = timedelta(hours=retention_hours)
        
        # Tick storage: (exchange, pair) -> deque of Ticks
        self.ticks: Dict[Tuple[str, str], deque] = {}
        
        # Statistics
        self.total_ticks_stored = 0
        self.total_ticks_received = 0
        self.start_time: Optional[datetime] = None
    
    def store(self, exchange: str, pair: str, bid: float, ask: float, timestamp: Optional[datetime] = None):
        """Store a tick"""
        timestamp = timestamp or datetime.now()
        
        if self.start_time is None:
            self.start_time = timestamp
        
        tick = Tick(
            timestamp=timestamp,
            exchange=exchange,
            pair=pair,
            bid=bid,
            ask=ask
        )
        
        key = (exchange, pair)
        if key not in self.ticks:
            self.ticks[key] = deque(maxlen=self.max_ticks)
        
        self.ticks[key].append(tick)
        self.total_ticks_stored += 1
        self.total_ticks_received += 1
    
    def get_ticks(
        self, 
        exchange: str, 
        pair: str, 
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Tick]:
        """Get ticks for an exchange/pair within time range"""
        key = (exchange, pair)
        if key not in self.ticks:
            return []
        
        result = []
        for tick in self.ticks[key]:
            if start and tick.timestamp < start:
                continue
            if end and tick.timestamp > end:
                continue
            result.append(tick)
            if len(result) >= limit:
                break
        
        return result
    
    def get_all_ticks(
        self,
        pair: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Tick]:
        """Get ticks across all exchanges for a pair"""
        result = []
        
        for (exchange, p), ticks in self.ticks.items():
            if pair and p != pair:
                continue
            
            for tick in ticks:
                if start and tick.timestamp < start:
                    continue
                if end and tick.timestamp > end:
                    continue
                result.append(tick)
        
        # Sort by timestamp and limit
        result.sort(key=lambda t: t.timestamp)
        return result[:limit]
    
    def aggregate_ohlcv(
        self, 
        exchange: str, 
        pair: str, 
        interval_seconds: int = 60,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> List[OHLCV]:
        """Aggregate ticks into OHLCV candles"""
        ticks = self.get_ticks(exchange, pair, start, end, limit=100000)
        
        if not ticks:
            return []
        
        candles = []
        current_candle_start = None
        current_ticks = []
        
        for tick in ticks:
            # Determine candle start time
            candle_start = datetime(
                tick.timestamp.year,
                tick.timestamp.month,
                tick.timestamp.day,
                tick.timestamp.hour,
                (tick.timestamp.minute // (interval_seconds // 60)) * (interval_seconds // 60),
                0
            )
            
            if current_candle_start is None:
                current_candle_start = candle_start
            
            if candle_start != current_candle_start:
                # Finalize previous candle
                if current_ticks:
                    candles.append(self._create_ohlcv(
                        exchange, pair, current_candle_start, current_ticks
                    ))
                current_candle_start = candle_start
                current_ticks = []
            
            current_ticks.append(tick)
        
        # Finalize last candle
        if current_ticks:
            candles.append(self._create_ohlcv(
                exchange, pair, current_candle_start, current_ticks
            ))
        
        return candles
    
    def _create_ohlcv(
        self, 
        exchange: str, 
        pair: str, 
        timestamp: datetime, 
        ticks: List[Tick]
    ) -> OHLCV:
        """Create OHLCV candle from ticks"""
        prices = [t.mid for t in ticks]
        
        return OHLCV(
            timestamp=timestamp,
            exchange=exchange,
            pair=pair,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=len(ticks),
            vwap=sum(prices) / len(prices)
        )
    
    def get_statistics(self) -> dict:
        """Get storage statistics"""
        stats = {
            "total_ticks_received": self.total_ticks_received,
            "total_ticks_stored": self.total_ticks_stored,
            "unique_keys": len(self.ticks),
            "ticks_per_key": {},
            "memory_estimate_mb": 0,
        }
        
        total_ticks = 0
        for (exchange, pair), ticks in self.ticks.items():
            count = len(ticks)
            stats["ticks_per_key"][f"{exchange}/{pair}"] = count
            total_ticks += count
        
        # Rough memory estimate (each tick ~200 bytes)
        stats["memory_estimate_mb"] = round(total_ticks * 200 / 1024 / 1024, 2)
        
        if self.start_time:
            duration = (datetime.now() - self.start_time).total_seconds()
            if duration > 0:
                stats["ticks_per_second"] = round(self.total_ticks_received / duration, 2)
                stats["duration_seconds"] = round(duration, 1)
        
        return stats
    
    def export_json(self, filepath: str, compressed: bool = True):
        """Export all ticks to JSON file"""
        data = {
            "exported_at": datetime.now().isoformat(),
            "statistics": self.get_statistics(),
            "ticks": {}
        }
        
        for (exchange, pair), ticks in self.ticks.items():
            key = f"{exchange}/{pair}"
            data["ticks"][key] = [t.to_dict() for t in ticks]
        
        if compressed:
            with gzip.open(filepath + ".gz", 'wt', encoding='utf-8') as f:
                json.dump(data, f)
        else:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        
        logger.info(f"Exported {self.total_ticks_stored} ticks to {filepath}")
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        stats = self.get_statistics()
        
        # Get recent ticks sample
        recent_ticks = []
        for (exchange, pair), ticks in self.ticks.items():
            if ticks:
                recent_ticks.append(ticks[-1].to_dict())
        
        return {
            "storage_statistics": stats,
            "recent_ticks": recent_ticks[:20],
            "available_pairs": list(set(pair for _, pair in self.ticks.keys())),
            "available_exchanges": list(set(ex for ex, _ in self.ticks.keys())),
        }


class ReplayEngine:
    """
    Replays historical tick data.
    
    Useful for:
    - Backtesting strategies
    - Debugging
    - Demo presentations
    """
    
    def __init__(self, storage: TickStorage):
        self.storage = storage
        self.is_playing = False
        self.playback_speed = 1.0
        self.current_position = 0
    
    def replay(
        self,
        pair: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        speed: float = 1.0,
        callback = None
    ) -> Iterator[Tick]:
        """
        Replay ticks for a pair.
        
        Args:
            pair: Trading pair to replay
            start: Start time
            end: End time  
            speed: Playback speed multiplier
            callback: Function to call for each tick
        
        Yields:
            Tick objects in chronological order
        """
        ticks = self.storage.get_all_ticks(pair, start, end, limit=100000)
        
        if not ticks:
            return
        
        self.is_playing = True
        self.playback_speed = speed
        
        import time
        
        last_time = None
        for i, tick in enumerate(ticks):
            if not self.is_playing:
                break
            
            self.current_position = i
            
            # Simulate real-time delay
            if last_time and speed < 100:
                delay = (tick.timestamp - last_time).total_seconds() / speed
                if delay > 0 and delay < 5:  # Cap at 5 seconds
                    time.sleep(delay)
            
            last_time = tick.timestamp
            
            if callback:
                callback(tick)
            
            yield tick
        
        self.is_playing = False
    
    def stop(self):
        """Stop replay"""
        self.is_playing = False
    
    def get_state(self) -> dict:
        return {
            "is_playing": self.is_playing,
            "playback_speed": self.playback_speed,
            "current_position": self.current_position,
        }
