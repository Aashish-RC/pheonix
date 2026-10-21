"""
Pheonix Auth & Identity Data Models
"""

import time
from typing import Optional, List
from pydantic import BaseModel, Field


class UserRecord(BaseModel):
    user_id: str
    username: str
    password_hash: str
    salt: str
    created_at: float = Field(default_factory=time.time)
    last_login_at: Optional[float] = None


class DeviceInfo(BaseModel):
    device_id: str
    device_name: str
    platform: str
    fingerprint: str
    first_seen_at: float = Field(default_factory=time.time)
    last_active_at: float = Field(default_factory=time.time)
    is_trusted: bool = True
    is_revoked: bool = False
    revocation_reason: Optional[str] = None


class SessionToken(BaseModel):
    token_string: str
    session_id: str
    user_id: str
    device_id: str
    issued_at: float
    expires_at: float


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    device_id: str
    device_name: str
    platform: str
    issued_at: float
    expires_at: float
    is_active: bool
