-- =============================================================================
-- MarketScout - Database Initialization Script
-- =============================================================================
-- This script runs automatically when the PostgreSQL container starts
-- It creates the TimescaleDB extension and all required tables
-- =============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================================================
-- Core Tables
-- =============================================================================

-- Users table (for authentication)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Create index on username for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- =============================================================================
-- Price Data Tables
-- =============================================================================

-- Tick data (main time-series table)
CREATE TABLE IF NOT EXISTS ticks (
    time        TIMESTAMPTZ NOT NULL,
    exchange    TEXT NOT NULL,
    pair        TEXT NOT NULL,
    bid         DOUBLE PRECISION NOT NULL,
    ask         DOUBLE PRECISION NOT NULL,
    bid_size    DOUBLE PRECISION,
    ask_size    DOUBLE PRECISION
);

-- Convert to hypertable for efficient time-series queries
SELECT create_hypertable('ticks', 'time', 
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 hour'
);

-- Create index for common query patterns
CREATE INDEX IF NOT EXISTS idx_ticks_exchange_pair_time 
ON ticks (exchange, pair, time DESC);

-- =============================================================================
-- Arbitrage Opportunities Tables
-- =============================================================================

-- Simple cross-exchange opportunities
CREATE TABLE IF NOT EXISTS opportunities (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    pair TEXT NOT NULL,
    buy_exchange TEXT NOT NULL,
    sell_exchange TEXT NOT NULL,
    buy_price DOUBLE PRECISION NOT NULL,
    sell_price DOUBLE PRECISION NOT NULL,
    profit_percent DOUBLE PRECISION NOT NULL,
    status VARCHAR(20) DEFAULT 'detected', -- detected, simulated, executed
    simulated_profit DOUBLE PRECISION,
    execution_notes TEXT
);

SELECT create_hypertable('opportunities', 'time', 
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_opportunities_pair_time 
ON opportunities (pair, time DESC);

-- Triangular arbitrage opportunities
CREATE TABLE IF NOT EXISTS triangular_opportunities (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    exchange TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    path TEXT NOT NULL, -- JSON array of pairs
    profit_percent DOUBLE PRECISION NOT NULL,
    start_amount DOUBLE PRECISION,
    end_amount DOUBLE PRECISION,
    status VARCHAR(20) DEFAULT 'detected'
);

SELECT create_hypertable('triangular_opportunities', 'time', 
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

-- =============================================================================
-- Portfolio Management Tables
-- =============================================================================

-- User portfolios
CREATE TABLE IF NOT EXISTS portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    initial_balance DOUBLE PRECISION DEFAULT 10000,
    current_balance DOUBLE PRECISION DEFAULT 10000,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios(user_id);

-- Portfolio positions (simulated holdings)
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    asset VARCHAR(20) NOT NULL, -- e.g., 'BTC', 'ETH', 'USDT'
    quantity DOUBLE PRECISION NOT NULL,
    avg_entry_price DOUBLE PRECISION,
    current_price DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_portfolio ON positions(portfolio_id);

-- Trade history (paper trades)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE,
    opportunity_id INTEGER,
    pair TEXT NOT NULL,
    side VARCHAR(10) NOT NULL, -- 'buy' or 'sell'
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION DEFAULT 0,
    exchange TEXT NOT NULL,
    trade_type VARCHAR(20) NOT NULL, -- 'arbitrage', 'triangular', 'manual'
    notes TEXT
);

SELECT create_hypertable('trades', 'time', 
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_trades_portfolio ON trades(portfolio_id, time DESC);

-- =============================================================================
-- Continuous Aggregates (Materialized Views)
-- =============================================================================

-- 1-minute OHLCV aggregation
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
GROUP BY bucket, exchange, pair
WITH NO DATA;

-- 1-hour OHLCV aggregation
CREATE MATERIALIZED VIEW IF NOT EXISTS ticks_1h
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 hour', time) AS bucket,
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
GROUP BY bucket, exchange, pair
WITH NO DATA;

-- Opportunity statistics per day
CREATE MATERIALIZED VIEW IF NOT EXISTS opportunity_stats_daily
WITH (timescaledb.continuous) AS
SELECT 
    time_bucket('1 day', time) AS bucket,
    pair,
    buy_exchange,
    sell_exchange,
    COUNT(*) AS opportunity_count,
    AVG(profit_percent) AS avg_profit,
    MAX(profit_percent) AS max_profit,
    MIN(profit_percent) AS min_profit
FROM opportunities
GROUP BY bucket, pair, buy_exchange, sell_exchange
WITH NO DATA;

-- =============================================================================
-- Compression and Retention Policies
-- =============================================================================

-- Enable compression on ticks table
ALTER TABLE ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'exchange, pair',
    timescaledb.compress_orderby = 'time DESC'
);

-- Compress data older than 7 days
SELECT add_compression_policy('ticks', INTERVAL '7 days', if_not_exists => true);

-- Delete data older than 30 days (configurable)
SELECT add_retention_policy('ticks', INTERVAL '30 days', if_not_exists => true);

-- Compress opportunities older than 30 days
ALTER TABLE opportunities SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'pair',
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('opportunities', INTERVAL '30 days', if_not_exists => true);

-- =============================================================================
-- Refresh Policies for Continuous Aggregates
-- =============================================================================

SELECT add_continuous_aggregate_policy('ticks_1m',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => true
);

SELECT add_continuous_aggregate_policy('ticks_1h',
    start_offset => INTERVAL '1 day',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => true
);

SELECT add_continuous_aggregate_policy('opportunity_stats_daily',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => true
);

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to calculate portfolio value
CREATE OR REPLACE FUNCTION calculate_portfolio_value(p_portfolio_id INTEGER)
RETURNS DOUBLE PRECISION AS $$
DECLARE
    total_value DOUBLE PRECISION := 0;
BEGIN
    SELECT COALESCE(SUM(quantity * COALESCE(current_price, avg_entry_price)), 0)
    INTO total_value
    FROM positions
    WHERE portfolio_id = p_portfolio_id;
    
    RETURN total_value;
END;
$$ LANGUAGE plpgsql;

-- Function to get cross-exchange spread opportunities
CREATE OR REPLACE FUNCTION get_cross_exchange_spreads(
    p_pair TEXT,
    p_window_minutes INTEGER DEFAULT 5
)
RETURNS TABLE (
    buy_exchange TEXT,
    sell_exchange TEXT,
    buy_price DOUBLE PRECISION,
    sell_price DOUBLE PRECISION,
    profit_percent DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    WITH latest_prices AS (
        SELECT DISTINCT ON (exchange)
            exchange,
            bid,
            ask,
            time
        FROM ticks
        WHERE pair = p_pair
          AND time >= NOW() - (p_window_minutes || ' minutes')::INTERVAL
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
    ORDER BY profit_percent DESC;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Initial Data
-- =============================================================================

-- Create default admin user (password: changeme123)
-- Password hash is bcrypt of 'changeme123'
INSERT INTO users (username, email, password_hash, is_admin) 
VALUES (
    'admin', 
    'admin@marketscout.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.VTtYL0f1ZPvKGi',
    TRUE
) ON CONFLICT (username) DO NOTHING;

-- Create default portfolio for admin
INSERT INTO portfolios (user_id, name, description, initial_balance, is_default)
SELECT id, 'Default Portfolio', 'Primary paper trading portfolio', 10000, TRUE
FROM users WHERE username = 'admin'
ON CONFLICT DO NOTHING;

-- Initialize default portfolio with USDT
INSERT INTO positions (portfolio_id, asset, quantity, avg_entry_price, current_price)
SELECT p.id, 'USDT', 10000, 1.0, 1.0
FROM portfolios p
JOIN users u ON p.user_id = u.id
WHERE u.username = 'admin' AND p.is_default = TRUE
ON CONFLICT DO NOTHING;

-- =============================================================================
-- Grants (for application user if different from postgres)
-- =============================================================================

-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_user;

COMMIT;
