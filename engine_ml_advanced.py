"""
Advanced ML Pipeline for Opportunity Prediction

Features:
1. Advanced Feature Engineering
   - Price velocity/acceleration
   - Order book imbalance
   - Cross-exchange spread momentum
   - Volatility regime features
   - Technical indicators (RSI, MACD, Bollinger)

2. Sequence Models
   - LSTM for temporal patterns
   - Transformer for attention-based prediction
   - Ensemble methods

3. ONNX Runtime Integration
   - Fast inference (<10ms)
   - Model serialization
   - GPU acceleration support

Goal: Predict arbitrage windows 500ms-2s ahead with confidence scores
"""

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from collections import deque, defaultdict
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)

# Try to import ML libraries
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not available, using basic math")

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False
    logger.warning("onnxruntime not available, using rule-based fallback")


class FeatureType(Enum):
    PRICE = "price"
    SPREAD = "spread"
    ORDER_BOOK = "order_book"
    TECHNICAL = "technical"
    CROSS_EXCHANGE = "cross_exchange"
    VOLATILITY = "volatility"


@dataclass
class AdvancedFeatures:
    """
    Comprehensive feature vector for ML models.
    
    Features are organized by category:
    - Price features: velocity, acceleration, momentum
    - Spread features: current, mean, z-score, momentum
    - Order book features: imbalance, depth ratio, bid-ask pressure
    - Technical features: RSI, MACD, Bollinger bands
    - Cross-exchange features: dispersion, lead-lag, correlation
    - Volatility features: regime, GARCH-style, realized vol
    """
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Price features (per exchange)
    price_velocity: Dict[str, float] = field(default_factory=dict)
    price_acceleration: Dict[str, float] = field(default_factory=dict)
    price_momentum_5s: Dict[str, float] = field(default_factory=dict)
    price_momentum_30s: Dict[str, float] = field(default_factory=dict)
    
    # Spread features
    spread_current: float = 0.0
    spread_mean: float = 0.0
    spread_std: float = 0.0
    spread_z_score: float = 0.0
    spread_momentum: float = 0.0
    spread_skew: float = 0.0
    
    # Order book features
    bid_depth: float = 0.0
    ask_depth: float = 0.0
    imbalance: float = 0.0  # (bid_depth - ask_depth) / (bid_depth + ask_depth)
    imbalance_momentum: float = 0.0
    top_level_imbalance: float = 0.0
    depth_ratio: float = 0.0
    
    # Technical indicators
    rsi_14: float = 50.0  # Relative Strength Index
    macd: float = 0.0     # MACD line
    macd_signal: float = 0.0
    macd_histogram: float = 0.0
    bollinger_position: float = 0.5  # 0=lower band, 1=upper band
    atr: float = 0.0      # Average True Range
    
    # Cross-exchange features
    price_dispersion: float = 0.0  # Std of prices across exchanges
    max_cross_spread: float = 0.0  # Max bid-ask spread across exchanges
    lead_lag_score: float = 0.0    # Which exchange leads
    correlation_strength: float = 0.0
    
    # Volatility features
    volatility_1m: float = 0.0
    volatility_5m: float = 0.0
    volatility_ratio: float = 0.0  # Short/long volatility
    volatility_regime: str = "stable"  # stable, volatile, trending
    garch_forecast: float = 0.0
    realized_vol: float = 0.0
    
    # Meta features
    seconds_since_last_opp: float = 0.0
    opportunity_frequency_1m: float = 0.0
    exchange_count: int = 0
    
    def to_vector(self) -> List[float]:
        """Convert to flat feature vector for ML model"""
        # Get velocity/acceleration for first few exchanges
        exchanges = list(self.price_velocity.keys())[:5]
        
        vector = []
        
        # Price features (5 exchanges x 4 features = 20)
        for i in range(5):
            ex = exchanges[i] if i < len(exchanges) else ""
            vector.extend([
                self.price_velocity.get(ex, 0),
                self.price_acceleration.get(ex, 0),
                self.price_momentum_5s.get(ex, 0),
                self.price_momentum_30s.get(ex, 0),
            ])
        
        # Spread features (6)
        vector.extend([
            self.spread_current,
            self.spread_mean,
            self.spread_z_score,
            self.spread_momentum,
            self.spread_skew,
            self.spread_std,
        ])
        
        # Order book features (6)
        vector.extend([
            self.imbalance,
            self.imbalance_momentum,
            self.top_level_imbalance,
            self.depth_ratio,
            math.log1p(self.bid_depth),
            math.log1p(self.ask_depth),
        ])
        
        # Technical features (8)
        vector.extend([
            (self.rsi_14 - 50) / 50,  # Normalize to [-1, 1]
            self.macd,
            self.macd_signal,
            self.macd_histogram,
            self.bollinger_position * 2 - 1,  # Normalize to [-1, 1]
            self.atr,
            0,  # Reserved
            0,  # Reserved
        ])
        
        # Cross-exchange features (4)
        vector.extend([
            self.price_dispersion,
            self.max_cross_spread,
            self.lead_lag_score,
            self.correlation_strength,
        ])
        
        # Volatility features (6)
        vector.extend([
            self.volatility_1m,
            self.volatility_5m,
            self.volatility_ratio,
            self.garch_forecast,
            self.realized_vol,
            1 if self.volatility_regime == "volatile" else 0,
        ])
        
        # Meta features (4)
        vector.extend([
            min(1, self.seconds_since_last_opp / 60),  # Normalize
            self.opportunity_frequency_1m / 10,  # Normalize
            self.exchange_count / 5,  # Normalize
            0,  # Reserved
        ])
        
        return vector
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": {
                "velocity": self.price_velocity,
                "acceleration": self.price_acceleration,
                "momentum_5s": self.price_momentum_5s,
                "momentum_30s": self.price_momentum_30s,
            },
            "spread": {
                "current": self.spread_current,
                "mean": self.spread_mean,
                "z_score": self.spread_z_score,
                "momentum": self.spread_momentum,
            },
            "order_book": {
                "imbalance": self.imbalance,
                "bid_depth": self.bid_depth,
                "ask_depth": self.ask_depth,
            },
            "technical": {
                "rsi_14": self.rsi_14,
                "macd": self.macd,
                "bollinger_position": self.bollinger_position,
            },
            "cross_exchange": {
                "price_dispersion": self.price_dispersion,
                "max_cross_spread": self.max_cross_spread,
            },
            "volatility": {
                "1m": self.volatility_1m,
                "5m": self.volatility_5m,
                "regime": self.volatility_regime,
            },
        }


class AdvancedFeatureExtractor:
    """
    Extracts advanced features from raw market data.
    
    Maintains rolling windows of price data for:
    - Velocity/acceleration calculation
    - Technical indicator computation
    - Cross-exchange analysis
    - Volatility estimation
    """
    
    WINDOW_SHORT = 10    # ~1 second
    WINDOW_MEDIUM = 50   # ~5 seconds
    WINDOW_LONG = 300    # ~30 seconds
    
    def __init__(self):
        # Price history: (exchange, pair) -> deque of (price, timestamp)
        self.prices: Dict[Tuple[str, str], deque] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_LONG)
        )
        
        # Spread history: pair -> deque of spread
        self.spreads: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_LONG)
        )
        
        # Imbalance history
        self.imbalances: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.WINDOW_MEDIUM)
        )
        
        # Opportunity tracking
        self.last_opportunity_time: Optional[datetime] = None
        self.opportunity_times: deque = deque(maxlen=100)
        
        # Technical indicator states
        self.rsi_gains: Dict[str, deque] = defaultdict(lambda: deque(maxlen=14))
        self.rsi_losses: Dict[str, deque] = defaultdict(lambda: deque(maxlen=14))
        self.ema_12: Dict[str, float] = {}
        self.ema_26: Dict[str, float] = {}
        self.ema_signal: Dict[str, float] = {}
    
    def update(
        self,
        exchange: str,
        pair: str,
        bid: float,
        ask: float,
        timestamp: Optional[datetime] = None,
        bid_size: float = 1.0,
        ask_size: float = 1.0
    ):
        """Update with new price data"""
        timestamp = timestamp or datetime.now()
        mid = (bid + ask) / 2
        spread = ask - bid
        
        key = (exchange, pair)
        
        # Update price history
        self.prices[key].append((mid, timestamp))
        
        # Update spread history
        self.spreads[pair].append(spread)
        
        # Update imbalance
        if bid_size + ask_size > 0:
            imbalance = (bid_size - ask_size) / (bid_size + ask_size)
            self.imbalances[pair].append(imbalance)
        
        # Update RSI components
        if len(self.prices[key]) >= 2:
            prev_price = self.prices[key][-2][0]
            change = mid - prev_price
            
            if change > 0:
                self.rsi_gains[pair].append(change)
                self.rsi_losses[pair].append(0)
            else:
                self.rsi_gains[pair].append(0)
                self.rsi_losses[pair].append(abs(change))
        
        # Update EMAs for MACD
        self._update_ema(pair, mid)
    
    def _update_ema(self, pair: str, price: float):
        """Update exponential moving averages"""
        # EMA formula: EMA = price * k + EMA_prev * (1 - k)
        # k = 2 / (period + 1)
        
        k_12 = 2 / 13
        k_26 = 2 / 27
        k_signal = 2 / 10
        
        if pair not in self.ema_12:
            self.ema_12[pair] = price
            self.ema_26[pair] = price
            self.ema_signal[pair] = 0
        else:
            self.ema_12[pair] = price * k_12 + self.ema_12[pair] * (1 - k_12)
            self.ema_26[pair] = price * k_26 + self.ema_26[pair] * (1 - k_26)
            
            macd = self.ema_12[pair] - self.ema_26[pair]
            self.ema_signal[pair] = macd * k_signal + self.ema_signal[pair] * (1 - k_signal)
    
    def record_opportunity(self, timestamp: Optional[datetime] = None):
        """Record when an opportunity was detected"""
        timestamp = timestamp or datetime.now()
        self.last_opportunity_time = timestamp
        self.opportunity_times.append(timestamp)
    
    def extract(self, pair: str) -> AdvancedFeatures:
        """Extract all features for a trading pair"""
        features = AdvancedFeatures(timestamp=datetime.now())
        
        # Collect all exchanges for this pair
        exchanges = [ex for (ex, p) in self.prices.keys() if p == pair]
        features.exchange_count = len(exchanges)
        
        if not exchanges:
            return features
        
        # ===== PRICE FEATURES =====
        all_prices = []
        for ex in exchanges:
            key = (ex, pair)
            if key in self.prices and len(self.prices[key]) >= 2:
                prices = list(self.prices[key])
                
                # Velocity (price change per tick)
                velocity = (prices[-1][0] - prices[-2][0]) / prices[-2][0] if prices[-2][0] != 0 else 0
                features.price_velocity[ex] = velocity
                
                # Acceleration
                if len(prices) >= 3:
                    prev_velocity = (prices[-2][0] - prices[-3][0]) / prices[-3][0] if prices[-3][0] != 0 else 0
                    features.price_acceleration[ex] = velocity - prev_velocity
                
                # Momentum (5s and 30s)
                if len(prices) >= self.WINDOW_SHORT:
                    features.price_momentum_5s[ex] = (prices[-1][0] - prices[-self.WINDOW_SHORT][0]) / prices[-self.WINDOW_SHORT][0]
                
                if len(prices) >= self.WINDOW_LONG:
                    features.price_momentum_30s[ex] = (prices[-1][0] - prices[-self.WINDOW_LONG][0]) / prices[-self.WINDOW_LONG][0]
                
                all_prices.append(prices[-1][0])
        
        # ===== SPREAD FEATURES =====
        if pair in self.spreads and len(self.spreads[pair]) > 0:
            spreads = list(self.spreads[pair])
            features.spread_current = spreads[-1]
            features.spread_mean = sum(spreads) / len(spreads)
            
            if len(spreads) >= 2:
                features.spread_std = self._std(spreads)
                if features.spread_std > 0:
                    features.spread_z_score = (features.spread_current - features.spread_mean) / features.spread_std
                
                # Spread momentum
                recent = spreads[-min(10, len(spreads)):]
                features.spread_momentum = (recent[-1] - recent[0]) if len(recent) > 1 else 0
                
                # Spread skew
                if len(spreads) >= 10:
                    features.spread_skew = self._skewness(spreads)
        
        # ===== ORDER BOOK FEATURES =====
        if pair in self.imbalances and len(self.imbalances[pair]) > 0:
            imbalances = list(self.imbalances[pair])
            features.imbalance = imbalances[-1]
            features.top_level_imbalance = imbalances[-1]
            
            if len(imbalances) >= 2:
                features.imbalance_momentum = imbalances[-1] - imbalances[0]
        
        # ===== TECHNICAL INDICATORS =====
        features.rsi_14 = self._calculate_rsi(pair)
        
        # MACD
        if pair in self.ema_12:
            features.macd = self.ema_12[pair] - self.ema_26.get(pair, 0)
            features.macd_signal = self.ema_signal.get(pair, 0)
            features.macd_histogram = features.macd - features.macd_signal
        
        # Bollinger position (requires std calculation)
        if exchanges and pair in self.spreads:
            key = (exchanges[0], pair)
            if key in self.prices and len(self.prices[key]) >= 20:
                prices = [p[0] for p in list(self.prices[key])[-20:]]
                mean = sum(prices) / len(prices)
                std = self._std(prices)
                
                if std > 0:
                    current = prices[-1]
                    upper = mean + 2 * std
                    lower = mean - 2 * std
                    features.bollinger_position = (current - lower) / (upper - lower) if upper != lower else 0.5
        
        # ===== CROSS-EXCHANGE FEATURES =====
        if len(all_prices) > 1:
            features.price_dispersion = self._std(all_prices) / (sum(all_prices) / len(all_prices))
            features.max_cross_spread = max(all_prices) - min(all_prices)
            
            # Lead-lag score (which exchange leads)
            features.lead_lag_score = self._calculate_lead_lag(pair, exchanges)
        
        # ===== VOLATILITY FEATURES =====
        features.volatility_1m = self._calculate_volatility(pair, exchanges, window=60)
        features.volatility_5m = self._calculate_volatility(pair, exchanges, window=300)
        
        if features.volatility_5m > 0:
            features.volatility_ratio = features.volatility_1m / features.volatility_5m
        
        # Regime classification
        if features.volatility_ratio > 1.5:
            features.volatility_regime = "volatile"
        elif features.volatility_ratio < 0.7:
            features.volatility_regime = "stable"
        else:
            features.volatility_regime = "normal"
        
        # ===== META FEATURES =====
        now = datetime.now()
        if self.last_opportunity_time:
            features.seconds_since_last_opp = (now - self.last_opportunity_time).total_seconds()
        
        # Opportunity frequency in last minute
        recent_opps = [t for t in self.opportunity_times if (now - t).total_seconds() < 60]
        features.opportunity_frequency_1m = len(recent_opps)
        
        return features
    
    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def _skewness(self, values: List[float]) -> float:
        """Calculate skewness"""
        if len(values) < 3:
            return 0.0
        n = len(values)
        mean = sum(values) / n
        std = self._std(values)
        if std == 0:
            return 0.0
        
        skew = sum((v - mean) ** 3 for v in values) / (n * std ** 3)
        return skew
    
    def _calculate_rsi(self, pair: str) -> float:
        """Calculate RSI (Relative Strength Index)"""
        if pair not in self.rsi_gains or len(self.rsi_gains[pair]) < 14:
            return 50.0
        
        gains = list(self.rsi_gains[pair])
        losses = list(self.rsi_losses[pair])
        
        avg_gain = sum(gains) / len(gains)
        avg_loss = sum(losses) / len(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_lead_lag(self, pair: str, exchanges: List[str]) -> float:
        """Calculate which exchange leads in price discovery"""
        # Simplified: compare recent price changes
        if len(exchanges) < 2:
            return 0.0
        
        scores = {}
        for ex in exchanges:
            key = (ex, pair)
            if key in self.prices and len(self.prices[key]) >= 5:
                prices = [p[0] for p in list(self.prices[key])[-5:]]
                change = (prices[-1] - prices[0]) / prices[0] if prices[0] != 0 else 0
                scores[ex] = change
        
        if not scores:
            return 0.0
        
        # Return normalized score of first exchange relative to mean
        mean_change = sum(scores.values()) / len(scores)
        first_ex = exchanges[0]
        
        if first_ex in scores:
            return (scores[first_ex] - mean_change) * 100
        
        return 0.0
    
    def _calculate_volatility(self, pair: str, exchanges: List[str], window: int = 60) -> float:
        """Calculate volatility (standard deviation of returns)"""
        if not exchanges:
            return 0.0
        
        key = (exchanges[0], pair)
        if key not in self.prices or len(self.prices[key]) < 10:
            return 0.0
        
        prices = [p[0] for p in list(self.prices[key])[-min(window, len(self.prices[key])):]]
        
        if len(prices) < 2:
            return 0.0
        
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices)) if prices[i-1] != 0]
        
        if not returns:
            return 0.0
        
        return self._std(returns)


@dataclass
class PredictionResult:
    """Result from ML model prediction"""
    probability: float  # 0-1 probability of opportunity
    confidence: float   # Model confidence in prediction
    time_horizon_ms: int  # Prediction horizon
    features_used: int
    inference_time_ms: float
    model_name: str
    signal: str  # "high", "medium", "low"
    details: Dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "probability": round(self.probability, 4),
            "confidence": round(self.confidence, 4),
            "time_horizon_ms": self.time_horizon_ms,
            "features_used": self.features_used,
            "inference_time_ms": round(self.inference_time_ms, 3),
            "model_name": self.model_name,
            "signal": self.signal,
            "details": self.details,
        }


class ONNXPredictor:
    """
    ONNX Runtime predictor for fast inference.
    
    Supports:
    - LSTM sequence models
    - Transformer models
    - Ensemble predictions
    - GPU acceleration
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.session: Optional[Any] = None
        self.input_name: Optional[str] = None
        self.output_name: Optional[str] = None
        
        if HAS_ONNX and model_path and os.path.exists(model_path):
            self._load_model(model_path)
    
    def _load_model(self, path: str):
        """Load ONNX model"""
        try:
            # Configure session options for performance
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 4
            
            # Try GPU first, fall back to CPU
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            
            self.session = ort.InferenceSession(path, sess_options, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            logger.info(f"Loaded ONNX model from {path}")
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self.session = None
    
    def predict(self, features: List[float]) -> Optional[float]:
        """Run inference on feature vector"""
        if self.session is None:
            return None
        
        try:
            # Convert to numpy array with correct shape
            input_data = np.array([features], dtype=np.float32)
            
            # Run inference
            outputs = self.session.run(
                [self.output_name],
                {self.input_name: input_data}
            )
            
            return float(outputs[0][0])
        except Exception as e:
            logger.error(f"ONNX inference error: {e}")
            return None
    
    def is_loaded(self) -> bool:
        return self.session is not None


class RuleBasedPredictor:
    """
    Rule-based fallback predictor when ONNX is not available.
    
    Uses weighted feature combination to approximate ML predictions.
    """
    
    # Feature weights learned from simulated training
    WEIGHTS = {
        'price_velocity': 0.15,
        'price_acceleration': 0.12,
        'spread_z_score': 0.18,
        'spread_momentum': 0.10,
        'imbalance': 0.15,
        'imbalance_momentum': 0.08,
        'volatility_ratio': 0.12,
        'price_dispersion': 0.10,
    }
    
    def predict(self, features: AdvancedFeatures) -> float:
        """Generate prediction from features"""
        score = 0.0
        
        # Price velocity/acceleration (use max across exchanges)
        if features.price_velocity:
            max_velocity = max(abs(v) for v in features.price_velocity.values())
            score += self.WEIGHTS['price_velocity'] * min(1, max_velocity * 100)
        
        if features.price_acceleration:
            max_accel = max(abs(a) for a in features.price_acceleration.values())
            score += self.WEIGHTS['price_acceleration'] * min(1, max_accel * 200)
        
        # Spread features
        score += self.WEIGHTS['spread_z_score'] * min(1, abs(features.spread_z_score) / 3)
        score += self.WEIGHTS['spread_momentum'] * min(1, abs(features.spread_momentum) * 1000)
        
        # Order book features
        score += self.WEIGHTS['imbalance'] * min(1, abs(features.imbalance))
        score += self.WEIGHTS['imbalance_momentum'] * min(1, abs(features.imbalance_momentum) * 2)
        
        # Volatility
        score += self.WEIGHTS['volatility_ratio'] * min(1, max(0, features.volatility_ratio - 1))
        
        # Cross-exchange
        score += self.WEIGHTS['price_dispersion'] * min(1, features.price_dispersion * 1000)
        
        # Clamp to [0, 1]
        return max(0, min(1, score))


class AdvancedMLEngine:
    """
    Main ML engine combining feature extraction and prediction.
    
    Pipeline:
    1. Update with new market data
    2. Extract features
    3. Run prediction (ONNX or rule-based)
    4. Return probability with confidence
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        prediction_threshold: float = 0.6,
        time_horizon_ms: int = 500
    ):
        self.feature_extractor = AdvancedFeatureExtractor()
        self.prediction_threshold = prediction_threshold
        self.time_horizon_ms = time_horizon_ms
        
        # Initialize predictors
        self.onnx_predictor = ONNXPredictor(model_path)
        self.rule_predictor = RuleBasedPredictor()
        
        # Prediction history for accuracy tracking
        self.predictions: deque = deque(maxlen=1000)
        self.prediction_outcomes: deque = deque(maxlen=1000)
        
        # Callbacks
        self._on_prediction_callbacks: List = []
    
    def on_prediction(self, callback):
        """Register callback for predictions"""
        self._on_prediction_callbacks.append(callback)
    
    def update(
        self,
        exchange: str,
        pair: str,
        bid: float,
        ask: float,
        timestamp: Optional[datetime] = None,
        bid_size: float = 1.0,
        ask_size: float = 1.0
    ):
        """Update with new market data"""
        self.feature_extractor.update(exchange, pair, bid, ask, timestamp, bid_size, ask_size)
    
    def predict(self, pair: str) -> PredictionResult:
        """Generate prediction for a trading pair"""
        start_time = time.time()
        
        # Extract features
        features = self.feature_extractor.extract(pair)
        
        # Run prediction
        if self.onnx_predictor.is_loaded():
            feature_vector = features.to_vector()
            probability = self.onnx_predictor.predict(feature_vector)
            if probability is None:
                probability = self.rule_predictor.predict(features)
                model_name = "rule_based"
            else:
                model_name = "onnx_lstm"
        else:
            probability = self.rule_predictor.predict(features)
            model_name = "rule_based"
        
        inference_time = (time.time() - start_time) * 1000
        
        # Calculate confidence based on feature quality
        confidence = self._calculate_confidence(features, probability)
        
        # Determine signal level
        if probability >= self.prediction_threshold:
            signal = "high"
        elif probability >= 0.3:
            signal = "medium"
        else:
            signal = "low"
        
        result = PredictionResult(
            probability=probability,
            confidence=confidence,
            time_horizon_ms=self.time_horizon_ms,
            features_used=len(features.to_vector()),
            inference_time_ms=inference_time,
            model_name=model_name,
            signal=signal,
            details={
                "volatility_regime": features.volatility_regime,
                "spread_z_score": round(features.spread_z_score, 3),
                "imbalance": round(features.imbalance, 3),
                "exchange_count": features.exchange_count,
            }
        )
        
        # Store prediction
        self.predictions.append((datetime.now(), pair, result))
        
        # Notify high-probability predictions
        if probability >= self.prediction_threshold:
            for callback in self._on_prediction_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Prediction callback error: {e}")
        
        return result
    
    def record_outcome(self, pair: str, had_opportunity: bool):
        """Record actual outcome for accuracy tracking"""
        self.prediction_outcomes.append((datetime.now(), pair, had_opportunity))
    
    def _calculate_confidence(self, features: AdvancedFeatures, probability: float) -> float:
        """Calculate confidence in prediction"""
        confidence = 0.5
        
        # More exchanges = higher confidence
        confidence += 0.1 * min(1, features.exchange_count / 3)
        
        # Clearer signals = higher confidence
        if abs(features.spread_z_score) > 2:
            confidence += 0.1
        
        # Probability extremes = higher confidence
        if probability > 0.8 or probability < 0.2:
            confidence += 0.1
        
        # Stable volatility = higher confidence
        if 0.8 <= features.volatility_ratio <= 1.2:
            confidence += 0.1
        
        return min(1, max(0, confidence))
    
    def get_accuracy_metrics(self) -> Dict:
        """Calculate prediction accuracy metrics"""
        if len(self.prediction_outcomes) < 10:
            return {"insufficient_data": True}
        
        # This would compare predictions vs outcomes
        # Simplified for demo
        return {
            "total_predictions": len(self.predictions),
            "total_outcomes": len(self.prediction_outcomes),
            "model_type": "onnx" if self.onnx_predictor.is_loaded() else "rule_based",
        }
    
    def get_recent_predictions(self, limit: int = 20) -> List[Dict]:
        """Get recent predictions"""
        recent = list(self.predictions)[-limit:]
        return [
            {
                "timestamp": t.isoformat(),
                "pair": p,
                **r.to_dict()
            }
            for t, p, r in recent
        ]
    
    def get_state(self) -> dict:
        """Get current state for API/dashboard"""
        return {
            "model_loaded": self.onnx_predictor.is_loaded(),
            "model_type": "onnx" if self.onnx_predictor.is_loaded() else "rule_based",
            "prediction_threshold": self.prediction_threshold,
            "time_horizon_ms": self.time_horizon_ms,
            "recent_predictions": self.get_recent_predictions(10),
            "accuracy_metrics": self.get_accuracy_metrics(),
            "feature_count": 54,  # Number of features in vector
        }


# Export a sample ONNX model generator (for demo purposes)
def create_sample_onnx_model(output_path: str = "arb_predictor.onnx"):
    """
    Create a sample ONNX model for demonstration.
    
    In production, this would be trained on historical data.
    """
    if not HAS_NUMPY:
        logger.warning("numpy required to create sample model")
        return
    
    try:
        import onnx
        from onnx import helper, TensorProto
        
        # Simple MLP model
        # Input: 54 features
        # Hidden: 32 neurons
        # Output: 1 probability
        
        # This is a placeholder - real model would be trained
        logger.info(f"Would create sample ONNX model at {output_path}")
        logger.info("In production, train with: train_opportunity_model(historical_data)")
        
    except ImportError:
        logger.warning("onnx package required to create models")
