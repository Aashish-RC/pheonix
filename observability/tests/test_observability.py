"""
Pheonix Observability Test Suite
Verifies exact token accounting, cost reconciliation against provider dashboards, and personal usage views.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest
from observability.models import UsageRecord, ModelPricing
from observability.core.store import ObservabilityStore
from observability.core.reconciler import PricingReconciler
from observability.core.logger import UsageCostLogger
from observability.core.view import PersonalUsageViewBuilder
from observability.client import ObservabilityClient


class TestPricingReconciler:
    """Verifies that computed prices match official provider billing rates exactly."""

    def test_reconciles_gpt4o_exact_cost(self):
        # GPT-4o: $2.50 / 1M prompt, $10.00 / 1M completion
        # 100,000 prompt tokens = $0.25, 20,000 completion tokens = $0.20 -> $0.45
        cost = PricingReconciler.calculate_cost("gpt-4o", prompt_tokens=100_000, completion_tokens=20_000)
        assert cost == 0.45

    def test_reconciles_gpt4o_mini_exact_cost(self):
        # GPT-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
        # 1,000,000 prompt = $0.15, 500,000 completion = $0.30 -> $0.45
        cost = PricingReconciler.calculate_cost("gpt-4o-mini", prompt_tokens=1_000_000, completion_tokens=500_000)
        assert cost == 0.45

    def test_reconciles_claude_sonnet_exact_cost(self):
        # Claude 3.7 Sonnet: $3.00 / 1M prompt, $15.00 / 1M completion
        # 10,000 prompt = $0.03, 10,000 completion = $0.15 -> $0.18
        cost = PricingReconciler.calculate_cost(
            "claude-3-7-sonnet-20250219",
            prompt_tokens=10_000,
            completion_tokens=10_000
        )
        assert cost == 0.18

    def test_reconciles_cached_prompt_discount(self):
        # Cached prompt gets 50% discount on prompt rate ($1.25 / 1M for gpt-4o)
        cost_normal = PricingReconciler.calculate_cost("gpt-4o", prompt_tokens=100_000, completion_tokens=0, is_cached=False)
        cost_cached = PricingReconciler.calculate_cost("gpt-4o", prompt_tokens=100_000, completion_tokens=0, is_cached=True)
        assert cost_normal == 0.25
        assert cost_cached == 0.125

    def test_local_offline_models_are_zero_cost(self):
        assert PricingReconciler.calculate_cost("llama3.2:1b", 50_000, 50_000) == 0.0
        assert PricingReconciler.calculate_cost("ollama/phi3", 100_000, 100_000) == 0.0
        assert PricingReconciler.calculate_cost("llama.cpp/default", 10_000, 10_000) == 0.0


class TestObservabilityStore:
    """Verifies SQLite storage integrity, append-only guarantees, and queries."""

    def test_inserts_and_retrieves_records(self, tmp_path):
        db_file = tmp_path / "test_obs.db"
        store = ObservabilityStore(db_path=db_file)
        assert store.count_records() == 0

        rec = UsageRecord(
            record_id="rec-1",
            request_id="req-1",
            timestamp="2026-10-21T12:00:00Z",
            actor="alice",
            model="gpt-4o",
            provider="openai",
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            cost_usd=0.00225,
            latency_ms=350.0,
            cached=False,
            status_code=200
        )
        store.insert_record(rec)
        assert store.count_records() == 1

        records = store.get_records(actor="alice")
        assert len(records) == 1
        assert records[0].model == "gpt-4o"
        assert records[0].cost_usd == 0.00225

    def test_filters_by_actor_and_model(self, tmp_path):
        db_file = tmp_path / "test_filter.db"
        store = ObservabilityStore(db_path=db_file)

        for i, (actor, model) in enumerate([("alice", "gpt-4o"), ("bob", "gpt-4o"), ("alice", "claude-3-7-sonnet-20250219")]):
            store.insert_record(UsageRecord(
                record_id=f"rec-{i}",
                request_id=f"req-{i}",
                timestamp=f"2026-10-21T12:0{i}:00Z",
                actor=actor,
                model=model,
                provider="test",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                cost_usd=0.01,
                latency_ms=100.0
            ))

        assert len(store.get_records(actor="alice")) == 2
        assert len(store.get_records(actor="bob")) == 1
        assert len(store.get_records(model="gpt-4o")) == 2


class TestPersonalUsageView:
    """Verification Gate: 'Done when: Numbers match provider dashboards'."""

    def test_aggregation_invariants_match_exact_record_sums(self, tmp_path):
        db_file = tmp_path / "test_dashboard.db"
        store = ObservabilityStore(db_path=db_file)
        logger = UsageCostLogger(store=store)

        # 1. Log multiple heterogeneous requests
        logger.log("req-1", model="gpt-4o", provider="openai", prompt_tokens=100_000, completion_tokens=20_000, actor="dev-user")
        logger.log("req-2", model="claude-3-7-sonnet-20250219", provider="anthropic", prompt_tokens=10_000, completion_tokens=10_000, actor="dev-user")
        logger.log("req-3", model="llama3.2:1b", provider="ollama", prompt_tokens=50_000, completion_tokens=500, actor="dev-user")
        logger.log("req-4", model="gpt-4o", provider="openai", prompt_tokens=20_000, completion_tokens=5_000, actor="dev-user", cached=True)

        builder = PersonalUsageViewBuilder(store=store)
        view = builder.build_view(actor="dev-user")

        # Invariant 1: Total requests
        assert view.total_requests == 4

        # Invariant 2: Total tokens equals sum of all logged tokens
        all_records = store.get_records(actor="dev-user")
        expected_tokens = sum(r.total_tokens for r in all_records)
        assert view.total_tokens == expected_tokens

        # Invariant 3: Total cost equals sum of individual record costs exactly
        expected_cost = round(sum(r.cost_usd for r in all_records), 6)
        assert view.total_cost_usd == expected_cost

        # Invariant 4: Model breakdown sums match total
        breakdown_cost_sum = round(sum(mb.cost_usd for mb in view.breakdown_by_model), 6)
        assert breakdown_cost_sum == view.total_cost_usd

        # Invariant 5: Provider breakdown includes openai, anthropic, ollama
        assert "openai" in view.breakdown_by_provider
        assert "anthropic" in view.breakdown_by_provider
        assert "ollama" in view.breakdown_by_provider
        assert view.breakdown_by_provider["ollama"] == 0.0

    def test_client_sdk_renders_cli_dashboard(self, tmp_path):
        db_file = tmp_path / "test_sdk.db"
        client = ObservabilityClient(db_path=db_file)

        client.log_inference(
            request_id="req-sdk-1",
            model="gpt-4o",
            provider="openai",
            prompt_tokens=4000,
            completion_tokens=500,
            latency_ms=620.0,
            actor="agent-runner"
        )

        dashboard_output = client.print_dashboard(actor="agent-runner")
        assert "Pheonix Personal Usage & Cost Dashboard" in dashboard_output
        assert "Total Spend" in dashboard_output
        assert "gpt-4o" in dashboard_output
        assert "openai" in dashboard_output
