"""Tests for ChannelDispatcher."""

from datetime import datetime, timezone
import pytest
from notifications.core.models import (
    NotificationChannel,
    NotificationItem,
    NotificationPriority,
    QuietHoursPolicy,
)
from notifications.policy.quiet_hours import QuietHoursEvaluator
from notifications.storage.inbox_store import InboxStore
from notifications.channels.dispatcher import ChannelDispatcher


def test_channel_dispatcher_nominal():
    store = InboxStore()
    quiet = QuietHoursEvaluator(QuietHoursPolicy(enabled=False))
    dispatcher = ChannelDispatcher(inbox_store=store, quiet_hours=quiet)

    item = NotificationItem(
        title="Deploy Success",
        body="Build #42 deployed cleanly",
        channels=[NotificationChannel.INBOX, NotificationChannel.DESKTOP, NotificationChannel.WEBHOOK],
    )

    receipt = dispatcher.dispatch(item)
    assert receipt.buffered_by_quiet_hours is False
    assert len(receipt.delivered_channels) == 3
    assert all(st.delivered for st in receipt.delivered_channels)

    # Inbox store contains the item
    assert store.get_notification(item.notification_id) is not None


def test_channel_dispatcher_buffered_during_quiet_hours(monkeypatch):
    store = InboxStore()
    quiet_policy = QuietHoursPolicy(enabled=True, start_hour=22, end_hour=7)
    quiet = QuietHoursEvaluator(quiet_policy)
    dispatcher = ChannelDispatcher(inbox_store=store, quiet_hours=quiet)

    # Mock datetime to 3 AM UTC
    fixed_time = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(quiet, "should_suppress", lambda item: True)

    item = NotificationItem(
        title="Nightly Summary",
        body="All systems nominal",
        priority=NotificationPriority.LOW,
        channels=[NotificationChannel.INBOX, NotificationChannel.DESKTOP],
    )

    receipt = dispatcher.dispatch(item)
    assert receipt.buffered_by_quiet_hours is True

    # Inbox delivered, Desktop suppressed
    inbox_status = next(st for st in receipt.delivered_channels if st.channel == NotificationChannel.INBOX)
    desktop_status = next(st for st in receipt.delivered_channels if st.channel == NotificationChannel.DESKTOP)

    assert inbox_status.delivered is True
    assert desktop_status.delivered is False
    assert "Suppressed" in (desktop_status.error or "")
