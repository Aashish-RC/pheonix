"""
Pheonix Auth & Identity Package
"""

from .core.manager import (
    AuthManager,
    AuthenticationError,
    SessionInvalidError,
)
from .models import (
    UserRecord,
    DeviceInfo,
    SessionToken,
    SessionInfo,
)
from .core.password import hash_password, verify_password
from .core.session import create_session_token, verify_session_token
from .core.device import compute_device_fingerprint, DeviceRegistry

__all__ = [
    "AuthManager",
    "AuthenticationError",
    "SessionInvalidError",
    "UserRecord",
    "DeviceInfo",
    "SessionToken",
    "SessionInfo",
    "hash_password",
    "verify_password",
    "create_session_token",
    "verify_session_token",
    "compute_device_fingerprint",
    "DeviceRegistry",
]
