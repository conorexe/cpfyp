"""
Notification service with multi-channel delivery.
"""

import os
import logging
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Dict, List, Callable, Any
from collections import deque
import uuid
import json

import aiohttp

from .models import (
    Notification, NotificationChannel, NotificationPriority,
    NotificationType, NotificationPreferences, PriceAlert,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Multi-channel notification service.
    
    Supports:
    - WebSocket (real-time to dashboard)
    - Email (SMTP)
    - Telegram bot
    - Discord webhook
    """
    
    def __init__(self):
        # Configuration from environment
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.notification_email = os.getenv("NOTIFICATION_EMAIL", "")
        
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        
        # WebSocket broadcast callback (set by dashboard)
        self._websocket_broadcast: Optional[Callable] = None
        
        # Notification history
        self._history: deque = deque(maxlen=100)
        
        # User preferences (in-memory, would be in database)
        self._preferences: Dict[int, NotificationPreferences] = {}
        
        # Price alerts
        self._price_alerts: Dict[str, PriceAlert] = {}
        
        # Statistics
        self.notifications_sent = 0
        self.notifications_failed = 0
    
    def set_websocket_broadcast(self, callback: Callable):
        """Set the WebSocket broadcast function"""
        self._websocket_broadcast = callback
    
    async def notify(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None,
        user_id: Optional[int] = None,
    ) -> Notification:
        """
        Send a notification through configured channels.
        
        Args:
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            priority: Priority level
            data: Additional data payload
            channels: Specific channels to use (None = all configured)
            user_id: Specific user to notify (None = broadcast)
        
        Returns:
            Notification object with delivery status
        """
        # Create notification
        notification = Notification(
            id=str(uuid.uuid4()),
            type=notification_type,
            title=title,
            message=message,
            priority=priority,
            data=data,
            channels=channels or [NotificationChannel.WEBSOCKET],
        )
        
        delivery_errors = {}
        
        # Deliver to each channel
        for channel in notification.channels:
            try:
                if channel == NotificationChannel.WEBSOCKET:
                    await self._send_websocket(notification)
                elif channel == NotificationChannel.EMAIL:
                    await self._send_email(notification, user_id)
                elif channel == NotificationChannel.TELEGRAM:
                    await self._send_telegram(notification, user_id)
                elif channel == NotificationChannel.DISCORD:
                    await self._send_discord(notification)
                    
            except Exception as e:
                logger.error(f"Failed to send notification via {channel}: {e}")
                delivery_errors[channel.value] = str(e)
                self.notifications_failed += 1
        
        # Update notification status
        notification.delivered = len(delivery_errors) == 0
        notification.delivery_errors = delivery_errors if delivery_errors else None
        
        # Store in history
        self._history.append(notification)
        
        if notification.delivered:
            self.notifications_sent += 1
        
        return notification
    
    async def _send_websocket(self, notification: Notification):
        """Send notification via WebSocket to dashboard"""
        if self._websocket_broadcast:
            await self._websocket_broadcast({
                "type": "notification",
                "data": {
                    "id": notification.id,
                    "notification_type": notification.type.value,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority.value,
                    "data": notification.data,
                    "timestamp": notification.timestamp.isoformat(),
                }
            })
            logger.debug(f"Sent WebSocket notification: {notification.title}")
    
    async def _send_email(
        self, 
        notification: Notification, 
        user_id: Optional[int] = None
    ):
        """Send notification via email"""
        if not all([self.smtp_host, self.smtp_user, self.smtp_password]):
            logger.debug("Email not configured, skipping")
            return
        
        # Get recipient email
        recipient = self.notification_email
        if user_id and user_id in self._preferences:
            prefs = self._preferences[user_id]
            if prefs.email_enabled and prefs.email_address:
                recipient = prefs.email_address
        
        if not recipient:
            return
        
        # Create email
        msg = MIMEMultipart()
        msg["From"] = self.smtp_user
        msg["To"] = recipient
        msg["Subject"] = f"[MarketScout] {notification.title}"
        
        # HTML body
        priority_color = {
            NotificationPriority.LOW: "#6c757d",
            NotificationPriority.MEDIUM: "#0d6efd",
            NotificationPriority.HIGH: "#fd7e14",
            NotificationPriority.CRITICAL: "#dc3545",
        }
        
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background: #1a1d26; color: #e8eaed; padding: 20px; border-radius: 10px;">
                <h2 style="color: {priority_color[notification.priority]}; margin-top: 0;">
                    {notification.title}
                </h2>
                <p style="font-size: 16px;">{notification.message}</p>
                <hr style="border-color: #2a2d3a;">
                <small style="color: #9aa0a6;">
                    {notification.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}
                </small>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html, "html"))
        
        # Send email (in thread pool to avoid blocking)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_smtp, msg, recipient)
        logger.info(f"Sent email notification to {recipient}")
    
    def _send_smtp(self, msg: MIMEMultipart, recipient: str):
        """Send SMTP email (blocking)"""
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
    
    async def _send_telegram(
        self, 
        notification: Notification, 
        user_id: Optional[int] = None
    ):
        """Send notification via Telegram bot"""
        token = self.telegram_bot_token
        chat_id = self.telegram_chat_id
        
        # Check user preferences
        if user_id and user_id in self._preferences:
            prefs = self._preferences[user_id]
            if prefs.telegram_enabled and prefs.telegram_chat_id:
                chat_id = prefs.telegram_chat_id
        
        if not token or not chat_id:
            logger.debug("Telegram not configured, skipping")
            return
        
        # Format message
        priority_emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.MEDIUM: "📊",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.CRITICAL: "🚨",
        }
        
        text = f"""
{priority_emoji[notification.priority]} *{notification.title}*

{notification.message}

_{notification.timestamp.strftime("%Y-%m-%d %H:%M:%S")}_
        """
        
        # Send via Telegram API
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"Telegram API error: {await resp.text()}")
        
        logger.info(f"Sent Telegram notification to {chat_id}")
    
    async def _send_discord(self, notification: Notification):
        """Send notification via Discord webhook"""
        if not self.discord_webhook_url:
            logger.debug("Discord not configured, skipping")
            return
        
        # Format Discord embed
        color_map = {
            NotificationPriority.LOW: 0x6c757d,
            NotificationPriority.MEDIUM: 0x0d6efd,
            NotificationPriority.HIGH: 0xfd7e14,
            NotificationPriority.CRITICAL: 0xdc3545,
        }
        
        embed = {
            "title": notification.title,
            "description": notification.message,
            "color": color_map[notification.priority],
            "timestamp": notification.timestamp.isoformat(),
            "footer": {
                "text": "MarketScout"
            }
        }
        
        # Add fields from data
        if notification.data:
            fields = []
            for key, value in notification.data.items():
                if isinstance(value, (int, float, str)):
                    fields.append({
                        "name": key.replace("_", " ").title(),
                        "value": str(value),
                        "inline": True,
                    })
            if fields:
                embed["fields"] = fields[:10]  # Max 10 fields
        
        payload = {"embeds": [embed]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.discord_webhook_url, json=payload) as resp:
                if resp.status not in [200, 204]:
                    raise Exception(f"Discord webhook error: {await resp.text()}")
        
        logger.info("Sent Discord notification")
    
    # Convenience methods for common notifications
    
    async def notify_arbitrage_opportunity(
        self,
        pair: str,
        buy_exchange: str,
        sell_exchange: str,
        profit_percent: float,
        buy_price: float,
        sell_price: float,
    ):
        """Send notification for arbitrage opportunity"""
        priority = NotificationPriority.LOW
        if profit_percent >= 0.5:
            priority = NotificationPriority.HIGH
        elif profit_percent >= 0.2:
            priority = NotificationPriority.MEDIUM
        
        channels = [NotificationChannel.WEBSOCKET]
        if profit_percent >= 0.5:
            # High-profit opportunities go to all channels
            if self.telegram_bot_token:
                channels.append(NotificationChannel.TELEGRAM)
            if self.discord_webhook_url:
                channels.append(NotificationChannel.DISCORD)
        
        await self.notify(
            notification_type=NotificationType.ARBITRAGE_OPPORTUNITY,
            title=f"Arbitrage: {pair}",
            message=f"Buy @ {buy_exchange} (${buy_price:,.2f}) → Sell @ {sell_exchange} (${sell_price:,.2f})\nProfit: {profit_percent:.3f}%",
            priority=priority,
            data={
                "pair": pair,
                "buy_exchange": buy_exchange,
                "sell_exchange": sell_exchange,
                "profit_percent": profit_percent,
                "buy_price": buy_price,
                "sell_price": sell_price,
            },
            channels=channels,
        )
    
    async def notify_system_alert(
        self,
        title: str,
        message: str,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
    ):
        """Send system alert notification"""
        channels = [NotificationChannel.WEBSOCKET]
        if priority in [NotificationPriority.HIGH, NotificationPriority.CRITICAL]:
            if self.telegram_bot_token:
                channels.append(NotificationChannel.TELEGRAM)
            if self.discord_webhook_url:
                channels.append(NotificationChannel.DISCORD)
            if self.smtp_host:
                channels.append(NotificationChannel.EMAIL)
        
        await self.notify(
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            message=message,
            priority=priority,
            channels=channels,
        )
    
    async def notify_connection_status(
        self,
        exchange: str,
        connected: bool,
    ):
        """Send connection status notification"""
        status = "Connected" if connected else "Disconnected"
        priority = NotificationPriority.LOW if connected else NotificationPriority.HIGH
        
        await self.notify(
            notification_type=NotificationType.CONNECTION_STATUS,
            title=f"{exchange} {status}",
            message=f"WebSocket connection to {exchange} is now {status.lower()}",
            priority=priority,
            data={"exchange": exchange, "connected": connected},
        )
    
    # Price alerts
    
    def create_price_alert(
        self,
        user_id: int,
        pair: str,
        condition: str,
        target_price: float,
    ) -> PriceAlert:
        """Create a new price alert"""
        alert = PriceAlert(
            id=str(uuid.uuid4()),
            user_id=user_id,
            pair=pair.upper(),
            condition=condition,
            target_price=target_price,
        )
        self._price_alerts[alert.id] = alert
        logger.info(f"Created price alert: {pair} {condition} ${target_price}")
        return alert
    
    async def check_price_alerts(self, pair: str, price: float):
        """Check and trigger price alerts"""
        for alert in list(self._price_alerts.values()):
            if alert.triggered or alert.pair != pair.upper():
                continue
            
            triggered = False
            if alert.condition == "above" and price >= alert.target_price:
                triggered = True
            elif alert.condition == "below" and price <= alert.target_price:
                triggered = True
            
            if triggered:
                alert.triggered = True
                alert.triggered_at = datetime.now()
                
                await self.notify(
                    notification_type=NotificationType.PRICE_ALERT,
                    title=f"Price Alert: {pair}",
                    message=f"{pair} is now {alert.condition} ${alert.target_price:,.2f}\nCurrent price: ${price:,.2f}",
                    priority=NotificationPriority.HIGH,
                    data={
                        "pair": pair,
                        "target_price": alert.target_price,
                        "current_price": price,
                        "condition": alert.condition,
                    },
                    channels=[
                        NotificationChannel.WEBSOCKET,
                        NotificationChannel.TELEGRAM,
                        NotificationChannel.DISCORD,
                    ],
                    user_id=alert.user_id,
                )
    
    def get_notification_history(self, limit: int = 50) -> List[Notification]:
        """Get recent notification history"""
        return list(self._history)[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get notification statistics"""
        return {
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "history_count": len(self._history),
            "active_price_alerts": len([a for a in self._price_alerts.values() if not a.triggered]),
            "channels_configured": {
                "email": bool(self.smtp_host),
                "telegram": bool(self.telegram_bot_token),
                "discord": bool(self.discord_webhook_url),
            }
        }


# Global notification service instance
notification_service = NotificationService()
