"""
Pheonix Usage & Cost Logger
Captures real-time model invocation events, calculates exact costs, and writes to SQLite ledger.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from ..models import UsageRecord
from .store import ObservabilityStore
from .reconciler import PricingReconciler


class UsageCostLogger:
    """
    Core logger ingesting telemetry from Model Gateway and Model Serving.
    """

    def __init__(self, store: Optional[ObservabilityStore] = None, daily_budget_usd: float = 25.0):
        self.store = store or ObservabilityStore()
        self.daily_budget_usd = daily_budget_usd

    def log(
        self,
        request_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float = 0.0,
        actor: str = "anonymous",
        cached: bool = False,
        status_code: int = 200,
        explicit_cost: Optional[float] = None
    ) -> UsageRecord:
        """
        Records an inference event into the append-only ledger.
        """
        if explicit_cost is not None:
            cost_usd = round(explicit_cost, 6)
        else:
            cost_usd = PricingReconciler.calculate_cost(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                is_cached=cached
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        record = UsageRecord(
            record_id=f"rec-{uuid.uuid4().hex[:12]}",
            request_id=request_id,
            timestamp=now_iso,
            actor=actor,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            cached=cached,
            status_code=status_code
        )

        self.store.insert_record(record)
        return record
