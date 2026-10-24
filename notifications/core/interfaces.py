"""Abstract interfaces for Pheonix Notifications components."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from .models import (
    DispatchReceipt,
    NotificationChannel,
    NotificationItem,
)


class BaseInboxStore(ABC):
    """Interface for managing the persistent notification inbox."""

    @abstractmethod
    def save_notification(self, item: NotificationItem) -> None:
        pass

    @abstractmethod
    def get_notification(self, notification_id: str) -> Optional[NotificationItem]:
        pass

    @abstractmethod
    def list_notifications(
        self,
        channel: Optional[NotificationChannel] = None,
        unread_only: bool = False,
        limit: int = 50,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[NotificationItem]:
        pass

    @abstractmethod
    def mark_as_read(self, notification_id: str) -> bool:
        pass

    @abstractmethod
    def delete_notification(self, notification_id: str) -> bool:
        pass

    @abstractmethod
    def get_unread_count(self) -> int:
        pass


class BaseQuietHoursPolicy(ABC):
    """Interface for evaluating quiet hours and suppression rules."""

    @abstractmethod
    def is_in_quiet_hours(self, check_time: Optional[datetime] = None) -> bool:
        pass

    @abstractmethod
    def should_suppress(
        self, item: NotificationItem, check_time: Optional[datetime] = None
    ) -> bool:
        pass


class BaseChannelDispatcher(ABC):
    """Interface for dispatching notifications to delivery channels."""

    @abstractmethod
    def dispatch(self, item: NotificationItem) -> DispatchReceipt:
        pass


class BaseOrchestratorListener(ABC):
    """Interface for listening to task completions and alerting the user."""

    @abstractmethod
    def on_task_finished(
        self, task_id: str, task_name: str, status: str, summary: str
    ) -> NotificationItem:
        pass
