"""Core data models for Pheonix Notifications Engine."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NotificationChannel(str, Enum):
    INBOX = "inbox"
    DESKTOP = "desktop"
    WEBHOOK = "webhook"
    DISCORD = "discord"
    SLACK = "slack"
    EMAIL = "email"


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationItem(BaseModel):
    notification_id: str = Field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:8]}")
    user_id: Optional[str] = None
    title: str
    body: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.INBOX, NotificationChannel.DESKTOP]
    )
    task_id: Optional[str] = None
    sender: str = "PheonixSystem"
    is_read: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class QuietHoursPolicy(BaseModel):
    enabled: bool = False
    start_hour: int = 22  # e.g., 10 PM
    end_hour: int = 7     # e.g., 7 AM
    timezone_offset_hours: float = 0.0
    bypass_for_urgent: bool = True


class NotificationRule(BaseModel):
    rule_id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:6]}")
    trigger_event: str  # e.g., "task_completed", "provider_degraded", "security_flag"
    min_priority: NotificationPriority = NotificationPriority.NORMAL
    target_channels: List[NotificationChannel] = Field(
        default_factory=lambda: [NotificationChannel.INBOX, NotificationChannel.DESKTOP]
    )
    is_active: bool = True


class DeliveryStatus(BaseModel):
    channel: NotificationChannel
    delivered: bool = True
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)


class DispatchReceipt(BaseModel):
    notification_id: str
    delivered_channels: List[DeliveryStatus] = Field(default_factory=list)
    buffered_by_quiet_hours: bool = False
