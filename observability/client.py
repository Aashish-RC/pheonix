"""
Pheonix Observability Client SDK
Provides high-level APIs for applications and agents to record usage and view cost dashboards.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from .models import UsageRecord, PersonalUsageView
from .core.store import ObservabilityStore
from .core.logger import UsageCostLogger
from .core.view import PersonalUsageViewBuilder


class ObservabilityClient:
    """
    Client for interacting with Pheonix Observability and Cost Accounting.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.store = ObservabilityStore(db_path=db_path)
        self.logger = UsageCostLogger(store=self.store)
        self.view_builder = PersonalUsageViewBuilder(store=self.store)

    def log_inference(
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
        """Logs a single model execution and returns the persisted record."""
        return self.logger.log(
            request_id=request_id,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            actor=actor,
            cached=cached,
            status_code=status_code,
            explicit_cost=explicit_cost
        )

    def get_personal_view(
        self,
        actor: Optional[str] = None,
        since_timestamp: Optional[str] = None
    ) -> PersonalUsageView:
        """Retrieves structured personal usage and spend metrics."""
        return self.view_builder.build_view(actor=actor, since_timestamp=since_timestamp)

    def print_dashboard(self, actor: Optional[str] = None) -> str:
        """Renders and returns formatted ASCII personal dashboard."""
        view = self.get_personal_view(actor=actor)
        return self.view_builder.render_cli_dashboard(view)
