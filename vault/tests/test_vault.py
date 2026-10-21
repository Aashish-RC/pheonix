"""
Pheonix Vault Automated Security & Cryptographic Invariant Tests
Validates zero-plaintext disk storage, memory zeroization, tamper detection, and instant revocation.
"""

import time
import os
import pytest
from pathlib import Path

from vault import (
    KeyStoreManager,
    SecretLease,
    SecretNotFoundError,
    SecretRevokedError,
    SecretExpiredError,
    SecretReleasedError,
    InvalidPassphraseError,
    CorruptedVaultError,
)
from vault.core.store import VAULT_MAGIC_V1


@pytest.fixture
def temp_vault_path(tmp_path):
    """Provides a fresh temporary vault file path."""
    return tmp_path / "test_vault.enc"


def test_vault_init_and_unlock(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    assert not mgr.is_initialized()

    mgr.initialize("correct-horse-battery-staple")
    assert mgr.is_initialized()
    assert temp_vault_path.exists()

    # Verify magic header
    with open(temp_vault_path, "rb") as f:
        magic = f.read(16)
        assert magic == VAULT_MAGIC_V1

    # Reload with correct passphrase
    mgr2 = KeyStoreManager(temp_vault_path)
    mgr2.unlock("correct-horse-battery-staple")

    # Reload with incorrect passphrase
    mgr3 = KeyStoreManager(temp_vault_path)
    with pytest.raises(InvalidPassphraseError):
        mgr3.unlock("wrong-passphrase")


def test_secret_put_and_lease(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("master-pass")

    raw_secret = "sk-proj-test123456789abcdef"
    mgr.put_secret(
        key_id="openai_prod",
        secret=raw_secret,
        provider="openai",
        description="Production OpenAI API Key",
        tags=["prod", "llm"],
    )

    assert mgr.has_secret("openai_prod")

    # Retrieve lease
    lease = mgr.get_lease("openai_prod")
    assert isinstance(lease, SecretLease)
    assert lease.is_valid()
    assert lease.get_plaintext() == raw_secret
    assert lease.get_bytes() == raw_secret.encode("utf-8")

    # Verify redaction in string representation
    assert raw_secret not in str(lease)
    assert raw_secret not in repr(lease)
    assert "[REDACTED]" in str(lease)


def test_memory_zeroization(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("master-pass")

    raw_secret = "super-sensitive-secret-token"
    mgr.put_secret("token_1", raw_secret)

    lease = mgr.get_lease("token_1")
    assert lease.is_valid()
    assert lease.get_plaintext() == raw_secret

    # Explicit release
    lease.release()
    assert not lease.is_valid()
    with pytest.raises(SecretReleasedError):
        lease.get_plaintext()
    with pytest.raises(SecretReleasedError):
        lease.get_bytes()

    # Context manager release
    with mgr.get_lease("token_1") as ctx_lease:
        assert ctx_lease.is_valid()
        assert ctx_lease.get_plaintext() == raw_secret
    # Post-context
    assert not ctx_lease.is_valid()
    with pytest.raises(SecretReleasedError):
        ctx_lease.get_plaintext()


def test_zero_plaintext_on_disk(temp_vault_path):
    """
    CRITICAL INVARIANT: Secrets must NEVER appear in plaintext anywhere in the vault file.
    """
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("master-pass-12345")

    sensitive_tokens = [
        "sk-proj-99999999999999999999999999999999",
        "ghp_verySecretGithubPersonalAccessToken123",
        "secret-db-password-xyz-777",
    ]

    for idx, token in enumerate(sensitive_tokens):
        mgr.put_secret(f"key_{idx}", token)

    # Read binary contents of the vault file from disk
    with open(temp_vault_path, "rb") as f:
        file_bytes = f.read()

    # Search for any plaintext substring
    for token in sensitive_tokens:
        assert token.encode("utf-8") not in file_bytes, f"Plaintext leak detected for {token}!"
        # Even partial tokens must not be exposed
        assert token[:15].encode("utf-8") not in file_bytes


def test_tamper_detection(temp_vault_path):
    """
    AEAD Authenticated Encryption: Any modification of ciphertext or header
    must immediately trigger an authentication rejection.
    """
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("passphrase-for-tamper-test")
    mgr.put_secret("target_key", "secret-value-to-protect")

    with open(temp_vault_path, "rb") as f:
        data = bytearray(f.read())

    # Flip a bit in the encrypted payload area (near the end of file)
    data[-5] ^= 0xFF

    with open(temp_vault_path, "wb") as f:
        f.write(data)

    # Attempt to unlock/load tampered vault
    mgr_tampered = KeyStoreManager(temp_vault_path)
    with pytest.raises((CorruptedVaultError, InvalidPassphraseError)):
        mgr_tampered.unlock("passphrase-for-tamper-test")


def test_revocation_lifecycle(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("passphrase-revocation")

    mgr.put_secret("anthropic_key", "sk-ant-test-8888")
    assert mgr.has_secret("anthropic_key")

    # Perform revocation
    revoked = mgr.revoke_secret("anthropic_key", reason="Key compromised in security audit")
    assert revoked is True

    # Check immediate state
    assert not mgr.has_secret("anthropic_key")
    with pytest.raises(SecretRevokedError) as exc_info:
        mgr.get_lease("anthropic_key")
    assert "Key compromised in security audit" in str(exc_info.value)

    # Verify persistence of revocation after reload
    mgr2 = KeyStoreManager(temp_vault_path)
    mgr2.unlock("passphrase-revocation")
    assert not mgr2.has_secret("anthropic_key")
    with pytest.raises(SecretRevokedError):
        mgr2.get_lease("anthropic_key")


def test_passphrase_rotation(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("initial-passphrase")
    mgr.put_secret("shared_secret", "secret-payload-persists-across-rotations")

    # Rotate passphrase
    mgr.rotate_passphrase("new-strong-passphrase")

    # Verify old passphrase no longer unlocks
    mgr_old = KeyStoreManager(temp_vault_path)
    with pytest.raises(InvalidPassphraseError):
        mgr_old.unlock("initial-passphrase")

    # Verify new passphrase unlocks and restores secrets
    mgr_new = KeyStoreManager(temp_vault_path)
    mgr_new.unlock("new-strong-passphrase")
    assert mgr_new.has_secret("shared_secret")
    with mgr_new.get_lease("shared_secret") as lease:
        assert lease.get_plaintext() == "secret-payload-persists-across-rotations"


def test_lease_expiry(temp_vault_path):
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("passphrase-expiry")
    mgr.put_secret("short_lived", "ephemeral-data")

    # Obtain lease with 1.5s TTL
    lease = mgr.get_lease("short_lived", ttl_seconds=1.5)
    assert lease.is_valid()
    assert lease.get_plaintext() == "ephemeral-data"

    time.sleep(1.6)
    assert not lease.is_valid()
    with pytest.raises(SecretExpiredError):
        lease.get_plaintext()


import concurrent.futures


def test_concurrent_threads_access_leases_without_deadlock(temp_vault_path):
    """Verifies that 20 concurrent worker threads can lease and read secrets simultaneously without deadlock."""
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("concurrency-test-passphrase")

    for i in range(5):
        mgr.put_secret(f"concurrency_key_{i}", f"secret_value_{i}_token")

    def worker(worker_id: int):
        target_key = f"concurrency_key_{worker_id % 5}"
        with mgr.get_lease(target_key, ttl_seconds=10.0) as lease:
            val = lease.get_plaintext()
            assert val == f"secret_value_{worker_id % 5}_token"
            return True

    # Execute 20 concurrent threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(worker, i) for i in range(20)]
        results = [f.result(timeout=10.0) for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    assert all(results)


def test_zero_plaintext_in_audit_dumps(temp_vault_path):
    """Verifies zero plaintext secrets appear anywhere in audit dumps or log records."""
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("audit-privacy-passphrase")

    secret_val = "super-secret-api-key-999-never-leak-in-audit"
    mgr.put_secret("audit_target", secret_val, description="Production API Key")

    # Access lease and revoke to generate diverse audit records
    with mgr.get_lease("audit_target", ttl_seconds=5.0) as lease:
        _ = lease.get_plaintext()

    audit_entries = mgr.get_audit_log()
    assert len(audit_entries) >= 3

    for entry in audit_entries:
        # Assert raw secret value never appears in audit details or string representations
        assert secret_val not in str(entry.details or "")
        assert secret_val not in str(entry)
        assert secret_val not in repr(entry)


def test_file_tampering_header_magic_detection(temp_vault_path):
    """Verifies that tampering with header magic bytes triggers instant corruption rejection."""
    mgr = KeyStoreManager(temp_vault_path)
    mgr.initialize("tamper-header-pass")
    mgr.put_secret("key1", "val1")

    with open(temp_vault_path, "r+b") as f:
        # Corrupt the magic bytes in the header
        f.seek(0)
        f.write(b"CORRUPTED_MAGIC_")

    mgr_tampered = KeyStoreManager(temp_vault_path)
    with pytest.raises((CorruptedVaultError, InvalidPassphraseError)):
        mgr_tampered.unlock("tamper-header-pass")
