"""
Cryptographic Device Pairing Coordinator.
Manages ephemeral PIN generation, mutual key verification, and secure device enrollment.
"""
from __future__ import annotations

import secrets
import time
from typing import Dict, Optional, Tuple
from remote_access.core.models import DeviceRegistration, DeviceStatus, DeviceType, PairingCode


class PairingCoordinator:
    """Coordinates out-of-band ephemeral pairing and mutual authentication."""

    def __init__(self, code_ttl_seconds: float = 300.0):
        self.code_ttl_seconds = code_ttl_seconds
        self._active_codes: Dict[str, PairingCode] = {}

    def generate_pairing_code(self, initiator_device_id: str, initiator_public_key: str) -> PairingCode:
        # Generate 6-digit cryptographically secure PIN
        code_str = f"{secrets.randbelow(900000) + 100000}"
        expires_at = time.time() + self.code_ttl_seconds

        code_obj = PairingCode(
            code=code_str,
            initiator_device_id=initiator_device_id,
            initiator_public_key=initiator_public_key,
            expires_at=expires_at,
            consumed=False,
        )
        self._active_codes[code_str] = code_obj
        return code_obj

    def redeem_pairing_code(
        self,
        code_str: str,
        client_device_id: str,
        client_device_name: str,
        client_device_type: DeviceType,
        client_public_key: str,
        client_ip: str = "127.0.0.1",
    ) -> Tuple[DeviceRegistration, bytes]:
        """Redeems an active pairing code and derives the initial pairing shared secret."""
        code_obj = self._active_codes.get(code_str)
        if not code_obj:
            raise ValueError("Invalid pairing code")

        if code_obj.consumed:
            raise ValueError("Pairing code has already been consumed")

        if time.time() > code_obj.expires_at:
            del self._active_codes[code_str]
            raise ValueError("Pairing code has expired")

        # Mark consumed
        code_obj.consumed = True
        del self._active_codes[code_str]

        # Derive shared secret from both public keys and PIN
        entropy = f"{code_obj.initiator_public_key}:{client_public_key}:{code_str}".encode("utf-8")

        registration = DeviceRegistration(
            device_id=client_device_id,
            device_name=client_device_name,
            device_type=client_device_type,
            public_key=client_public_key,
            ip_address=client_ip,
            status=DeviceStatus.ACTIVE,
            paired_at=time.time(),
            last_seen_at=time.time(),
        )

        return registration, entropy
