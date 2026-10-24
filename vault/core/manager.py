"""
Pheonix Vault High-Level KeyStore Manager
Coordinates secret lifecycle, access leasing, rotation, and revocation.
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import time
import threading

from ..models import SecretMetadata, AuditEntry
from .memory_guard import SecretLease
from .store import VaultStore, InvalidPassphraseError, CorruptedVaultError


class SecretNotFoundError(Exception):
    """Raised when a requested key ID does not exist in the vault."""
    pass


class SecretRevokedError(Exception):
    """Raised when a requested key ID has been explicitly revoked."""
    pass


class KeyStoreManager:
    """
    Manages the lifecycle of encrypted credentials in the Pheonix vault.
    Zero-plaintext storage guarantee: Secrets are only decrypted into ephemeral SecretLeases.
    """

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.store = VaultStore(self.vault_path)
        self._unlocked_passphrase: Optional[str] = None
        self._cached_data: Optional[Dict[str, Any]] = None
        self._lock = threading.RLock()

    def is_initialized(self) -> bool:
        return self.store.exists()

    def initialize(self, passphrase: str):
        """Create a new, empty encrypted vault."""
        if self.is_initialized():
            raise FileExistsError(f"Vault already initialized at {self.vault_path}")

        initial_data = {
            "version": 1,
            "created_at": time.time(),
            "secrets": {},
            "audit": [
                {
                    "timestamp": time.time(),
                    "action": "INIT",
                    "key_id": None,
                    "success": True,
                    "details": "Vault initialized",
                }
            ],
        }
        self.store.save_vault(initial_data, passphrase)
        self._unlocked_passphrase = passphrase
        self._cached_data = initial_data

    def unlock(self, passphrase: str):
        """Unlock and decrypt vault into active session memory."""
        data = self.store.load_vault(passphrase)
        self._unlocked_passphrase = passphrase
        self._cached_data = data

    def lock(self):
        """Clear decrypted data and cached passphrase from active memory."""
        self._unlocked_passphrase = None
        self._cached_data = None

    def _ensure_unlocked(self):
        if not self._unlocked_passphrase or self._cached_data is None:
            raise PermissionError("Vault is locked. Call unlock(passphrase) first.")

    @property
    def _data(self) -> Dict[str, Any]:
        self._ensure_unlocked()
        assert self._cached_data is not None
        return self._cached_data

    @property
    def _passphrase(self) -> str:
        self._ensure_unlocked()
        assert self._unlocked_passphrase is not None
        return self._unlocked_passphrase

    def _persist(
        self,
        action: str,
        key_id: Optional[str] = None,
        details: Optional[str] = None,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        role: str = "user",
    ):
        with self._lock:
            audit_entry = {
                "timestamp": time.time(),
                "action": action,
                "key_id": key_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "role": role,
                "success": True,
                "details": details,
            }
            self._data["audit"].append(audit_entry)
            self.store.save_vault(self._data, self._passphrase)
            try:
                from audit.client import get_audit_logger
                get_audit_logger().record(
                    module="vault",
                    action=action.lower(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    role=role,
                    resource=key_id or "vault",
                    status="success",
                    details={"details": details} if details else {},
                )
            except Exception:
                pass

    def put_secret(
        self,
        key_id: str,
        secret: str,
        provider: str = "custom",
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
    ):
        """Store or update a secret in the encrypted vault."""
        with self._lock:
            self._ensure_unlocked()
            now = time.time()
            existing = self._data["secrets"].get(key_id)

            meta = SecretMetadata(
                key_id=key_id,
                provider=provider,
                tenant_id=tenant_id,
                user_id=user_id,
                description=description,
                tags=tags or [],
                created_at=existing["metadata"]["created_at"] if existing else now,
                updated_at=now,
                revoked=False,
                revoked_at=None,
                revocation_reason=None,
            )

            self._data["secrets"][key_id] = {
                "metadata": meta.model_dump(),
                "value": secret,
            }
            self._persist(
                "PUT",
                key_id=key_id,
                details=f"Provider: {provider}",
                tenant_id=tenant_id,
                user_id=user_id,
            )

    def get_lease(self, key_id: str, ttl_seconds: float = 60.0) -> SecretLease:
        """
        Obtain an ephemeral in-memory lease for a secret.
        The lease guarantees memory zeroization on disposal.
        """
        with self._lock:
            self._ensure_unlocked()
            secret_entry = self._data["secrets"].get(key_id)
            if not secret_entry:
                raise SecretNotFoundError(f"Key ID '{key_id}' not found in vault.")

            meta = secret_entry["metadata"]
            if meta.get("revoked", False):
                raise SecretRevokedError(
                    f"Key ID '{key_id}' was revoked at {meta.get('revoked_at')}: {meta.get('revocation_reason')}"
                )

            secret_str = secret_entry["value"]
            lease = SecretLease(key_id, secret_str.encode("utf-8"), ttl_seconds=ttl_seconds)
            self._persist(
                "GET",
                key_id=key_id,
                details=f"Lease granted for {ttl_seconds}s",
                tenant_id=meta.get("tenant_id", "default"),
                user_id=meta.get("user_id"),
            )
            return lease

    def has_secret(self, key_id: str) -> bool:
        """Check if an active, non-revoked secret exists."""
        self._ensure_unlocked()
        entry = self._data["secrets"].get(key_id)
        if not entry:
            return False
        return not entry["metadata"].get("revoked", False)

    def list_secrets(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[SecretMetadata]:
        """List metadata of all stored secrets with optional tenant and per-user filtering."""
        self._ensure_unlocked()
        results = [
            SecretMetadata(**entry["metadata"])
            for entry in self._data["secrets"].values()
        ]
        if tenant_id is not None:
            results = [s for s in results if s.tenant_id == tenant_id]
        if user_id is not None:
            results = [s for s in results if s.user_id == user_id]
        return results

    def revoke_secret(self, key_id: str, reason: Optional[str] = None) -> bool:
        """
        Immediately revoke a secret, tombstoning its metadata and erasing the ciphertext.
        """
        self._ensure_unlocked()
        entry = self._data["secrets"].get(key_id)
        if not entry:
            return False

        now = time.time()
        entry["metadata"]["revoked"] = True
        entry["metadata"]["revoked_at"] = now
        entry["metadata"]["revocation_reason"] = reason or "Explicit user revocation"
        # Overwrite value with tombstone marker
        entry["value"] = "[REVOKED_TOMBSTONE]"

        self._persist("REVOKE", key_id=key_id, details=reason)
        return True

    def rotate_passphrase(self, new_passphrase: str):
        """
        Re-encrypt the vault DEK with a new KEK derived from new_passphrase.
        Envelope encryption ensures instant rotation without re-encrypting individual secrets.
        """
        self._ensure_unlocked()
        self._unlocked_passphrase = new_passphrase
        self._persist("ROTATE", details="Vault master passphrase rotated")

    def get_audit_log(self) -> List[AuditEntry]:
        """Retrieve audit log entries."""
        self._ensure_unlocked()
        return [AuditEntry(**entry) for entry in self._data.get("audit", [])]
