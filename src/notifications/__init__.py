"""
Notification system for MarketScout.

Supports multiple channels:
- WebSocket (real-time dashboard)
- Email (SMTP)
- Telegram bot
- Discord webhook
"""

from .models import Notification, NotificationChannel, NotificationPriority
from .service import NotificationService, notification_service

__all__ = [
    "Notification",
    "NotificationChannel",
    "NotificationPriority",
    "NotificationService",
    "notification_service",
]
