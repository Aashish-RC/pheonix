"""Novu Multi-Channel Backend and Unified Notification Dispatcher."""

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from .models import (
    DeliveryStatus,
    DispatchReceipt,
    NotificationChannel,
    NotificationItem,
    NotificationPriority,
    utc_now,
)
from ..channels.dispatcher import ChannelDispatcher
from ..storage.inbox_store import InboxStore


class NovuBackend:
    """Novu In-App & Multi-Channel Notification Integration with local mock inbox fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        backend_url: str = "https://api.novu.co",
        timeout: float = 5.0,
        inbox_store: Optional[InboxStore] = None,
    ):
        self.api_key = api_key or os.getenv("NOVU_API_KEY")
        self.backend_url = (backend_url or "https://api.novu.co").rstrip("/")
        self.timeout = timeout
        self.inbox_store = inbox_store or InboxStore()

    def trigger(
        self,
        event: str,
        subscriber_id: str,
        payload: Optional[Dict[str, Any]] = None,
        overrides: Optional[Dict[str, Any]] = None,
    ) -> NotificationItem:
        """Triggers a notification event via Novu Cloud REST API or persists to local inbox store."""
        data = payload or {}
        title = data.get("title") or event.replace("_", " ").title()
        body = data.get("message") or data.get("body") or f"Event '{event}' occurred."

        item = NotificationItem(
            user_id=subscriber_id,
            title=title,
            body=body,
            priority=NotificationPriority.NORMAL,
            channels=[NotificationChannel.INBOX, NotificationChannel.DESKTOP],
            sender="NovuDispatcher",
            metadata={"event": event, "payload": data, "overrides": overrides or {}},
            created_at=utc_now(),
        )

        # 1. Always record in local mock inbox store for offline resilience and local inspection
        self.inbox_store.save_notification(item)

        # 2. If Novu API Key is configured, trigger remote event in Novu
        if self.api_key:
            try:
                endpoint = f"{self.backend_url}/v1/events/trigger"
                post_body = json.dumps({
                    "name": event,
                    "to": {"subscriberId": subscriber_id},
                    "payload": data,
                    "overrides": overrides or {},
                }).encode("utf-8")
                req = urllib.request.Request(
                    endpoint,
                    data=post_body,
                    headers={
                        "Authorization": f"ApiKey {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    pass
            except Exception:
                # Log or tolerate network failure; local feed is preserved
                pass

        return item

    def get_user_feed(self, user_id: str) -> List[NotificationItem]:
        """Returns chronological notifications for the given user."""
        return self.inbox_store.get_user_feed(user_id=user_id)


_global_backend: Optional[NovuBackend] = None


def get_default_backend() -> NovuBackend:
    global _global_backend
    if _global_backend is None:
        _global_backend = NovuBackend()
    return _global_backend


def notify(
    user_id: str,
    event: str,
    message: Optional[str] = None,
    title: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    backend: Optional[NovuBackend] = None,
) -> NotificationItem:
    """Dispatches a notification to the user's feed and multi-channel backend."""
    b = backend or get_default_backend()
    p = payload.copy() if payload else {}
    if message:
        p["message"] = message
    if title:
        p["title"] = title
    return b.trigger(event=event, subscriber_id=user_id, payload=p)


__all__ = [
    "ChannelDispatcher",
    "NovuBackend",
    "get_default_backend",
    "notify",
]
