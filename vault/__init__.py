"""
Pheonix Vault - Zero-Plaintext Cryptographic Vault and Key Store
"""

from .core.manager import (
    KeyStoreManager,
    SecretNotFoundError,
    SecretRevokedError,
)
from .core.memory_guard import (
    SecretLease,
    SecretExpiredError,
    SecretReleasedError,
)
from .core.store import (
    InvalidPassphraseError,
    CorruptedVaultError,
)
from .models import SecretMetadata, AuditEntry

__all__ = [
    "KeyStoreManager",
    "SecretLease",
    "SecretMetadata",
    "AuditEntry",
    "SecretNotFoundError",
    "SecretRevokedError",
    "SecretExpiredError",
    "SecretReleasedError",
    "InvalidPassphraseError",
    "CorruptedVaultError",
]
