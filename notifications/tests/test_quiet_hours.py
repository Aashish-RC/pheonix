"""Tests for QuietHoursEvaluator."""

from datetime import datetime, timezone
import pytest
from notifications.core.models import (
    NotificationItem,
    NotificationPriority,
    QuietHoursPolicy,
)
from notifications.policy.quiet_hours import QuietHoursEvaluator


def test_quiet_hours_disabled():
    policy = QuietHoursPolicy(enabled=False, start_hour=22, end_hour=7)
    evaluator = QuietHoursEvaluator(policy)
    item = NotificationItem(title="Test", body="Msg", priority=NotificationPriority.NORMAL)

    # 2 AM UTC
    t_night = datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)
    assert evaluator.is_in_quiet_hours(t_night) is False
    assert evaluator.should_suppress(item, t_night) is False


def test_quiet_hours_overnight_suppression():
    policy = QuietHoursPolicy(enabled=True, start_hour=22, end_hour=7, bypass_for_urgent=True)
    evaluator = QuietHoursEvaluator(policy)

    # 3 AM UTC (within quiet hours: 22 to 7)
    t_night = datetime(2026, 10, 21, 3, 0, tzinfo=timezone.utc)
    assert evaluator.is_in_quiet_hours(t_night) is True

    # Normal notification should be suppressed
    normal_item = NotificationItem(title="Normal", body="Normal alert", priority=NotificationPriority.NORMAL)
    assert evaluator.should_suppress(normal_item, t_night) is True

    # Urgent notification should NOT be suppressed
    urgent_item = NotificationItem(title="Emergency", body="Critical alert", priority=NotificationPriority.URGENT)
    assert evaluator.should_suppress(urgent_item, t_night) is False


def test_quiet_hours_daytime_active():
    policy = QuietHoursPolicy(enabled=True, start_hour=22, end_hour=7)
    evaluator = QuietHoursEvaluator(policy)

    # 14:00 (2 PM UTC) - daytime outside quiet hours
    t_day = datetime(2026, 10, 21, 14, 0, tzinfo=timezone.utc)
    assert evaluator.is_in_quiet_hours(t_day) is False

    normal_item = NotificationItem(title="Normal", body="Normal alert", priority=NotificationPriority.NORMAL)
    assert evaluator.should_suppress(normal_item, t_day) is False
