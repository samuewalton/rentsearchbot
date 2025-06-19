# -*- coding: utf-8 -*-
"""Simple notification management placeholder."""

import logging
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_notifications: List[Dict[str, Any]] = []


def add_notification(user_id: int, notification_type: str, title: str, message: str) -> None:
    """Store a notification for a user."""
    _notifications.append({
        "user_id": user_id,
        "type": notification_type,
        "title": title,
        "message": message,
        "is_read": False,
        "created_at": datetime.now(),
    })


def get_user_notifications(user_id: int) -> List[Dict[str, Any]]:
    """Return notifications for the specified user."""
    return [n for n in _notifications if n.get("user_id") == user_id]


class NotificationManager:
    def add_notification(self, user_id: int, notification_type: str, title: str, message: str) -> None:
        add_notification(user_id, notification_type, title, message)

    def get_user_notifications(self, user_id: int) -> List[Dict[str, Any]]:
        return get_user_notifications(user_id)


notification_manager = NotificationManager()

