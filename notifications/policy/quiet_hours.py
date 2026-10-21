"""Quiet Hours Policy: Enforces user quiet periods, alert buffering, and emergency overrides."""

from datetime import datetime, timezone
from typing import Optional
from ..core.interfaces import BaseQuietHoursPolicy
from ..core.models import (
    NotificationItem,
    NotificationPriority,
    QuietHoursPolicy,
)


class QuietHoursEvaluator(BaseQuietHoursPolicy):
    """Calculates quiet hours windows and determines alert suppression eligibility."""

    def __init__(self, policy: Optional[QuietHoursPolicy] = None):
        self.policy = policy or QuietHoursPolicy()

    def is_in_quiet_hours(self, check_time: Optional[datetime] = None) -> bool:
        if not self.policy.enabled:
            return False

        t = check_time or datetime.now(timezone.utc)
        current_hour = (t.hour + int(self.policy.timezone_offset_hours)) % 24

        start = self.policy.start_hour
        end = self.policy.end_hour

        if start > end:
            # Overnights (e.g., 22:00 to 07:00)
            return current_hour >= start or current_hour < end
        else:
            # Same day window (e.g., 13:00 to 15:00)
            return start <= current_hour < end

    def should_suppress(
        self, item: NotificationItem, check_time: Optional[datetime] = None
    ) -> bool:
        if not self.is_in_quiet_hours(check_time):
            return False

        # Urgent / critical notifications bypass quiet hours if enabled
        if self.policy.bypass_for_urgent and item.priority == NotificationPriority.URGENT:
            return False

        return True
