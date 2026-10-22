"""Live End-to-End Integration Test through Model Gateway & Live Infrastructure.

Validates the full live pipeline when live services are up:
1. Auth: register and log in
2. Vault: store credentials
3. Providers: activate provider 'ollama' with a real ping to http://localhost:11434
4. Gateway: POST chat completion to /v1/chat/completions -> assert non-empty answer
5. Memory: store conversation turn in Qdrant (http://localhost:6333)
6. Search: find indexed turn in Meilisearch (http://localhost:7700)
"""

import os
import sys
import json
import shutil
import urllib.request
import urllib.error
import pytest
from pathlib import Path

# Auth & Vault
from auth.core.manager import AuthManager
from vault.core.manager import KeyStoreManager

# Providers
from providers import ProviderActivationManager, ProviderCatalog

# Memory
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR / "memory") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "memory"))

from engine import MemoryEngine
from config import (
    MemoryConfig,
    WorkingMemoryBackend,
    FactStoreBackend,
    VectorStoreBackend,
    EmbeddingBackend,
)

# Search
from search import (
    MeilisearchClient,
    SearchDocument,
    SearchQuery,
    CorpusType,
)


@pytest.fixture
def test_env_setup(tmp_path):
    vault_file = tmp_path / "live_e2e_vault.enc"
    wal_dir = tmp_path / "wal"
    wal_dir.mkdir(parents=True, exist_ok=True)
    sqlite_db = tmp_path / "live_e2e_memory.db"

    yield {
        "vault_file": vault_file,
        "wal_dir": str(wal_dir),
        "sqlite_db": str(sqlite_db),
    }

    shutil.rmtree(wal_dir, ignore_errors=True)
    if sqlite_db.exists():
        try:
            sqlite_db.unlink()
        except OSError:
            pass


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("PHEONIX_LIVE") != "1",
    reason="Live integration tests require PHEONIX_LIVE=1 environment variable",
)
def test_e2e_live_gateway_pipeline(test_env_setup):
    """Live end-to-end test verifying Auth -> Vault -> Provider (Ollama) -> Gateway -> Qdrant -> Meilisearch."""
    # 1. Auth: register and log in
    vault_path = test_env_setup["vault_file"]
    vault = KeyStoreManager(vault_path)
    vault.initialize("master-passphrase-live-test")
    assert vault.is_initialized()

    auth_mgr = AuthManager(vault_manager=vault)
    user = auth_mgr.register_initial_user("live_tester", "PassphraseLiveTest!9988")
    assert user.username == "live_tester"

    session = auth_mgr.authenticate(
        username="live_tester",
        password="PassphraseLiveTest!9988",
        device_id="live_device_01",
        device_name="Live Test Device",
        platform="windows",
    )
    assert session.token_string is not None
    verified = auth_mgr.validate_session(session.token_string)
    assert verified["uid"] == user.user_id

    # 2. Vault: store a key in the vault
    ollama_service_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    vault.put_secret(
        key_id="ollama_local_url",
        secret=ollama_service_url,
        tags=["provider", "llm", "ollama"],
    )
    leased = vault.get_lease("ollama_local_url")
    assert leased.get_plaintext() == ollama_service_url
    leased.release()

    # 3. Providers: activate provider 'ollama' with a real ping to http://localhost:11434
    prov_mgr = ProviderActivationManager(vault_manager=vault)
    # Using real ping (no probe_fn mock injected)
    success, prov_record, ping = prov_mgr.activate_provider(
        provider_id="ollama",
        secret="local",
    )
    assert success is True, f"Failed live ping to Ollama at {ollama_service_url}: {ping.error_message}"
    assert ping.success is True
    assert prov_record.status.value == "active"

    # 4. Gateway: POST a chat to the gateway /v1/chat/completions -> assert non-empty answer
    gateway_url = os.getenv("MODEL_GATEWAY_URL", "http://localhost:4000")
    payload = json.dumps({
        "model": "llama3.2:1b",
        "messages": [
            {"role": "user", "content": "Respond with the single word PONG."}
        ],
        "max_tokens": 16,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{gateway_url}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30.0) as resp:
        assert resp.getcode() == 200
        resp_data = json.loads(resp.read().decode("utf-8"))

    choices = resp_data.get("choices", [])
    assert len(choices) > 0, "Gateway returned no choices in response"
    assistant_text = choices[0].get("message", {}).get("content", "").strip()
    assert len(assistant_text) > 0, "Gateway returned empty completion text"

    # 5. Memory: stores the turn in Qdrant
    qdrant_host = os.getenv("QDRANT_HOST", "http://localhost:6333")
    mem_config = MemoryConfig(
        working_backend=WorkingMemoryBackend.IN_MEMORY,
        wal_dir=test_env_setup["wal_dir"],
        fact_backend=FactStoreBackend.SQLITE,
        sqlite_path=test_env_setup["sqlite_db"],
        vector_backend=VectorStoreBackend.QDRANT,
        qdrant_location=qdrant_host,
        embedding_backend=EmbeddingBackend.LOCAL,
        embedding_dim=64,
        max_context_tokens=500,
    )
    memory_engine = MemoryEngine(config=mem_config)
    turn_text = f"User: Respond with the single word PONG.\nAssistant: {assistant_text}"
    mem_entry = memory_engine.remember(
        user_id=user.username,
        text=turn_text,
        session_id=session.session_id,
    )
    assert mem_entry is not None
    assert mem_entry["user_id"] == user.username

    # 6. Search: finds it in Meilisearch
    meili_url = os.getenv("MEILISEARCH_URL", "http://localhost:7700")
    meili_key = os.getenv("MEILISEARCH_MASTER_KEY", "masterKeyPheonix2026")
    search_client = MeilisearchClient(url=meili_url, master_key=meili_key)

    # Index document in Meilisearch
    search_doc = SearchDocument(
        id=f"turn_{session.session_id}_1",
        corpus_type=CorpusType.CHAT,
        project_id="live_e2e_proj",
        title="Live Turn 1",
        content=turn_text,
        tags=["live", "test", "chat"],
        metadata={"user_id": user.username, "session_id": session.session_id},
    )
    search_client.index_document(search_doc)

    # Search for turn in Meilisearch
    results = search_client.query("PONG", project_id="live_e2e_proj")
    assert len(results) > 0, "Expected at least 1 search hit for 'PONG'"
    assert "PONG" in results[0].document.content or "PONG" in results[0].document.title
