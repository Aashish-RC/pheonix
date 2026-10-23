"""
Pheonix AuthManager
Coordinates single-user local authentication, session tokens, and device registry.
"""

import os
import uuid
import time
from typing import Optional, List, Dict, Any
from pathlib import Path

from ..models import UserRecord, DeviceInfo, SessionToken, SessionInfo
from .password import hash_password, verify_password
from .session import (
    create_session_token,
    verify_session_token,
    create_session_token_with_vault,
    verify_session_token_with_vault,
)
from .device import DeviceRegistry


class AuthenticationError(Exception):
    """Raised when authentication fails due to invalid credentials."""
    pass


class SessionInvalidError(Exception):
    """Raised when a session token is invalid, expired, or revoked."""
    pass


class AuthManager:
    """
    Manages single-user local authentication, cryptographic session lifecycle,
    and registered device management.
    Supports Vault key-lease backend for zero-plaintext key storage.
    """

    def __init__(
        self,
        signing_key: bytes = None,
        vault_manager: Any = None,
        vault_key_id: str = "auth_session_signing_key",
    ):
        self._vault_manager = vault_manager
        self._vault_key_id = vault_key_id

        if self._vault_manager:
            if not self._vault_manager.has_secret(vault_key_id):
                key_bytes = signing_key or os.urandom(32)
                self._vault_manager.put_secret(
                    key_id=vault_key_id,
                    secret=key_bytes.hex(),
                    provider="auth_session",
                    description="Session token HMAC signing key",
                )
            self._signing_key = None
        else:
            self._signing_key = signing_key or os.urandom(32)

        self.device_registry = DeviceRegistry()
        self._user: Optional[UserRecord] = None
        self.max_concurrent_sessions: int = 5
        # session_id -> { "session_id", "user_id", "device_id", "issued_at", "expires_at", "is_active" }
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def is_user_registered(self) -> bool:
        return self._user is not None

    def register_initial_user(
        self,
        username: str,
        password: str,
        tenant_id: str = "default",
        role: str = "owner",
    ) -> UserRecord:
        """Register the primary local owner/user."""
        if self._user is not None:
            raise ValueError("Single-user model: User already registered. Reset required to register new owner.")

        pwd_hash, salt = hash_password(password)
        user = UserRecord(
            user_id=f"usr_{uuid.uuid4().hex[:12]}",
            username=username,
            password_hash=pwd_hash,
            salt=salt,
            tenant_id=tenant_id,
            role=role,
            created_at=time.time(),
        )
        self._user = user
        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="auth",
                action="user_registered",
                tenant_id=tenant_id,
                user_id=user.user_id,
                role=role,
                resource=username,
                status="success",
                details={"username": username},
            )
        except Exception:
            pass
        return user

    def authenticate(
        self,
        username: str,
        password: str,
        device_id: str,
        device_name: str = "Local Device",
        platform: str = "desktop",
        ttl_seconds: float = 86400.0,
    ) -> SessionToken:
        """
        Authenticate user with password and bind session to device.
        Done when: You can sign in and see your devices.
        """
        if not self._user:
            raise AuthenticationError("No user registered in system.")

        if username != self._user.username:
            raise AuthenticationError("Invalid username or password.")

        if not verify_password(password, self._user.password_hash, self._user.salt):
            raise AuthenticationError("Invalid username or password.")

        if self.device_registry.is_device_blacklisted(device_id):
            raise AuthenticationError(f"Device '{device_id}' has been blacklisted.")

        # Register or update device
        device = self.device_registry.register_or_update(
            device_id=device_id,
            device_name=device_name,
            platform=platform,
            is_trusted=True,
        )

        if device.is_revoked:
            raise AuthenticationError(f"Device '{device_id}' has been revoked: {device.revocation_reason}")

        # Enforce concurrent session limit (max 5 sessions per user)
        now = time.time()
        user_active = [
            s for s in self._sessions.values()
            if s["user_id"] == self._user.user_id and s.get("is_active", False) and s.get("expires_at", 0) > now
        ]
        if len(user_active) >= self.max_concurrent_sessions:
            user_active.sort(key=lambda s: s.get("issued_at", 0))
            oldest = user_active[0]
            oldest["is_active"] = False

        # Issue signed cryptographic session token
        session_id = f"sess_{uuid.uuid4().hex[:16]}"
        tenant_id = getattr(self._user, "tenant_id", "default")
        role = getattr(self._user, "role", "user")

        if self._vault_manager:
            token_str, iat, exp = create_session_token_with_vault(
                session_id=session_id,
                user_id=self._user.user_id,
                device_id=device_id,
                ttl_seconds=ttl_seconds,
                vault_manager=self._vault_manager,
                key_id=self._vault_key_id,
                tenant_id=tenant_id,
                role=role,
            )
        else:
            token_str, iat, exp = create_session_token(
                session_id=session_id,
                user_id=self._user.user_id,
                device_id=device_id,
                ttl_seconds=ttl_seconds,
                signing_key=self._signing_key,
                tenant_id=tenant_id,
                role=role,
            )

        self._sessions[session_id] = {
            "session_id": session_id,
            "user_id": self._user.user_id,
            "device_id": device_id,
            "tenant_id": tenant_id,
            "role": role,
            "issued_at": iat,
            "expires_at": exp,
            "is_active": True,
        }

        self._user.last_login_at = time.time()
        try:
            from audit.client import get_audit_logger
            get_audit_logger().record(
                module="auth",
                action="login",
                tenant_id=tenant_id,
                user_id=self._user.user_id,
                role=role,
                resource=device_id,
                status="success",
                details={"device_name": device_name, "platform": platform},
            )
        except Exception:
            pass

        return SessionToken(
            token_string=token_str,
            session_id=session_id,
            user_id=self._user.user_id,
            device_id=device_id,
            tenant_id=tenant_id,
            role=role,
            issued_at=iat,
            expires_at=exp,
        )

    def validate_session(self, token_str: str) -> Dict[str, Any]:
        """
        Validate cryptographic signature, expiration, session state, and device state.
        """
        if self._vault_manager:
            is_valid, payload, err = verify_session_token_with_vault(
                token_str=token_str,
                vault_manager=self._vault_manager,
                key_id=self._vault_key_id,
            )
        else:
            is_valid, payload, err = verify_session_token(token_str, self._signing_key)

        if not is_valid:
            raise SessionInvalidError(f"Session verification failed: {err}")

        device_id = payload["did"]
        if self.device_registry.is_device_blacklisted(device_id):
            raise SessionInvalidError(f"Origin device '{device_id}' is blacklisted.")

        if not self.device_registry.is_device_active(device_id):
            raise SessionInvalidError(f"Origin device '{device_id}' is revoked or not trusted.")

        session_id = payload["sid"]
        sess_record = self._sessions.get(session_id)
        if not sess_record or not sess_record.get("is_active", False):
            raise SessionInvalidError("Session has been revoked or expired.")

        return payload

    def list_active_sessions(self) -> List[SessionInfo]:
        """List all active sessions and their bound devices."""
        now = time.time()
        active = []
        for sid, sess in list(self._sessions.items()):
            if not sess.get("is_active", False):
                continue
            if now > sess.get("expires_at", 0):
                sess["is_active"] = False
                continue

            dev = self.device_registry.get_device(sess["device_id"])
            active.append(
                SessionInfo(
                    session_id=sid,
                    user_id=sess["user_id"],
                    device_id=sess["device_id"],
                    device_name=dev.device_name if dev else "Unknown Device",
                    platform=dev.platform if dev else "unknown",
                    issued_at=sess["issued_at"],
                    expires_at=sess["expires_at"],
                    is_active=True,
                )
            )
        return active

    def list_devices(self) -> List[DeviceInfo]:
        """Inspect all registered devices."""
        return self.device_registry.list_devices()

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific active session."""
        if session_id in self._sessions:
            self._sessions[session_id]["is_active"] = False
            return True
        return False

    def revoke_device(self, device_id: str, reason: str = "Device revoked by user") -> bool:
        """
        Revoke a device and instantly terminate ALL active sessions originating from it.
        """
        revoked = self.device_registry.revoke_device(device_id, reason=reason)
        if not revoked:
            return False

        # Invalidate all active sessions for this device
        for sess in self._sessions.values():
            if sess["device_id"] == device_id:
                sess["is_active"] = False

        return True

    def sign_out(self, token_str: str) -> bool:
        """Sign out current session."""
        try:
            payload = self.validate_session(token_str)
            return self.revoke_session(payload["sid"])
        except Exception:
            return False

    def blacklist_device(self, device_id: str, reason: str = "Device blacklisted by admin") -> bool:
        """Blacklist a device permanently and invalidate all its active sessions."""
        self.device_registry.blacklist_device(device_id, reason)
        for sess in self._sessions.values():
            if sess["device_id"] == device_id:
                sess["is_active"] = False
        return True

    def is_device_blacklisted(self, device_id: str) -> bool:
        return self.device_registry.is_device_blacklisted(device_id)
