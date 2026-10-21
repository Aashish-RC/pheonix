"""Inbox Store: Thread-safe persistent notification storage and query engine."""

import threading
from typing import Dict, List, Optional
from ..core.interfaces import BaseInboxStore
from ..core.models import (
    NotificationChannel,
    NotificationItem,
)


class InboxStore(BaseInboxStore):
    """Local thread-safe persistent inbox repository for user notifications."""

    def __init__(self):
        self._lock = threading.Lock()
        self._items: Dict[str, NotificationItem] = {}

    def save_notification(self, item: NotificationItem) -> None:
        with self._lock:
            self._items[item.notification_id] = item

    def get_notification(self, notification_id: str) -> Optional[NotificationItem]:
        with self._lock:
            return self._items.get(notification_id)

    def list_notifications(
        self,
        channel: Optional[NotificationChannel] = None,
        unread_only: bool = False,
        limit: int = 50,
        user_id: Optional[str] = None,
    ) -> List[NotificationItem]:
        with self._lock:
            results = list(self._items.values())

            if user_id is not None:
                results = [item for item in results if item.user_id == user_id]

            if channel is not None:
                results = [item for item in results if channel in item.channels]

            if unread_only:
                results = [item for item in results if not item.is_read]

            # Sort descending by timestamp
            results.sort(key=lambda x: x.created_at, reverse=True)
            return results[:limit]

    def get_user_feed(self, user_id: str, limit: int = 50) -> List[NotificationItem]:
        return self.list_notifications(user_id=user_id, limit=limit)

    def mark_as_read(self, notification_id: str) -> bool:
        with self._lock:
            item = self._items.get(notification_id)
            if item:
                item.is_read = True
                return True
            return False

    def delete_notification(self, notification_id: str) -> bool:
        with self._lock:
            return self._items.pop(notification_id, None) is not None

    def get_unread_count(self) -> int:
        with self._lock:
            return sum(1 for item in self._items.values() if not item.is_read)
