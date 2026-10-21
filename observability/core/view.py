"""
Pheonix Personal Usage View
Aggregates ledger records into a personal developer dashboard showing consumption, costs, and breakdown.
"""

from collections import defaultdict
from typing import List, Optional
from ..models import UsageRecord, ModelBreakdown, PersonalUsageView
from .store import ObservabilityStore


class PersonalUsageViewBuilder:
    """
    Builds structured personal usage and cost views from the ledger.
    """

    def __init__(self, store: ObservabilityStore):
        self.store = store

    def build_view(self, actor: Optional[str] = None, since_timestamp: Optional[str] = None) -> PersonalUsageView:
        records: List[UsageRecord] = self.store.get_records(actor=actor, since_timestamp=since_timestamp)

        if not records:
            return PersonalUsageView(time_window="all-time" if not since_timestamp else f"since {since_timestamp}")

        total_requests = len(records)
        total_tokens = sum(r.total_tokens for r in records)
        total_cost = round(sum(r.cost_usd for r in records), 6)
        cached_count = sum(1 for r in records if r.cached)
        avg_latency = round(sum(r.latency_ms for r in records) / total_requests, 2)

        # Estimated savings from cached responses (full cost avoided)
        estimated_savings = round(sum(r.cost_usd for r in records if r.cached), 6)

        # Aggregation by model
        model_groups = defaultdict(lambda: {
            "provider": "",
            "count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0
        })

        provider_costs = defaultdict(float)

        for r in records:
            m = model_groups[r.model]
            m["provider"] = r.provider
            m["count"] += 1
            m["prompt_tokens"] += r.prompt_tokens
            m["completion_tokens"] += r.completion_tokens
            m["total_tokens"] += r.total_tokens
            m["cost_usd"] += r.cost_usd

            provider_costs[r.provider] += r.cost_usd

        breakdown_by_model = [
            ModelBreakdown(
                model=model_name,
                provider=data["provider"],
                request_count=data["count"],
                prompt_tokens=data["prompt_tokens"],
                completion_tokens=data["completion_tokens"],
                total_tokens=data["total_tokens"],
                cost_usd=round(data["cost_usd"], 6)
            )
            for model_name, data in model_groups.items()
        ]

        breakdown_by_provider = {
            prov: round(cost, 6) for prov, cost in provider_costs.items()
        }

        return PersonalUsageView(
            time_window="all-time" if not since_timestamp else f"since {since_timestamp}",
            total_requests=total_requests,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            cached_requests=cached_count,
            estimated_savings_usd=estimated_savings,
            avg_latency_ms=avg_latency,
            breakdown_by_model=breakdown_by_model,
            breakdown_by_provider=breakdown_by_provider
        )

    def render_cli_dashboard(self, view: PersonalUsageView) -> str:
        """Renders a formatted text dashboard suitable for console viewing."""
        lines = [
            "============================================================",
            f"  Pheonix Personal Usage & Cost Dashboard ({view.time_window})",
            "============================================================",
            f"Total Requests  : {view.total_requests}",
            f"Total Tokens    : {view.total_tokens:,}",
            f"Total Spend     : ${view.total_cost_usd:.4f} USD",
            f"Cached Requests : {view.cached_requests} (Saved ~${view.estimated_savings_usd:.4f})",
            f"Average Latency : {view.avg_latency_ms:.1f} ms",
            "------------------------------------------------------------",
            "Provider Breakdown:",
        ]
        for prov, cost in view.breakdown_by_provider.items():
            lines.append(f"  - {prov:<15}: ${cost:.4f}")

        lines.append("------------------------------------------------------------")
        lines.append("Model Breakdown:")
        for mb in view.breakdown_by_model:
            lines.append(
                f"  - {mb.model:<24} | Req: {mb.request_count:>3} | Tokens: {mb.total_tokens:>8,} | Cost: ${mb.cost_usd:.4f}"
            )
        lines.append("============================================================")
        return "\n".join(lines)
