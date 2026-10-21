"""
Pheonix Provider Activation & Health Manager
Integrates with Key Store Vault and coordinates probe tests and revocation synchronization.
"""

import time
from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path

from ..models import (
    ActivatedProvider,
    ProviderStatus,
    ProviderDescriptor,
    PingResult,
    AuthType,
)
from .registry import ProviderCatalog, BUILTIN_PROVIDERS
from .ping import ping_provider


class ProviderActivationError(Exception):
    """Raised when provider activation fails."""
    pass


class ProviderActivationManager:
    """
    Manages active model providers, executes ping tests, and enforces revocation synchronization.
    Guarantees: A revoked key shows as inactive.
    """

    def __init__(self, vault_manager=None):
        self.vault_manager = vault_manager
        # provider_id -> ActivatedProvider
        self._activated: Dict[str, ActivatedProvider] = {}
        self._consecutive_failures: Dict[str, int] = {}

    def activate_provider(
        self,
        provider_id: str,
        secret: str = "",
        probe_fn: Optional[Callable[[ProviderDescriptor, str], PingResult]] = None,
    ) -> Tuple[bool, ActivatedProvider, PingResult]:
        """
        Onboard and activate a provider key.
        Runs live ping test; if ping succeeds, marks status as ACTIVE.
        """
        desc = ProviderCatalog.get_descriptor(provider_id)
        if not desc:
            raise ProviderActivationError(f"Unsupported provider: '{provider_id}'")

        key_id = f"prov_{provider_id}"
        now = time.time()

        # 1. Store secret safely in Vault if vault manager provided and secret is non-empty
        if self.vault_manager and secret:
            self.vault_manager.put_secret(
                key_id=key_id,
                secret=secret,
                provider=provider_id,
                description=f"Active credential for {desc.name}",
            )

        # 2. Execute automated ping probe
        ping_res = ping_provider(desc, secret, probe_fn=probe_fn)

        status = ProviderStatus.ACTIVE if ping_res.success else ProviderStatus.INACTIVE

        activated_record = ActivatedProvider(
            provider_id=provider_id,
            name=desc.name,
            key_id=key_id,
            status=status,
            auth_type=desc.auth_type,
            last_ping_at=now,
            last_latency_ms=ping_res.latency_ms if ping_res.success else None,
            activated_at=now,
            revocation_reason=None if ping_res.success else ping_res.error_message,
        )

        self._activated[provider_id] = activated_record
        return ping_res.success, activated_record, ping_res

    def recheck_provider(
        self,
        provider_id: str,
        probe_fn: Optional[Callable[[ProviderDescriptor, str], PingResult]] = None,
    ) -> PingResult:
        """
        Recheck health of an activated provider.
        CRITICAL: If the key was revoked in the Vault, the provider immediately becomes INACTIVE.
        """
        record = self._activated.get(provider_id)
        if not record:
            raise KeyError(f"Provider '{provider_id}' is not activated.")

        desc = ProviderCatalog.get_descriptor(provider_id)
        if not desc:
            raise KeyError(f"Descriptor for '{provider_id}' not found.")

        # 1. Vault Revocation Check
        if self.vault_manager and desc.auth_type != AuthType.LOCAL_ENDPOINT:
            if not self.vault_manager.has_secret(record.key_id):
                record.status = ProviderStatus.INACTIVE
                record.revocation_reason = "Underlying vault credential was revoked or deleted"
                return PingResult(
                    success=False,
                    latency_ms=0.0,
                    status_code=401,
                    error_message=record.revocation_reason,
                )

        # 2. Retrieve secret lease from vault
        secret_val = ""
        if self.vault_manager and desc.auth_type != AuthType.LOCAL_ENDPOINT:
            try:
                lease = self.vault_manager.get_lease(record.key_id)
                with lease:
                    secret_val = lease.get_plaintext()
            except Exception as e:
                record.status = ProviderStatus.INACTIVE
                record.revocation_reason = f"Credential lease error: {e}"
                return PingResult(success=False, latency_ms=0.0, error_message=str(e))

        # 3. Probe endpoint
        ping_res = ping_provider(desc, secret_val, probe_fn=probe_fn)
        record.last_ping_at = time.time()
        record.last_latency_ms = ping_res.latency_ms

        if ping_res.success:
            self._consecutive_failures[provider_id] = 0
            record.status = ProviderStatus.ACTIVE
            record.revocation_reason = None
        else:
            failures = self._consecutive_failures.get(provider_id, 0) + 1
            self._consecutive_failures[provider_id] = failures
            if failures >= 3:
                record.status = ProviderStatus.QUARANTINED
                record.revocation_reason = (
                    f"Provider automatically quarantined after {failures} consecutive failed pings: {ping_res.error_message}"
                )
            else:
                record.status = ProviderStatus.INACTIVE
                record.revocation_reason = ping_res.error_message

        return ping_res

    def refresh_provider_token(
        self,
        provider_id: str,
        refresh_fn: Callable[[], str],
    ) -> Tuple[bool, Optional[str]]:
        """Handles automated or manual OAuth/token refresh for a provider."""
        record = self._activated.get(provider_id)
        if not record:
            return False, f"Provider '{provider_id}' is not activated."

        try:
            new_token = refresh_fn()
            if not new_token:
                raise ValueError("Token refresh returned empty token")

            if self.vault_manager and record.key_id:
                self.vault_manager.put_secret(
                    key_id=record.key_id,
                    secret=new_token,
                    provider=provider_id,
                    description=f"Refreshed credential for {record.name}",
                )

            self._consecutive_failures[provider_id] = 0
            record.status = ProviderStatus.ACTIVE
            record.revocation_reason = None
            return True, None
        except Exception as e:
            record.status = ProviderStatus.INACTIVE
            record.revocation_reason = f"Token refresh failure: {e}"
            return False, str(e)

    def reactivate_provider(
        self,
        provider_id: str,
        secret: Optional[str] = None,
        probe_fn: Optional[Callable[[ProviderDescriptor, str], PingResult]] = None,
    ) -> Tuple[bool, ActivatedProvider, PingResult]:
        """Recovers and reactivates a quarantined or inactive provider with a refreshed or new key."""
        self._consecutive_failures[provider_id] = 0
        desc = ProviderCatalog.get_descriptor(provider_id)

        # Retrieve secret from vault if none provided
        sec = secret or ""
        if not sec and self.vault_manager:
            try:
                lease = self.vault_manager.get_lease(f"prov_{provider_id}")
                with lease:
                    sec = lease.get_plaintext()
            except Exception:
                pass

        return self.activate_provider(provider_id=provider_id, secret=sec, probe_fn=probe_fn)

    def revoke_provider(self, provider_id: str, reason: str = "User revoked provider") -> bool:
        """
        Explicitly revoke an active provider.
        Synchronizes with Vault: A revoked key shows as inactive.
        """
        record = self._activated.get(provider_id)
        if not record:
            return False

        record.status = ProviderStatus.INACTIVE
        record.revocation_reason = reason

        # Revoke key in Vault
        if self.vault_manager:
            self.vault_manager.revoke_secret(record.key_id, reason=reason)

        return True

    def get_provider_status(self, provider_id: str) -> ProviderStatus:
        """
        Inspect live status. If vault key was revoked out-of-band, immediately reflects INACTIVE.
        """
        record = self._activated.get(provider_id)
        if not record:
            return ProviderStatus.INACTIVE

        # Check if underlying vault key has been revoked
        if self.vault_manager and record.auth_type != AuthType.LOCAL_ENDPOINT:
            if not self.vault_manager.has_secret(record.key_id):
                record.status = ProviderStatus.INACTIVE
                record.revocation_reason = "Key revoked in vault"

        return record.status

    def is_provider_active(self, provider_id: str) -> bool:
        return self.get_provider_status(provider_id) == ProviderStatus.ACTIVE

    def list_activated_providers(
        self,
        status_filter: Optional[ProviderStatus] = None,
    ) -> List[ActivatedProvider]:
        """List activated providers, ensuring vault status synchronization."""
        results = []
        for pid in list(self._activated.keys()):
            # Trigger status sync
            self.get_provider_status(pid)
            rec = self._activated[pid]
            if status_filter is None or rec.status == status_filter:
                results.append(rec)
        return results

    def export_capability_sync(self) -> List[Dict[str, Any]]:
        """
        Export provider activation statuses for gateway capability matrix synchronization.
        Wires providers -> model-gateway capability matrix.
        """
        sync_payload = []
        for pid in list(self._activated.keys()):
            self.get_provider_status(pid)
            rec = self._activated[pid]
            desc = ProviderCatalog.get_descriptor(pid)
            sync_payload.append({
                "provider": pid,
                "active": rec.status == ProviderStatus.ACTIVE,
                "latencyMs": rec.last_latency_ms,
                "models": desc.models if desc else [],
                "keyId": rec.key_id,
            })
        return sync_payload

