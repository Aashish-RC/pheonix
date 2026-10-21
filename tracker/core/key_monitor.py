"""
Pheonix Key Status & Quota Monitor
Tracks active provider keys, monitors spend against monthly quotas, and triggers alerts.
"""

from typing import Dict, List, Optional
from ..models import KeyQuotaStatus, AlertLevel, SubscriptionPlan
from .plans import PlanRegistry


class KeyMonitor:
    """Tracks active provider credentials, quota limits, and usage percentages."""

    def __init__(self, plan_registry: Optional[PlanRegistry] = None):
        self.plans = plan_registry or PlanRegistry()
        self._key_records: Dict[str, KeyQuotaStatus] = {}
        self._init_mock_keys()

    def _init_mock_keys(self) -> None:
        """Initializes default tracked provider keys."""
        default_keys = [
            ("key-openai-prod", "openai", True, 84.50),
            ("key-anthropic-prod", "anthropic", True, 195.00),
            ("key-gemini-prod", "gemini", True, 45.00),
            ("key-mistral-backup", "mistral", False, 0.00),
        ]
        for key_id, provider, active, spend in default_keys:
            self.register_key(key_id=key_id, provider=provider, is_active=active, current_spend=spend)

    def register_key(
        self,
        key_id: str,
        provider: str,
        is_active: bool = True,
        current_spend: float = 0.0
    ) -> KeyQuotaStatus:
        plan = self.plans.get_plan(provider)
        quota = plan.monthly_quota_usd if plan else 100.0
        used_percent = round((current_spend / quota) * 100.0, 1) if quota > 0 else 0.0

        alert: AlertLevel = "normal"
        if used_percent >= 100.0:
            alert = "exhausted"
        elif used_percent >= 85.0:
            alert = "critical"
        elif used_percent >= 70.0:
            alert = "warning"

        status = KeyQuotaStatus(
            key_id=key_id,
            provider=provider,
            is_active=is_active,
            current_spend_usd=current_spend,
            monthly_quota_usd=quota,
            quota_used_percent=used_percent,
            alert_level=alert
        )
        self._key_records[key_id] = status
        return status

    def get_key_status(self, key_id: str) -> Optional[KeyQuotaStatus]:
        return self._key_records.get(key_id)

    def list_keys(self, provider: Optional[str] = None, only_active: bool = False) -> List[KeyQuotaStatus]:
        keys = list(self._key_records.values())
        if provider:
            keys = [k for k in keys if k.provider.lower() == provider.lower()]
        if only_active:
            keys = [k for k in keys if k.is_active]
        return keys
