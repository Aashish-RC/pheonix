"""End-to-End Tests for Notifications: Verifies that a finished task notifies you."""

import pytest
from notifications.core.models import (
    NotificationChannel,
    NotificationPriority,
)
from notifications.channels.dispatcher import ChannelDispatcher
from notifications.listener.orchestrator_listener import OrchestratorListener
from notifications.storage.inbox_store import InboxStore


def test_finished_task_notifies_you():
    """Core Done When Criteria: A finished task notifies you."""
    inbox = InboxStore()
    dispatcher = ChannelDispatcher(inbox_store=inbox)
    listener = OrchestratorListener(dispatcher=dispatcher)

    # Initial state: 0 notifications in inbox
    assert inbox.get_unread_count() == 0

    # Step 1: Orchestrator completes a parallel multi-step workflow task
    task_id = "task_orch_98765"
    task_name = "Automated PR Security & Quality Pipeline"
    task_status = "success"
    task_summary = "All 5 workflow steps passed across 2 parallel barriers with zero errors."

    # Step 2: Trigger task finished event
    notification = listener.on_task_finished(
        task_id=task_id,
        task_name=task_name,
        status=task_status,
        summary=task_summary,
    )

    # Step 3: Verify notification delivery into inbox
    assert notification is not None
    assert notification.task_id == task_id
    assert notification.priority == NotificationPriority.NORMAL
    assert "Task Finished" in notification.title
    assert "All 5 workflow steps passed" in notification.body

    # Step 4: Verify user inbox receives the alert
    assert inbox.get_unread_count() == 1
    stored_items = inbox.list_notifications()
    assert len(stored_items) == 1
    assert stored_items[0].notification_id == notification.notification_id
    assert stored_items[0].is_read is False

    # Step 5: User opens and marks notification as read
    inbox.mark_as_read(notification.notification_id)
    assert inbox.get_unread_count() == 0
