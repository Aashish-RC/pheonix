"""Orchestrator Listener: Subscribes to orchestrator task completions and generates notifications."""

from typing import Optional
from ..core.interfaces import (
    BaseChannelDispatcher,
    BaseOrchestratorListener,
)
from ..core.models import (
    NotificationChannel,
    NotificationItem,
    NotificationPriority,
)
from ..channels.dispatcher import ChannelDispatcher


class OrchestratorListener(BaseOrchestratorListener):
    """Bridges orchestrator execution events to the user notification system."""

    def __init__(self, dispatcher: Optional[BaseChannelDispatcher] = None):
        self.dispatcher = dispatcher or ChannelDispatcher()

    def on_task_finished(
        self, task_id: str, task_name: str, status: str, summary: str
    ) -> NotificationItem:
        priority = (
            NotificationPriority.NORMAL
            if status == "success"
            else NotificationPriority.HIGH
        )
        title = f"Task Finished: {task_name} ({status.upper()})"
        body = f"Workflow '{task_name}' [{task_id}] completed with status '{status}'. {summary}"

        item = NotificationItem(
            title=title,
            body=body,
            priority=priority,
            task_id=task_id,
            sender="OrchestratorEngine",
            channels=[NotificationChannel.INBOX, NotificationChannel.DESKTOP],
            metadata={"status": status, "task_name": task_name},
        )

        self.dispatcher.dispatch(item)
        return item
