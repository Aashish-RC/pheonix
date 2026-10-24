"""
Pheonix Observability Data Models
Defines schema for usage records, exact pricing structures, and personal usage views.
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class UsageRecord(BaseModel):
    """Immutable ledger record representing a single model invocation."""
    record_id: str
    request_id: str
    tenant_id: str = "default"
    timestamp: str
    actor: str = "anonymous"
    model: str
    provider: str
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    cached: bool = False
    status_code: int = 200


class ModelPricing(BaseModel):
    """Official published billing rate per million tokens for exact reconciliation."""
    model: str
    provider: str
    prompt_per_million: float
    completion_per_million: float


class ModelBreakdown(BaseModel):
    """Aggregated usage and cost metrics for a specific model."""
    model: str
    provider: str
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class PersonalUsageView(BaseModel):
    """Personalized consumption and expenditure summary for the developer/user."""
    tenant_id: str = "default"
    time_window: str = "all-time"
    total_requests: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    cached_requests: int = 0
    estimated_savings_usd: float = 0.0
    avg_latency_ms: float = 0.0
    breakdown_by_model: List[ModelBreakdown] = Field(default_factory=list)
    breakdown_by_provider: Dict[str, float] = Field(default_factory=dict)
