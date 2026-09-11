# -*- coding: utf-8 -*-
"""Notification management (S4).

שתי שכבות:
  * אחסון in-memory לקריאה מהבוט (get_user_notifications)
  * תור outbox + worker אסינכרוני ששולח לטלגרם בזמן אמת
"""

import asyncio
import logging
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List

logger = logging.getLogger(__name__)

_notifications: List[Dict[str, Any]] = []
_outbox: Deque[Dict[str, Any]] = deque(maxlen=1000)


def add_notification(
    user_id: int, notification_type: str, title: str, message: str
) -> None:
    """שומר התראה למשתמש ומכניס אותה לתור השליחה לטלגרם."""
    _notifications.append(
        {
            "user_id": user_id,
            "type": notification_type,
            "title": title,
            "message": message,
            "is_read": False,
            "created_at": datetime.now(),
        }
    )
    _outbox.append({"user_id": user_id, "title": title, "message": message})


def get_user_notifications(user_id: int) -> List[Dict[str, Any]]:
    """מחזיר התראות שמורות של המשתמש."""
    return [n for n in _notifications if n.get("user_id") == user_id]


async def notification_sender_worker(bot: Any, poll_interval: float = 10.0) -> None:
    """לולאת רקע: שולחת התראות מהתור לטלגרם. מופעלת מ-bot_core.main."""
    logger.info("notification sender started")
    while True:
        try:
            while _outbox:
                item = _outbox.popleft()
                try:
                    await bot.send_message(
                        item["user_id"],
                        f"{item['title']}\n{item['message']}",
                    )
                except Exception as e:
                    logger.error(
                        f"שליחת התראה ל-{item.get('user_id')} נכשלה: {e}"
                    )
            await asyncio.sleep(poll_interval)
        except asyncio.CancelledError:
            logger.info("notification sender stopped")
            raise


class NotificationManager:
    def add_notification(
        self, user_id: int, notification_type: str, title: str, message: str
    ) -> None:
        add_notification(user_id, notification_type, title, message)

    def get_user_notifications(self, user_id: int) -> List[Dict[str, Any]]:
        return get_user_notifications(user_id)


notification_manager = NotificationManager()
