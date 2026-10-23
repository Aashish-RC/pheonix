"""
Pheonix Vault Data Models and Invariants
"""

from typing import Optional, List, Dict
import time
from pydantic import BaseModel, Field


class SecretMetadata(BaseModel):
    key_id: str
    provider: str = "custom"
    tenant_id: str = "default"
    user_id: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    revoked: bool = False
    revoked_at: Optional[float] = None
    revocation_reason: Optional[str] = None


class SecretRecord(BaseModel):
    metadata: SecretMetadata
    encrypted_value: str  # Base64-encoded encrypted value (or payload-level entry)


class AuditEntry(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    action: str  # e.g., "INIT", "PUT", "GET", "REVOKE", "ROTATE"
    key_id: Optional[str] = None
    tenant_id: str = "default"
    user_id: Optional[str] = None
    role: str = "user"
    success: bool = True
    details: Optional[str] = None
