"""
Pheonix Subscription and Key Tracker Test Suite
Verifies subscription plan management, renewal countdowns, quota monitoring, and active keys listing.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import date
import pytest
from tracker.models import SubscriptionPlan, KeyQuotaStatus, ProviderRenewal
from tracker.core.plans import PlanRegistry
from tracker.core.renewal_engine import RenewalEngine
from tracker.core.key_monitor import KeyMonitor
from tracker.client import TrackerClient


class TestPlanRegistry:
    """Tests subscription plan catalog management."""

    def test_default_plans_loaded(self):
        registry = PlanRegistry()
        plans = registry.list_plans()
        providers = [p.provider for p in plans]

        assert "openai" in providers
        assert "anthropic" in providers
        assert "gemini" in providers
        assert "mistral" in providers

    def test_registers_custom_plan(self):
        registry = PlanRegistry()
        custom = SubscriptionPlan(
            plan_id="groq-enterprise",
            provider="groq",
            name="Groq Ultra LPU Tier",
            monthly_cost_usd=50.0,
            monthly_quota_usd=1000.0,
            renewal_day_of_month=5
        )
        registry.register_plan(custom)
        retrieved = registry.get_plan("groq")

        assert retrieved is not None
        assert retrieved.monthly_cost_usd == 50.0
        assert retrieved.renewal_day_of_month == 5


class TestRenewalEngine:
    """Tests renewal date and countdown calculations."""

    def test_calculates_renewal_within_same_month(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=25
        )
        ref_date = date(2026, 10, 20)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2026-10-25"
        assert renewal.days_remaining == 5
        assert renewal.status == "active"

    def test_calculates_renewal_rollover_to_next_month(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=5
        )
        ref_date = date(2026, 10, 20)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2026-11-05"
        assert renewal.days_remaining == 16

    def test_marks_due_soon_when_under_three_days(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=23
        )
        ref_date = date(2026, 10, 21)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.days_remaining == 2
        assert renewal.status == "due_soon"

    def test_handles_december_to_january_rollover(self):
        plan = SubscriptionPlan(
            plan_id="test-plan",
            provider="test",
            name="Test Plan",
            renewal_day_of_month=1
        )
        ref_date = date(2026, 12, 15)
        renewal = RenewalEngine.calculate_renewal(plan, reference_date=ref_date)

        assert renewal.next_renewal_date == "2027-01-01"
        assert renewal.days_remaining == 17


class TestKeyMonitor:
    """Tests key status and quota threshold alerting."""

    def test_normal_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-1", "openai", is_active=True, current_spend=50.0)
        assert status.quota_used_percent == 10.0
        assert status.alert_level == "normal"

    def test_warning_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-2", "openai", is_active=True, current_spend=360.0)
        assert status.quota_used_percent == 72.0
        assert status.alert_level == "warning"

    def test_critical_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-3", "openai", is_active=True, current_spend=440.0)
        assert status.quota_used_percent == 88.0
        assert status.alert_level == "critical"

    def test_exhausted_alert_level(self):
        monitor = KeyMonitor()
        status = monitor.register_key("key-4", "openai", is_active=True, current_spend=520.0)
        assert status.quota_used_percent == 104.0
        assert status.alert_level == "exhausted"


class TestTrackerVerificationGate:
    """Verification Gate: 'Done when: Renewals and active keys are listed'."""

    def test_renewals_and_active_keys_are_listed(self):
        client = TrackerClient()

        # 1. Active keys listing
        active_keys = client.list_active_keys()
        assert len(active_keys) >= 3
        for key in active_keys:
            assert key.is_active is True
            assert key.monthly_quota_usd > 0
            assert key.quota_used_percent >= 0

        # 2. Upcoming renewals listing
        renewals = client.list_upcoming_renewals(reference_date=date(2026, 10, 21))
        assert len(renewals) >= 4
        for r in renewals:
            assert r.days_remaining >= 0
            assert r.next_renewal_date is not None
            assert r.provider in ["openai", "anthropic", "gemini", "mistral"]

        # 3. Dashboard output includes both
        dashboard = client.render_dashboard(reference_date=date(2026, 10, 21))
        assert "Pheonix Subscription & Key Tracker Dashboard" in dashboard
        assert "Active Keys & Quota Consumption" in dashboard
        assert "Upcoming Subscription Renewals" in dashboard
        assert "openai" in dashboard
        assert "anthropic" in dashboard
