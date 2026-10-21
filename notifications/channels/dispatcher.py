"""Channel Dispatcher: Routes notifications across inbox, desktop badges, and webhook channels."""

from typing import List, Optional
from ..core.interfaces import (
    BaseChannelDispatcher,
    BaseInboxStore,
    BaseQuietHoursPolicy,
)
from ..core.models import (
    DeliveryStatus,
    DispatchReceipt,
    NotificationChannel,
    NotificationItem,
)
from ..policy.quiet_hours import QuietHoursEvaluator
from ..storage.inbox_store import InboxStore


class ChannelDispatcher(BaseChannelDispatcher):
    """Coordinates notification delivery across configured targets respecting quiet hours."""

    def __init__(
        self,
        inbox_store: Optional[BaseInboxStore] = None,
        quiet_hours: Optional[BaseQuietHoursPolicy] = None,
    ):
        self.inbox_store = inbox_store or InboxStore()
        self.quiet_hours = quiet_hours or QuietHoursEvaluator()

    def dispatch(self, item: NotificationItem) -> DispatchReceipt:
        # Always persist to inbox for history and audit
        self.inbox_store.save_notification(item)

        suppressed = self.quiet_hours.should_suppress(item)
        statuses: List[DeliveryStatus] = []

        for ch in item.channels:
            if ch == NotificationChannel.INBOX:
                # Inbox is always delivered
                statuses.append(DeliveryStatus(channel=ch, delivered=True))
            elif suppressed:
                # Suppressed by quiet hours for external / loud channels
                statuses.append(
                    DeliveryStatus(
                        channel=ch,
                        delivered=False,
                        error="Suppressed by active Quiet Hours policy",
                    )
                )
            else:
                # Normal delivery to external/desktop channel
                statuses.append(DeliveryStatus(channel=ch, delivered=True))

        return DispatchReceipt(
            notification_id=item.notification_id,
            delivered_channels=statuses,
            buffered_by_quiet_hours=suppressed,
        )
