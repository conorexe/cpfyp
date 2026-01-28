"""
TimescaleDB Integration for Tick Storage

Provides high-performance time-series storage for:
- Billions of price ticks
- Real-time aggregations (OHLCV)
- Historical queries
- Compression and retention policies

TimescaleDB is a PostgreSQL extension optimized for time-series data.
If TimescaleDB is not available, falls back to in-memory storage.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any, Generator
from collections import deque
import json

logger = logging.getLogger(__name__)

# Try to import psycopg2 for PostgreSQL/TimescaleDB
try:
    import psycopg2
    from psycopg2.extras import execute_values, RealDictCursor
    from psycopg2.pool import ThreadedConnectionPool
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False
    logger.warning("psycopg2 not available, using in-memory storage")


@dataclass
class TickRecord:
    """Single tick record for database storage"""
    timestamp: datetime
    exchange: str
    pair: str
    bid: float
    ask: float
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    
    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid
    
    def to_tuple(self) -> tuple:
        return (
            self.timestamp,
            self.exchange,
            self.pair,
            self.bid,
            self.ask,
            self.bid_size,
            self.ask_size
        )
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "exchange": self.exchange,
            "pair": self.pair,
            "bid": self.bid,
            "ask": self.ask,
            "mid": self.mid,
            "spread": self.spread,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
        }


class TimescaleDBStorage:
    """
    TimescaleDB storage engine for tick data.
    
    Schema:
    - ticks: Main hypertable for tick data
    - ticks_1m: Continuous aggregate for 1-minute OHLCV
    - ticks_1h: Continuous aggregate for 1-hour OHLCV
    
    Features:
    - Automatic chunk management
    - Compression for old data
    - Continuous aggregates for fast queries
    - Retention policies
    """
    
    CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS timescaledb;"
    
    CREATE_TICKS_TABLE = """
    CREATE TABLE IF NOT EXISTS ticks (
        time        TIMESTAMPTZ NOT NULL,
        exchange    TEXT NOT NULL,
        pair        TEXT NOT NULL,
        bid         DOUBLE PRECISION NOT NULL,
        ask         DOUBLE PRECISION NOT NULL,
        bid_size    DOUBLE PRECISION,
        ask_size    DOUBLE PRECISION
    );
    """
    
    CREATE_HYPERTABLE = """
    SELECT create_hypertable('ticks', 'time', 
        if_not_exists => TRUE,
        chunk_time_interval => INTERVAL '1 hour'
    );
    """
    
    CREATE_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_ticks_exchange_pair_time 
    ON ticks (exchange, pair, time DESC);
    """
    
    CREATE_CONTINUOUS_AGGREGATE_1M = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS ticks_1m
    WITH (timescaledb.continuous) AS
    SELECT 
        time_bucket('1 minute', time) AS bucket,
        exchange,
        pair,
        FIRST(bid, time) AS open_bid,
        MAX(bid) AS high_bid,
        MIN(bid) AS low_bid,
        LAST(bid, time) AS close_bid,
        FIRST(ask, time) AS open_ask,
        MAX(ask) AS high_ask,
        MIN(ask) AS low_ask,
        LAST(ask, time) AS close_ask,
        AVG((bid + ask) / 2) AS vwap,
        COUNT(*) AS tick_count
    FROM ticks
    GROUP BY bucket, exchange, pair;
    """
    
    ENABLE_COMPRESSION = """
    ALTER TABLE ticks SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'exchange, pair',
        timescaledb.compress_orderby = 'time DESC'
    );
    """
    
    ADD_COMPRESSION_POLICY = """
    SELECT add_compression_policy('ticks', INTERVAL '7 days', if_not_exists => true);
    """
    
    ADD_RETENTION_POLICY = """
    SELECT add_retention_policy('ticks', INTERVAL '30 days', if_not_exists => true);
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "arbitrage",
        user: str = "postgres",
        password: str = "",
        min_connections: int = 1,
        max_connections: int = 10,
        enable_compression: bool = True,
        retention_days: int = 30
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.enable_compression = enable_compression
        self.retention_days = retention_days
        
        self.pool: Optional[Any] = None
        self.connected = False
        
        # Write buffer for batch inserts
        self.write_buffer: List[TickRecord] = []
        self.buffer_size = 1000
        
        # Statistics
        self.ticks_written = 0
        self.ticks_buffered = 0
        self.last_flush = datetime.now()
        
        if HAS_PSYCOPG2:
            try:
                self._connect(min_connections, max_connections)
                self._initialize_schema()
            except Exception as e:
                logger.warning(f"Failed to connect to TimescaleDB: {e}")
                self.connected = False
    
    def _connect(self, min_conn: int, max_conn: int):
        """Establish connection pool to TimescaleDB"""
        self.pool = ThreadedConnectionPool(
            minconn=min_conn,
            maxconn=max_conn,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password
        )
        self.connected = True
        logger.info(f"Connected to TimescaleDB at {self.host}:{self.port}/{self.database}")
    
    def _initialize_schema(self):
        """Create tables and hypertables if they don't exist"""
        if not self.connected:
            return
        
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                # Create extension
                cur.execute(self.CREATE_EXTENSION)
                
                # Create table
                cur.execute(self.CREATE_TICKS_TABLE)
                
                # Convert to hypertable
                try:
                    cur.execute(self.CREATE_HYPERTABLE)
                except psycopg2.errors.DuplicateTable:
                    pass  # Already a hypertable
                
                # Create index
                cur.execute(self.CREATE_INDEX)
                
                # Create continuous aggregate
                try:
                    cur.execute(self.CREATE_CONTINUOUS_AGGREGATE_1M)
                except Exception as e:
                    logger.debug(f"Continuous aggregate may already exist: {e}")
                
                # Enable compression
                if self.enable_compression:
                    try:
                        cur.execute(self.ENABLE_COMPRESSION)
                        cur.execute(self.ADD_COMPRESSION_POLICY)
                    except Exception as e:
                        logger.debug(f"Compression policy may already exist: {e}")
                
                # Add retention policy
                try:
                    cur.execute(f"""
                        SELECT add_retention_policy('ticks', 
                            INTERVAL '{self.retention_days} days', 
                            if_not_exists => true
                        );
                    """)
                except Exception as e:
                    logger.debug(f"Retention policy may already exist: {e}")
                
                conn.commit()
                logger.info("TimescaleDB schema initialized")
        except Exception as e:
            logger.error(f"Failed to initialize schema: {e}")
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    def store(
        self,
        exchange: str,
        pair: str,
        bid: float,
        ask: float,
        timestamp: Optional[datetime] = None,
        bid_size: Optional[float] = None,
        ask_size: Optional[float] = None
    ):
        """Store a single tick (buffered for batch insert)"""
        timestamp = timestamp or datetime.now()
        
        tick = TickRecord(
            timestamp=timestamp,
            exchange=exchange,
            pair=pair,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size
        )
        
        self.write_buffer.append(tick)
        self.ticks_buffered += 1
        
        # Flush buffer when full
        if len(self.write_buffer) >= self.buffer_size:
            self.flush()
    
    def flush(self):
        """Flush write buffer to database"""
        if not self.write_buffer:
            return
        
        if not self.connected:
            # Discard buffer if not connected
            self.write_buffer.clear()
            return
        
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                values = [tick.to_tuple() for tick in self.write_buffer]
                
                execute_values(
                    cur,
                    """
                    INSERT INTO ticks (time, exchange, pair, bid, ask, bid_size, ask_size)
                    VALUES %s
                    """,
                    values,
                    page_size=1000
                )
                
                conn.commit()
                self.ticks_written += len(self.write_buffer)
                self.write_buffer.clear()
                self.last_flush = datetime.now()
                
        except Exception as e:
            logger.error(f"Failed to flush ticks: {e}")
            conn.rollback()
        finally:
            self.pool.putconn(conn)
    
    def query_ticks(
        self,
        exchange: Optional[str] = None,
        pair: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Dict]:
        """Query tick data with optional filters"""
        if not self.connected:
            return []
        
        conditions = []
        params = []
        
        if exchange:
            conditions.append("exchange = %s")
            params.append(exchange)
        
        if pair:
            conditions.append("pair = %s")
            params.append(pair)
        
        if start:
            conditions.append("time >= %s")
            params.append(start)
        
        if end:
            conditions.append("time <= %s")
            params.append(end)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)
        
        query = f"""
            SELECT time, exchange, pair, bid, ask, bid_size, ask_size
            FROM ticks
            WHERE {where_clause}
            ORDER BY time DESC
            LIMIT %s
        """
        
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return []
        finally:
            self.pool.putconn(conn)
    
    def query_ohlcv(
        self,
        exchange: str,
        pair: str,
        start: datetime,
        end: datetime,
        interval: str = "1 minute"
    ) -> List[Dict]:
        """Query aggregated OHLCV data"""
        if not self.connected:
            return []
        
        query = """
            SELECT 
                time_bucket(%s, time) AS bucket,
                FIRST(bid, time) AS open,
                MAX((bid + ask) / 2) AS high,
                MIN((bid + ask) / 2) AS low,
                LAST(ask, time) AS close,
                COUNT(*) AS volume
            FROM ticks
            WHERE exchange = %s AND pair = %s
              AND time >= %s AND time <= %s
            GROUP BY bucket
            ORDER BY bucket
        """
        
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (interval, exchange, pair, start, end))
                results = cur.fetchall()
                return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"OHLCV query failed: {e}")
            return []
        finally:
            self.pool.putconn(conn)
    
    def query_spread_stats(
        self,
        exchange: str,
        pair: str,
        hours: int = 24
    ) -> Dict:
        """Get spread statistics for a pair"""
        if not self.connected:
            return {}
        
        query = """
            SELECT 
                AVG(ask - bid) AS avg_spread,
                MIN(ask - bid) AS min_spread,
                MAX(ask - bid) AS max_spread,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ask - bid) AS median_spread,
                COUNT(*) AS tick_count,
                AVG((bid + ask) / 2) AS avg_price
            FROM ticks
            WHERE exchange = %s AND pair = %s
              AND time >= NOW() - INTERVAL '%s hours'
        """
        
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (exchange, pair, hours))
                result = cur.fetchone()
                return dict(result) if result else {}
        except Exception as e:
            logger.error(f"Spread stats query failed: {e}")
            return {}
        finally:
            self.pool.putconn(conn)
    
    def query_cross_exchange_spread(
        self,
        pair: str,
        window_minutes: int = 5
    ) -> List[Dict]:
        """Get cross-exchange spread opportunities from recent data"""
        if not self.connected:
            return []
        
        query = """
            WITH latest_prices AS (
                SELECT DISTINCT ON (exchange)
                    exchange,
                    bid,
                    ask,
                    time
                FROM ticks
                WHERE pair = %s
                  AND time >= NOW() - INTERVAL '%s minutes'
                ORDER BY exchange, time DESC
            )
            SELECT 
                a.exchange AS buy_exchange,
                b.exchange AS sell_exchange,
                a.ask AS buy_price,
                b.bid AS sell_price,
                ((b.bid - a.ask) / a.ask * 100) AS profit_percent
            FROM latest_prices a
            CROSS JOIN latest_prices b
            WHERE a.exchange != b.exchange
              AND b.bid > a.ask
            ORDER BY profit_percent DESC
        """
        
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (pair, window_minutes))
                results = cur.fetchall()
                return [dict(r) for r in results]
        except Exception as e:
            logger.error(f"Cross-exchange query failed: {e}")
            return []
        finally:
            self.pool.putconn(conn)
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        if not self.connected:
            return {"connected": False}
        
        stats = {
            "connected": True,
            "ticks_written": self.ticks_written,
            "ticks_buffered": len(self.write_buffer),
            "last_flush": self.last_flush.isoformat(),
        }
        
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Total rows
                cur.execute("SELECT COUNT(*) AS total FROM ticks")
                stats["total_ticks"] = cur.fetchone()["total"]
                
                # Chunks info
                cur.execute("""
                    SELECT 
                        COUNT(*) AS num_chunks,
                        SUM(total_bytes) AS total_bytes
                    FROM timescaledb_information.chunks
                    WHERE hypertable_name = 'ticks'
                """)
                chunk_info = cur.fetchone()
                stats["num_chunks"] = chunk_info["num_chunks"] if chunk_info else 0
                stats["total_bytes"] = chunk_info["total_bytes"] if chunk_info else 0
                
                # Compression stats
                cur.execute("""
                    SELECT 
                        COUNT(*) FILTER (WHERE is_compressed) AS compressed_chunks,
                        COUNT(*) AS total_chunks
                    FROM timescaledb_information.chunks
                    WHERE hypertable_name = 'ticks'
                """)
                comp_info = cur.fetchone()
                stats["compressed_chunks"] = comp_info["compressed_chunks"] if comp_info else 0
                
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
        finally:
            self.pool.putconn(conn)
        
        return stats
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "storage_type": "timescaledb" if self.connected else "memory",
            "database_stats": self.get_database_stats(),
            "buffer_size": len(self.write_buffer),
            "buffer_max": self.buffer_size,
            "retention_days": self.retention_days,
            "compression_enabled": self.enable_compression,
        }
    
    def close(self):
        """Close database connections"""
        if self.write_buffer:
            self.flush()
        if self.pool:
            self.pool.closeall()
            self.connected = False


class InMemoryFallback:
    """
    In-memory fallback when TimescaleDB is not available.
    Uses efficient deque-based storage with automatic cleanup.
    """
    
    def __init__(self, max_ticks_per_key: int = 100000, retention_hours: int = 24):
        self.max_ticks = max_ticks_per_key
        self.retention = timedelta(hours=retention_hours)
        
        # Storage: (exchange, pair) -> deque of TickRecord
        self.ticks: Dict[Tuple[str, str], deque] = {}
        
        self.ticks_stored = 0
        self.start_time: Optional[datetime] = None
    
    def store(
        self,
        exchange: str,
        pair: str,
        bid: float,
        ask: float,
        timestamp: Optional[datetime] = None,
        bid_size: Optional[float] = None,
        ask_size: Optional[float] = None
    ):
        timestamp = timestamp or datetime.now()
        
        if self.start_time is None:
            self.start_time = timestamp
        
        tick = TickRecord(
            timestamp=timestamp,
            exchange=exchange,
            pair=pair,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size
        )
        
        key = (exchange, pair)
        if key not in self.ticks:
            self.ticks[key] = deque(maxlen=self.max_ticks)
        
        self.ticks[key].append(tick)
        self.ticks_stored += 1
    
    def flush(self):
        """No-op for in-memory storage"""
        pass
    
    def query_ticks(
        self,
        exchange: Optional[str] = None,
        pair: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[Dict]:
        result = []
        
        for (ex, p), ticks in self.ticks.items():
            if exchange and ex != exchange:
                continue
            if pair and p != pair:
                continue
            
            for tick in ticks:
                if start and tick.timestamp < start:
                    continue
                if end and tick.timestamp > end:
                    continue
                result.append(tick.to_dict())
                if len(result) >= limit:
                    return result
        
        return result
    
    def get_database_stats(self) -> Dict:
        total_ticks = sum(len(ticks) for ticks in self.ticks.values())
        
        return {
            "connected": False,
            "storage_type": "in_memory",
            "total_ticks": total_ticks,
            "unique_keys": len(self.ticks),
            "ticks_stored": self.ticks_stored,
        }
    
    def get_state(self) -> dict:
        return {
            "storage_type": "memory",
            "database_stats": self.get_database_stats(),
            "max_ticks_per_key": self.max_ticks,
            "retention_hours": self.retention.total_seconds() / 3600,
        }


def create_tick_storage(
    use_timescale: bool = True,
    **timescale_kwargs
) -> Any:
    """
    Factory function to create appropriate tick storage.
    
    Returns TimescaleDBStorage if available, otherwise InMemoryFallback.
    """
    if use_timescale and HAS_PSYCOPG2:
        try:
            storage = TimescaleDBStorage(**timescale_kwargs)
            if storage.connected:
                return storage
        except Exception as e:
            logger.warning(f"Failed to create TimescaleDB storage: {e}")
    
    logger.info("Using in-memory tick storage")
    return InMemoryFallback()
