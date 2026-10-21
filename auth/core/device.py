"""
Pheonix Device Identity & Registry Engine
Tracks registered devices, fingerprints, trust status, and revocation.
"""

import hashlib
import time
from typing import Dict, Any, Optional
from ..models import DeviceInfo


def compute_device_fingerprint(
    device_id: str,
    platform: str,
    hardware_salt: str = "PHX_DEVICE_SALT",
) -> str:
    """Compute a deterministic cryptographic fingerprint for a device."""
    data = f"{device_id}:{platform}:{hardware_salt}".encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class DeviceRegistry:
    """In-memory and persisted device catalog."""

    def __init__(self):
        self._devices: Dict[str, DeviceInfo] = {}
        self._blacklisted: set[str] = set()

    def blacklist_device(self, device_id: str, reason: str = "Device blacklisted") -> bool:
        self._blacklisted.add(device_id)
        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.is_revoked = True
            dev.is_trusted = False
            dev.revocation_reason = reason
        return True

    def is_device_blacklisted(self, device_id: str) -> bool:
        return device_id in self._blacklisted

    def register_or_update(
        self,
        device_id: str,
        device_name: str,
        platform: str,
        is_trusted: bool = True,
    ) -> DeviceInfo:
        """Register a new device or update last active timestamp."""
        now = time.time()
        fp = compute_device_fingerprint(device_id, platform)

        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.last_active_at = now
            dev.device_name = device_name
            dev.platform = platform
            return dev

        dev = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            platform=platform,
            fingerprint=fp,
            first_seen_at=now,
            last_active_at=now,
            is_trusted=is_trusted,
            is_revoked=False,
            revocation_reason=None,
        )
        self._devices[device_id] = dev
        return dev

    def get_device(self, device_id: str) -> Optional[DeviceInfo]:
        return self._devices.get(device_id)

    def is_device_active(self, device_id: str) -> bool:
        if self.is_device_blacklisted(device_id):
            return False
        dev = self._devices.get(device_id)
        if not dev:
            return False
        return not dev.is_revoked and dev.is_trusted

    def revoke_device(self, device_id: str, reason: str = "User initiated revocation") -> bool:
        dev = self._devices.get(device_id)
        if not dev:
            return False
        dev.is_revoked = True
        dev.is_trusted = False
        dev.revocation_reason = reason
        dev.last_active_at = time.time()
        return True

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())
