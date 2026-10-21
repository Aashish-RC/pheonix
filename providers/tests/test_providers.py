"""
Pheonix Provider Activation Automated Tests
Validates key onboarding, ping probes, periodic health checks, and revocation synchronization.
CRITICAL INVARIANT: "Done when: A revoked key shows as inactive"
"""

import pytest
from pathlib import Path

from providers import (
    ProviderActivationManager,
    ProviderCatalog,
    ProviderStatus,
    PingResult,
    ProviderDescriptor,
)
from vault import KeyStoreManager


@pytest.fixture
def temp_vault(tmp_path):
    vault_path = tmp_path / "providers_test_vault.enc"
    mgr = KeyStoreManager(vault_path)
    mgr.initialize("master-passphrase-for-providers")
    return mgr


def mock_successful_probe(desc: ProviderDescriptor, secret: str) -> PingResult:
    return PingResult(
        success=True,
        latency_ms=42.5,
        status_code=200,
        error_message=None,
    )


def mock_failing_probe(desc: ProviderDescriptor, secret: str) -> PingResult:
    return PingResult(
        success=False,
        latency_ms=115.0,
        status_code=401,
        error_message="HTTP 401: Invalid API Key or Unauthorized",
    )


def test_provider_catalog():
    assert ProviderCatalog.get_descriptor("openai") is not None
    assert ProviderCatalog.get_descriptor("anthropic") is not None
    assert ProviderCatalog.get_descriptor("gemini") is not None
    assert ProviderCatalog.get_descriptor("ollama") is not None

    supported = ProviderCatalog.list_supported_providers()
    assert len(supported) >= 6


def test_provider_activation_success(temp_vault):
    mgr = ProviderActivationManager(vault_manager=temp_vault)

    success, record, ping = mgr.activate_provider(
        provider_id="openai",
        secret="sk-proj-valid-test-key",
        probe_fn=mock_successful_probe,
    )

    assert success is True
    assert record.status == ProviderStatus.ACTIVE
    assert ping.latency_ms == 42.5
    assert mgr.is_provider_active("openai") is True

    # Check that key was securely stored in vault
    assert temp_vault.has_secret("prov_openai")
    with temp_vault.get_lease("prov_openai") as lease:
        assert lease.get_plaintext() == "sk-proj-valid-test-key"


def test_provider_activation_failure_when_ping_fails(temp_vault):
    mgr = ProviderActivationManager(vault_manager=temp_vault)

    success, record, ping = mgr.activate_provider(
        provider_id="mistral",
        secret="bad-key-xyz",
        probe_fn=mock_failing_probe,
    )

    assert success is False
    assert record.status == ProviderStatus.INACTIVE
    assert "HTTP 401" in record.revocation_reason
    assert mgr.is_provider_active("mistral") is False


def test_revoked_key_shows_as_inactive(temp_vault):
    """
    CRITICAL INVARIANT: "Done when: A revoked key shows as inactive"
    Verify that when a key is revoked in the Vault, the provider
    immediately reports INACTIVE status.
    """
    mgr = ProviderActivationManager(vault_manager=temp_vault)

    # 1. Activate provider with valid key
    mgr.activate_provider(
        provider_id="anthropic",
        secret="sk-ant-valid-token-123",
        probe_fn=mock_successful_probe,
    )
    assert mgr.get_provider_status("anthropic") == ProviderStatus.ACTIVE
    assert mgr.is_provider_active("anthropic") is True

    # 2. Revoke the key directly in the underlying Vault
    temp_vault.revoke_secret("prov_anthropic", reason="Compromised during security incident")

    # 3. VERIFICATION: Status immediately transitions to INACTIVE
    status = mgr.get_provider_status("anthropic")
    assert status == ProviderStatus.INACTIVE
    assert mgr.is_provider_active("anthropic") is False

    # 4. Attempting to recheck also confirms INACTIVE without throwing unhandled exceptions
    recheck_res = mgr.recheck_provider("anthropic", probe_fn=mock_successful_probe)
    assert recheck_res.success is False
    assert mgr.get_provider_status("anthropic") == ProviderStatus.INACTIVE


def test_manager_revoke_provider_syncs_with_vault(temp_vault):
    mgr = ProviderActivationManager(vault_manager=temp_vault)

    mgr.activate_provider(
        provider_id="gemini",
        secret="valid-gemini-key",
        probe_fn=mock_successful_probe,
    )
    assert mgr.is_provider_active("gemini") is True

    # Revoke via ProviderActivationManager
    revoked = mgr.revoke_provider("gemini", reason="User opted out of Google provider")
    assert revoked is True

    # Provider is INACTIVE
    assert mgr.get_provider_status("gemini") == ProviderStatus.INACTIVE
    assert mgr.is_provider_active("gemini") is False

    # Key is also revoked in the Vault
    assert not temp_vault.has_secret("prov_gemini")


def test_recheck_provider_degraded_and_restored(temp_vault):
    mgr = ProviderActivationManager(vault_manager=temp_vault)

    mgr.activate_provider(
        provider_id="openrouter",
        secret="sk-or-test",
        probe_fn=mock_successful_probe,
    )
    assert mgr.is_provider_active("openrouter") is True

    # Periodic recheck fails (upstream outage / quota exhausted)
    recheck_bad = mgr.recheck_provider("openrouter", probe_fn=mock_failing_probe)
    assert recheck_bad.success is False
    assert mgr.get_provider_status("openrouter") == ProviderStatus.INACTIVE

    # Periodic recheck passes (service restored)
    recheck_good = mgr.recheck_provider("openrouter", probe_fn=mock_successful_probe)
    assert recheck_good.success is True
    assert mgr.get_provider_status("openrouter") == ProviderStatus.ACTIVE


def test_local_provider_activation():
    # Ollama local endpoint doesn't require API key
    mgr = ProviderActivationManager(vault_manager=None)

    success, record, ping = mgr.activate_provider(
        provider_id="ollama",
        secret="",
        probe_fn=mock_successful_probe,
    )

    assert success is True
    assert record.status == ProviderStatus.ACTIVE
    assert mgr.is_provider_active("ollama") is True


def test_automatic_quarantine_after_3_failed_pings(temp_vault):
    """Verifies that 3 consecutive failed health pings automatically place provider in QUARANTINED state."""
    mgr = ProviderActivationManager(vault_manager=temp_vault)
    mgr.activate_provider(
        provider_id="openai",
        secret="sk-test-quarantine",
        probe_fn=mock_successful_probe,
    )
    assert mgr.get_provider_status("openai") == ProviderStatus.ACTIVE

    # Failure 1
    res1 = mgr.recheck_provider("openai", probe_fn=mock_failing_probe)
    assert not res1.success
    assert mgr.get_provider_status("openai") == ProviderStatus.INACTIVE

    # Failure 2
    res2 = mgr.recheck_provider("openai", probe_fn=mock_failing_probe)
    assert not res2.success
    assert mgr.get_provider_status("openai") == ProviderStatus.INACTIVE

    # Failure 3 -> triggers QUARANTINE
    res3 = mgr.recheck_provider("openai", probe_fn=mock_failing_probe)
    assert not res3.success
    assert mgr.get_provider_status("openai") == ProviderStatus.QUARANTINED
    assert mgr.is_provider_active("openai") is False

    rec = mgr._activated["openai"]
    assert "quarantined" in rec.revocation_reason.lower()


def test_token_refresh_failure_and_success_handling(temp_vault):
    """Verifies handling of token refresh failures and recovery upon successful token rotation."""
    mgr = ProviderActivationManager(vault_manager=temp_vault)
    mgr.activate_provider(
        provider_id="anthropic",
        secret="sk-ant-refresh-initial",
        probe_fn=mock_successful_probe,
    )
    assert mgr.is_provider_active("anthropic") is True

    # 1. Token refresh failure (e.g. invalid refresh grant)
    def failing_refresh():
        raise RuntimeError("OAuth refresh token expired or revoked by identity provider")

    success, err = mgr.refresh_provider_token("anthropic", failing_refresh)
    assert success is False
    assert "OAuth refresh token expired" in err
    assert mgr.get_provider_status("anthropic") == ProviderStatus.INACTIVE

    # 2. Token refresh success
    def successful_refresh():
        return "sk-ant-refreshed-new-token-12345"

    ok, no_err = mgr.refresh_provider_token("anthropic", successful_refresh)
    assert ok is True
    assert no_err is None
    assert mgr.get_provider_status("anthropic") == ProviderStatus.ACTIVE
    with temp_vault.get_lease("prov_anthropic") as lease:
        assert lease.get_plaintext() == "sk-ant-refreshed-new-token-12345"


def test_key_reactivation_from_quarantine(temp_vault):
    """Verifies that a quarantined provider can be reactivated with a new or refreshed key."""
    mgr = ProviderActivationManager(vault_manager=temp_vault)
    mgr.activate_provider("gemini", "initial-key", probe_fn=mock_successful_probe)

    # Force 3 failures to quarantine
    for _ in range(3):
        mgr.recheck_provider("gemini", probe_fn=mock_failing_probe)

    assert mgr.get_provider_status("gemini") == ProviderStatus.QUARANTINED

    # Reactivate with fresh valid key
    success, record, ping = mgr.reactivate_provider(
        provider_id="gemini",
        secret="new-fresh-gemini-key-999",
        probe_fn=mock_successful_probe,
    )

    assert success is True
    assert record.status == ProviderStatus.ACTIVE
    assert mgr.get_provider_status("gemini") == ProviderStatus.ACTIVE
    assert mgr.is_provider_active("gemini") is True
    assert mgr._consecutive_failures.get("gemini") == 0
