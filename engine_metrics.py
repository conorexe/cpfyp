"""
Prometheus Metrics & Monitoring Engine

Provides comprehensive metrics for:
- Price feed health (latency, staleness, update rates)
- Arbitrage opportunity detection rates
- Execution performance
- System resource usage
- Trading statistics

Exposes metrics in Prometheus format for Grafana dashboards.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Callable
from collections import defaultdict, deque
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    from prometheus_client import (
        Counter, Gauge, Histogram, Summary, Info,
        generate_latest, CONTENT_TYPE_LATEST,
        CollectorRegistry, REGISTRY
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus_client not available, using internal metrics only")


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class InternalMetric:
    """Fallback metric when prometheus_client is not available"""
    name: str
    metric_type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    values: Dict[tuple, float] = field(default_factory=dict)
    
    def labels_key(self, **label_values) -> tuple:
        return tuple(label_values.get(l, '') for l in self.labels)
    
    def inc(self, amount: float = 1, **label_values):
        key = self.labels_key(**label_values)
        self.values[key] = self.values.get(key, 0) + amount
    
    def set(self, value: float, **label_values):
        key = self.labels_key(**label_values)
        self.values[key] = value
    
    def observe(self, value: float, **label_values):
        # For histograms, just track the latest value
        key = self.labels_key(**label_values)
        self.values[key] = value


class MetricsEngine:
    """
    Central metrics collection and export engine.
    
    Supports both Prometheus metrics and internal metrics collection.
    """
    
    def __init__(self, enable_prometheus: bool = True):
        self.enable_prometheus = enable_prometheus and HAS_PROMETHEUS
        
        # Internal metrics (always available)
        self._internal_metrics: Dict[str, InternalMetric] = {}
        
        # Time series data for internal dashboards
        self._time_series: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Prometheus metrics
        if self.enable_prometheus:
            self._setup_prometheus_metrics()
        
        # Feed health tracking
        self._feed_last_update: Dict[str, datetime] = {}
        self._feed_update_counts: Dict[str, int] = defaultdict(int)
        self._feed_latencies: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Start background update task
        self._running = True
        self._update_thread = threading.Thread(target=self._background_updates, daemon=True)
        self._update_thread.start()
    
    def _setup_prometheus_metrics(self):
        """Initialize Prometheus metrics"""
        
        # ===== PRICE FEED METRICS =====
        self.price_updates_total = Counter(
            'arb_price_updates_total',
            'Total price updates received',
            ['exchange', 'pair']
        )
        
        self.price_update_latency = Histogram(
            'arb_price_update_latency_seconds',
            'Latency of price updates',
            ['exchange'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )
        
        self.feed_staleness = Gauge(
            'arb_feed_staleness_seconds',
            'Time since last update from exchange',
            ['exchange', 'pair']
        )
        
        self.feed_health = Gauge(
            'arb_feed_health',
            'Feed health score (0-1)',
            ['exchange']
        )
        
        # ===== ARBITRAGE METRICS =====
        self.opportunities_detected_total = Counter(
            'arb_opportunities_detected_total',
            'Total arbitrage opportunities detected',
            ['type', 'pair']  # type: simple, triangular, cross_exchange, etc.
        )
        
        self.opportunity_profit_percent = Histogram(
            'arb_opportunity_profit_percent',
            'Profit percentage of detected opportunities',
            ['type'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        )
        
        self.current_best_opportunity = Gauge(
            'arb_current_best_opportunity_percent',
            'Best current opportunity profit percentage',
            ['type']
        )
        
        # ===== EXECUTION METRICS =====
        self.trades_executed_total = Counter(
            'arb_trades_executed_total',
            'Total trades executed',
            ['exchange', 'result']  # result: success, failed
        )
        
        self.trade_latency = Histogram(
            'arb_trade_latency_seconds',
            'Trade execution latency',
            ['exchange'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
        )
        
        self.slippage_percent = Histogram(
            'arb_slippage_percent',
            'Execution slippage percentage',
            ['exchange'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0]
        )
        
        # ===== ML METRICS =====
        self.ml_predictions_total = Counter(
            'arb_ml_predictions_total',
            'Total ML predictions made',
            ['model', 'signal']  # signal: high, medium, low
        )
        
        self.ml_prediction_latency = Histogram(
            'arb_ml_prediction_latency_seconds',
            'ML prediction latency',
            ['model'],
            buckets=[0.001, 0.005, 0.01, 0.02, 0.05, 0.1]
        )
        
        self.ml_model_accuracy = Gauge(
            'arb_ml_model_accuracy',
            'ML model accuracy (rolling)',
            ['model']
        )
        
        # ===== SYSTEM METRICS =====
        self.websocket_connections = Gauge(
            'arb_websocket_connections',
            'Active WebSocket connections',
            ['type']  # type: exchange, dashboard
        )
        
        self.tick_storage_total = Gauge(
            'arb_tick_storage_total',
            'Total ticks stored'
        )
        
        self.memory_usage_bytes = Gauge(
            'arb_memory_usage_bytes',
            'Memory usage in bytes'
        )
        
        # Info metric for version/config
        self.bot_info = Info(
            'arb_bot',
            'Arbitrage bot information'
        )
        self.bot_info.info({
            'version': '1.0.0',
            'mode': 'simulation',  # Would be set dynamically
        })
    
    def _background_updates(self):
        """Background thread for periodic metric updates"""
        while self._running:
            try:
                self._update_feed_metrics()
                self._update_system_metrics()
                time.sleep(1)  # Update every second
            except Exception as e:
                logger.error(f"Metrics update error: {e}")
    
    def _update_feed_metrics(self):
        """Update feed health metrics"""
        now = datetime.now()
        
        for key, last_update in self._feed_last_update.items():
            exchange, pair = key.split(':')
            staleness = (now - last_update).total_seconds()
            
            if self.enable_prometheus:
                self.feed_staleness.labels(exchange=exchange, pair=pair).set(staleness)
        
        # Calculate feed health per exchange
        exchange_staleness: Dict[str, List[float]] = defaultdict(list)
        for key, last_update in self._feed_last_update.items():
            exchange = key.split(':')[0]
            staleness = (now - last_update).total_seconds()
            exchange_staleness[exchange].append(staleness)
        
        for exchange, staleness_list in exchange_staleness.items():
            if staleness_list:
                avg_staleness = sum(staleness_list) / len(staleness_list)
                # Health score: 1.0 if <0.5s, decreasing to 0 at 10s
                health = max(0, 1 - (avg_staleness / 10))
                
                if self.enable_prometheus:
                    self.feed_health.labels(exchange=exchange).set(health)
                
                self._time_series[f"feed_health:{exchange}"].append((now, health))
    
    def _update_system_metrics(self):
        """Update system resource metrics"""
        try:
            import psutil
            process = psutil.Process()
            memory = process.memory_info().rss
            
            if self.enable_prometheus:
                self.memory_usage_bytes.set(memory)
        except ImportError:
            pass
    
    # ===== PUBLIC METHODS FOR RECORDING METRICS =====
    
    def record_price_update(
        self,
        exchange: str,
        pair: str,
        latency_ms: Optional[float] = None
    ):
        """Record a price update"""
        now = datetime.now()
        key = f"{exchange}:{pair}"
        
        self._feed_last_update[key] = now
        self._feed_update_counts[key] += 1
        
        if latency_ms:
            self._feed_latencies[exchange].append(latency_ms)
        
        if self.enable_prometheus:
            self.price_updates_total.labels(exchange=exchange, pair=pair).inc()
            if latency_ms:
                self.price_update_latency.labels(exchange=exchange).observe(latency_ms / 1000)
    
    def record_opportunity(
        self,
        opp_type: str,
        pair: str,
        profit_percent: float
    ):
        """Record detected arbitrage opportunity"""
        now = datetime.now()
        
        if self.enable_prometheus:
            self.opportunities_detected_total.labels(type=opp_type, pair=pair).inc()
            self.opportunity_profit_percent.labels(type=opp_type).observe(profit_percent)
        
        self._time_series[f"opportunity:{opp_type}"].append((now, profit_percent))
    
    def record_best_opportunity(self, opp_type: str, profit_percent: float):
        """Update current best opportunity"""
        if self.enable_prometheus:
            self.current_best_opportunity.labels(type=opp_type).set(profit_percent)
    
    def record_trade(
        self,
        exchange: str,
        success: bool,
        latency_ms: float,
        slippage_percent: float
    ):
        """Record trade execution"""
        result = "success" if success else "failed"
        
        if self.enable_prometheus:
            self.trades_executed_total.labels(exchange=exchange, result=result).inc()
            self.trade_latency.labels(exchange=exchange).observe(latency_ms / 1000)
            self.slippage_percent.labels(exchange=exchange).observe(slippage_percent)
    
    def record_ml_prediction(
        self,
        model: str,
        signal: str,
        latency_ms: float,
        accuracy: Optional[float] = None
    ):
        """Record ML prediction"""
        if self.enable_prometheus:
            self.ml_predictions_total.labels(model=model, signal=signal).inc()
            self.ml_prediction_latency.labels(model=model).observe(latency_ms / 1000)
            if accuracy is not None:
                self.ml_model_accuracy.labels(model=model).set(accuracy)
    
    def record_websocket_connection(self, conn_type: str, count: int):
        """Update WebSocket connection count"""
        if self.enable_prometheus:
            self.websocket_connections.labels(type=conn_type).set(count)
    
    def record_tick_storage(self, total_ticks: int):
        """Update tick storage count"""
        if self.enable_prometheus:
            self.tick_storage_total.set(total_ticks)
    
    # ===== METRIC EXPORT =====
    
    def get_prometheus_metrics(self) -> bytes:
        """Generate Prometheus metrics output"""
        if self.enable_prometheus:
            return generate_latest(REGISTRY)
        return b""
    
    def get_prometheus_content_type(self) -> str:
        """Get Prometheus content type"""
        if self.enable_prometheus:
            return CONTENT_TYPE_LATEST
        return "text/plain"
    
    def get_metrics_summary(self) -> dict:
        """Get summary of all metrics for dashboard"""
        now = datetime.now()
        
        # Calculate feed statistics
        feed_stats = {}
        for key, last_update in self._feed_last_update.items():
            exchange = key.split(':')[0]
            if exchange not in feed_stats:
                feed_stats[exchange] = {
                    "update_count": 0,
                    "avg_latency_ms": 0,
                    "staleness_s": 0,
                    "health": 0,
                }
            
            staleness = (now - last_update).total_seconds()
            latencies = list(self._feed_latencies.get(exchange, []))
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            
            feed_stats[exchange]["update_count"] += self._feed_update_counts.get(key, 0)
            feed_stats[exchange]["staleness_s"] = max(feed_stats[exchange]["staleness_s"], staleness)
            feed_stats[exchange]["avg_latency_ms"] = avg_latency
            feed_stats[exchange]["health"] = max(0, 1 - (staleness / 10))
        
        # Get recent time series
        recent_opportunities = {}
        for key, series in self._time_series.items():
            if key.startswith("opportunity:"):
                opp_type = key.split(":")[1]
                recent = [(t.isoformat(), v) for t, v in series if (now - t).total_seconds() < 300]
                recent_opportunities[opp_type] = recent[-50:]  # Last 50
        
        return {
            "prometheus_enabled": self.enable_prometheus,
            "feed_statistics": feed_stats,
            "recent_opportunities": recent_opportunities,
            "total_feeds_active": len(self._feed_last_update),
        }
    
    def get_state(self) -> dict:
        """Get current state for API"""
        return self.get_metrics_summary()
    
    def stop(self):
        """Stop background thread"""
        self._running = False


# Grafana Dashboard JSON Configuration
GRAFANA_DASHBOARD = {
    "title": "Crypto Arbitrage Bot",
    "uid": "arb-bot-main",
    "panels": [
        {
            "title": "Price Updates Rate",
            "type": "graph",
            "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
            "targets": [{
                "expr": "rate(arb_price_updates_total[1m])",
                "legendFormat": "{{exchange}} - {{pair}}"
            }]
        },
        {
            "title": "Feed Latency",
            "type": "graph",
            "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
            "targets": [{
                "expr": "histogram_quantile(0.95, rate(arb_price_update_latency_seconds_bucket[5m]))",
                "legendFormat": "p95 {{exchange}}"
            }]
        },
        {
            "title": "Feed Health",
            "type": "gauge",
            "gridPos": {"x": 0, "y": 8, "w": 6, "h": 6},
            "targets": [{
                "expr": "arb_feed_health",
                "legendFormat": "{{exchange}}"
            }]
        },
        {
            "title": "Opportunities Detected",
            "type": "graph",
            "gridPos": {"x": 6, "y": 8, "w": 12, "h": 6},
            "targets": [{
                "expr": "rate(arb_opportunities_detected_total[5m])",
                "legendFormat": "{{type}}"
            }]
        },
        {
            "title": "Best Opportunity",
            "type": "stat",
            "gridPos": {"x": 18, "y": 8, "w": 6, "h": 6},
            "targets": [{
                "expr": "arb_current_best_opportunity_percent",
                "legendFormat": "{{type}}"
            }]
        },
        {
            "title": "Opportunity Profit Distribution",
            "type": "heatmap",
            "gridPos": {"x": 0, "y": 14, "w": 12, "h": 8},
            "targets": [{
                "expr": "rate(arb_opportunity_profit_percent_bucket[5m])",
                "legendFormat": "{{le}}"
            }]
        },
        {
            "title": "Trade Execution Latency",
            "type": "graph",
            "gridPos": {"x": 12, "y": 14, "w": 12, "h": 8},
            "targets": [{
                "expr": "histogram_quantile(0.95, rate(arb_trade_latency_seconds_bucket[5m]))",
                "legendFormat": "p95 {{exchange}}"
            }]
        },
        {
            "title": "ML Prediction Latency",
            "type": "graph",
            "gridPos": {"x": 0, "y": 22, "w": 12, "h": 6},
            "targets": [{
                "expr": "histogram_quantile(0.99, rate(arb_ml_prediction_latency_seconds_bucket[5m]))",
                "legendFormat": "p99 {{model}}"
            }]
        },
        {
            "title": "System Memory",
            "type": "graph",
            "gridPos": {"x": 12, "y": 22, "w": 12, "h": 6},
            "targets": [{
                "expr": "arb_memory_usage_bytes / 1024 / 1024",
                "legendFormat": "Memory (MB)"
            }]
        },
    ]
}


def get_grafana_dashboard_json() -> dict:
    """Get Grafana dashboard configuration"""
    return GRAFANA_DASHBOARD


# Global metrics engine instance
metrics_engine = MetricsEngine()
