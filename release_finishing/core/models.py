"""
Data models for Release Finishing, Update Channels, and System Diagnostics.
"""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ReleaseChannel(str, Enum):
    ALPHA = "alpha"
    BETA = "beta"
    STABLE = "stable"


class ReleaseStatus(str, Enum):
    DRAFT = "draft"
    STAGED = "staged"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"


class ReleasePackage(BaseModel):
    release_id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:10]}")
    tenant_id: str = "default"
    version: str
    channel: ReleaseChannel = ReleaseChannel.STABLE
    status: ReleaseStatus = ReleaseStatus.STAGED
    sha256_bundle_checksum: str
    component_manifests: Dict[str, str] = Field(default_factory=dict)
    changelog: List[str] = Field(default_factory=list)
    canary_percentage: int = 100  # 0 to 100
    created_at: float = Field(default_factory=time.time)


class RolloutRule(BaseModel):
    channel: ReleaseChannel
    min_health_score: float = 0.95
    required_canary_duration_seconds: float = 0.0


class DiagnosticCheckResult(BaseModel):
    component: str
    healthy: bool
    latency_ms: float = 0.0
    message: str = "OK"


class SystemHealthReport(BaseModel):
    overall_healthy: bool
    health_score: float
    tenant_id: str = "default"
    checks: List[DiagnosticCheckResult] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)
