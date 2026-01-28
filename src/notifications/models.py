"""
Notification data models.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    WEBSOCKET = "websocket"  # Real-time dashboard
    EMAIL = "email"
    TELEGRAM = "telegram"
    DISCORD = "discord"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(str, Enum):
    """Types of notifications"""
    ARBITRAGE_OPPORTUNITY = "arbitrage_opportunity"
    TRIANGULAR_OPPORTUNITY = "triangular_opportunity"
    PRICE_ALERT = "price_alert"
    SYSTEM_ALERT = "system_alert"
    TRADE_EXECUTED = "trade_executed"
    CONNECTION_STATUS = "connection_status"


class Notification(BaseModel):
    """Notification message"""
    id: str
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.MEDIUM
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    # Delivery tracking
    channels: List[NotificationChannel] = [NotificationChannel.WEBSOCKET]
    delivered: bool = False
    delivery_errors: Optional[Dict[str, str]] = None


class NotificationPreferences(BaseModel):
    """User notification preferences"""
    user_id: int
    
    # Channel settings
    email_enabled: bool = False
    email_address: Optional[str] = None
    
    telegram_enabled: bool = False
    telegram_chat_id: Optional[str] = None
    
    discord_enabled: bool = False
    discord_webhook_url: Optional[str] = None
    
    # Event settings
    arbitrage_min_profit: float = 0.1  # Minimum profit % to notify
    notify_triangular: bool = True
    notify_system_alerts: bool = True
    
    # Quiet hours
    quiet_hours_enabled: bool = False
    quiet_hours_start: int = 22  # 10 PM
    quiet_hours_end: int = 8    # 8 AM


class PriceAlert(BaseModel):
    """User-defined price alert"""
    id: str
    user_id: int
    pair: str
    condition: str  # "above" or "below"
    target_price: float
    triggered: bool = False
    triggered_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
