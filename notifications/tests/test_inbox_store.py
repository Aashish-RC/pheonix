"""Tests for InboxStore."""

import pytest
from notifications.core.models import (
    NotificationChannel,
    NotificationItem,
    NotificationPriority,
)
from notifications.storage.inbox_store import InboxStore


@pytest.fixture
def store():
    return InboxStore()


def test_inbox_store_crud(store):
    item1 = NotificationItem(
        title="Alert 1",
        body="First message",
        channels=[NotificationChannel.INBOX, NotificationChannel.DESKTOP],
    )
    item2 = NotificationItem(
        title="Alert 2",
        body="Second message",
        priority=NotificationPriority.HIGH,
        channels=[NotificationChannel.INBOX],
    )

    store.save_notification(item1)
    store.save_notification(item2)

    assert store.get_unread_count() == 2

    # Query all
    all_items = store.list_notifications()
    assert len(all_items) == 2

    # Query desktop channel only
    desktop_items = store.list_notifications(channel=NotificationChannel.DESKTOP)
    assert len(desktop_items) == 1
    assert desktop_items[0].title == "Alert 1"

    # Mark item1 as read
    marked = store.mark_as_read(item1.notification_id)
    assert marked is True
    assert store.get_unread_count() == 1

    unread_items = store.list_notifications(unread_only=True)
    assert len(unread_items) == 1
    assert unread_items[0].notification_id == item2.notification_id

    # Delete item2
    deleted = store.delete_notification(item2.notification_id)
    assert deleted is True
    assert store.get_notification(item2.notification_id) is None
