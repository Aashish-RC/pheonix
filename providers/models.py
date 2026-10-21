"""
Pheonix Provider Activation Models & Types
"""

import time
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ProviderStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"
    REVOKED = "revoked"
    UNTESTED = "untested"


class AuthType(str, Enum):
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    LOCAL_ENDPOINT = "local_endpoint"


class ProviderDescriptor(BaseModel):
    provider_id: str
    name: str
    auth_type: AuthType = AuthType.API_KEY
    probe_url: str
    header_name: str = "Authorization"
    header_format: str = "Bearer {token}"
    models: List[str] = Field(default_factory=list)
    is_local: bool = False


class PingResult(BaseModel):
    success: bool
    latency_ms: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class ActivatedProvider(BaseModel):
    provider_id: str
    name: str
    key_id: str
    status: ProviderStatus = ProviderStatus.UNTESTED
    auth_type: AuthType = AuthType.API_KEY
    last_ping_at: Optional[float] = None
    last_latency_ms: Optional[float] = None
    activated_at: float = Field(default_factory=time.time)
    revocation_reason: Optional[str] = None
