#!/usr/bin/env python3
"""
Pheonix Status Table Generator & Verification Script.

Ensures STATUS.md and ROADMAP.md stay synchronized and cannot drift.
Usage:
    python scripts/generate_status.py --check     # verify table integrity (fails CI if drifted)
    python scripts/generate_status.py --update    # regenerate STATUS.md table
"""

import sys
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
STATUS_MD = ROOT_DIR / "STATUS.md"
ROADMAP_MD = ROOT_DIR / "ROADMAP.md"


@dataclass
class StatusStep:
    step: int
    name: str
    module: str
    label: str  # REAL, PARTIAL, SIMULATED, MISSING
    evidence: str
    missing: str


CANONICAL_STEPS: List[StatusStep] = [
    StatusStep(1, "Repo, CI & Test Harness", "root/ci", "REAL", "`scripts/test_all.py`, `pyproject.toml`, `.github/workflows/ci.yml`", "Live multi-OS remote CI workflow verification runs."),
    StatusStep(2, "Key Store & Secrets", "vault", "REAL", "`vault/core/vault.py`, `vault/tests/test_vault.py`", "Hardware Security Module (HSM) / external KMS integration."),
    StatusStep(3, "Auth & Identity", "auth", "REAL", "`auth/core/session.py`, `auth/tests/test_auth.py`", "Multi-user database persistence and remote OAuth server."),
    StatusStep(4, "Component Registry v0", "registry", "REAL", "`registry/core/registry.py`, `registry/tests/test_registry.py`", "Remote package publishing / registry sync."),
    StatusStep(5, "Rules Layer, Minimal", "rules", "REAL", "`rules/core/engine.py`, `rules/tests/test_rules.py`", "Distributed pub/sub rule synchronization across remote nodes."),
    StatusStep(6, "Provider Activation", "providers", "PARTIAL", "`providers/core/manager.py`, `providers/tests/test_providers.py`", "Real remote provider ping over internet; tests inject fake pings. Note: Verified working in live gateway integration pipeline with Ollama and Qdrant."),
    StatusStep(7, "Model Gateway", "model-gateway", "PARTIAL", "`model-gateway/src/gateway.ts`, `model-gateway/tests/`", "Live upstream LLM provider calls; tests use mock upstreams only. Note: Verified working in live gateway integration pipeline with Ollama and Qdrant."),
    StatusStep(8, "Model Serving", "serving", "PARTIAL", "`serving/core/engine.py`, `serving/tests/test_serving.py`", "Live running Ollama / llama.cpp process in test; tested with mock adapter."),
    StatusStep(9, "Observability, Basic", "observability", "PARTIAL", "`observability/core/tracer.py`, `observability/tests/test_observability.py`", "Live remote Langfuse / OpenLLMetry collector; tests use mock HTTP and local buffer."),
    StatusStep(10, "Guardrails and Safety v0", "guardrails", "REAL", "`guardrails/core/engine.py`, `guardrails/tests/test_guardrails.py`", "ML embedding classifiers; uses deterministic attack patterns and crisis taxonomy."),
    StatusStep(11, "Subscription & Key Tracker", "tracker", "REAL", "`tracker/core/tracker.py`, `tracker/tests/test_tracker.py`", "Live billing provider webhooks (Stripe / OpenRouter billing sync)."),
    StatusStep(12, "Storage and Files", "storage", "PARTIAL", "`storage/core/engine.py`, `storage/drivers/s3.py`, `storage/tests/test_s3_driver.py`", "Production remote AWS S3 / MinIO cluster endpoint connection in live CI."),
    StatusStep(13, "Memory and Retrieval", "memory", "PARTIAL", "`memory/core/engine.py`, `memory/tests/test_engine.py`", "Live Qdrant cluster connection in test; runs SQLite facts and mock embeddings. Note: Verified working in live gateway integration pipeline with Qdrant and Ollama embeddings."),
    StatusStep(14, "Knowledge and Docs", "knowledge", "PARTIAL", "`knowledge/core/engine.py`, `knowledge/tests/test_knowledge.py`", "Live external document sync and sync engine coupling."),
    StatusStep(15, "Global Search", "search", "PARTIAL", "`search/core/engine.py`, `search/tests/test_meilisearch.py`", "Live Meilisearch HTTP service; tested with mock adapter and local fallback. Note: Verified working in live gateway integration pipeline with Meilisearch."),
    StatusStep(16, "Web Search and Scraping", "web_search", "PARTIAL", "`web_search/core/provider.py`, `web_search/tests/test_firecrawl.py`", "Live Firecrawl API key / live web scrape network access in test suite."),
    StatusStep(17, "Resource Optimizer", "resource_optimizer", "PARTIAL", "`resource_optimizer/core/optimizer.py`, `resource_optimizer/tests/test_resource_optimizer.py`", "Real host saturating inference benchmark; tests use fake signal injection & psutil."),
    StatusStep(18, "Permission Modes", "permissions", "REAL", "`permissions/core/engine.py`, `permissions/tests/test_permissions.py`", "Interactive OS desktop confirmation popups."),
    StatusStep(19, "Orchestrator", "orchestrator", "REAL", "`orchestrator/engine/dag_runner.py`, `orchestrator/tests/test_parallel_fanout.py`", "Durable workflow state persistence surviving host machine reboot."),
    StatusStep(20, "Agent Execution & Sandboxes", "sandboxes", "PARTIAL", "`sandboxes/core/engines.py`, `sandboxes/tests/test_engines.py`", "Real Docker daemon and cloud E2B runner in test; runs local subprocess only."),
    StatusStep(21, "Tool and MCP Registry", "tools_mcp", "PARTIAL", "`tools_mcp/runner/dispatcher.py`, `tools_mcp/tests/test_tools_mcp.py`", "Live external MCP server stdio/SSE socket transport."),
    StatusStep(22, "Internal Agents", "internal_agents", "REAL", "`internal_agents/core/runner.py`, `internal_agents/tests/test_internal_agents.py`", "Persistent background daemon cron scheduler."),
    StatusStep(23, "Recommender, Full", "recommender", "REAL", "`recommender/core/engine.py`, `recommender/tests/test_recommender.py`", "Large-scale empirical benchmark dataset training."),
    StatusStep(24, "Browser Automation", "browser_automation", "PARTIAL", "`browser_automation/core/agent.py`, `browser_automation/tests/test_playwright_live.py`", "Full multi-tab human takeover and CAPTCHA solving; Playwright adapter verified live."),
    StatusStep(25, "Agent Builder", "agent_builder", "REAL", "`agent_builder/core/builder.py`, `agent_builder/tests/test_agent_builder.py`", "Visual drag-and-drop web canvas frontend."),
    StatusStep(26, "Workflow Builder", "workflow_builder", "REAL", "`workflow_builder/core/builder.py`, `workflow_builder/tests/test_workflow_builder.py`", "Visual node-graph UI editor."),
    StatusStep(27, "Skills & Plugin Packaging", "skills_packaging", "REAL", "`skills_packaging/core/packager.py`, `skills_packaging/tests/test_skills_packaging.py`", "Remote marketplace package registry index."),
    StatusStep(28, "Notifications", "notifications", "PARTIAL", "`notifications/channels/dispatcher.py`, `notifications/tests/test_channel_dispatcher.py`", "Live Novu cloud and SMTP email dispatch; tests use local inbox store."),
    StatusStep(29, "Voice and Speech", "voice_speech", "PARTIAL", "`voice_speech/tts/synthesis_engine.py`, `voice_speech/tests/test_tts_gateway.py`", "Live Whisper model weights and live gateway audio server; tested via httpx MockTransport fake."),
    StatusStep(30, "Media Generation", "media_gen", "PARTIAL", "`media_gen/core/image_route.py`, `media_gen/tests/test_image_route_gateway.py`", "Live running model-gateway service; tested with httpx MockTransport fake and output guardrail."),
    StatusStep(31, "Translation", "translation", "PARTIAL", "`translation/core/engine.py`, `translation/tests/test_translation_gateway.py`", "Live LibreTranslate container and gateway chat server; tested with httpx MockTransport fake."),
    StatusStep(32, "Remote Access & Pairing", "remote_access", "PARTIAL", "`remote_access/relay_server.py`, `remote_access/tests/test_relay_server.py`", "Real WireGuard kernel tunnel interface; X25519 pairing, ChaCha20-Poly1305, and WebSocket relay verified."),
    StatusStep(33, "Sync", "sync_engine", "PARTIAL", "`sync_engine/core/engine.py`, `sync_engine/tests/test_sync_engine.py`", "Live peer-to-peer network transport across physically separate machines."),
    StatusStep(34, "Component Registry Finishing", "release_finishing", "REAL", "`release_finishing/core/releaser.py`, `release_finishing/tests/test_release_finishing.py`", "Live signed binary CDN distribution."),
]


def generate_status_markdown() -> str:
    lines = [
        "# Pheonix System Implementation Status (Audited)",
        "",
        "*Status Audit Date: October 2026*  ",
        "*Enforcing Rule 4 Status Labels:*",
        "- **`REAL`**: Does the real work and is tested against the real thing.",
        "- **`PARTIAL`**: Real code path exists but only tested with fakes or mocks.",
        "- **`SIMULATED`**: Mock or fake only, no real call.",
        "- **`MISSING`**: Not built.",
        "",
        "---",
        "",
        "## 34-Step Master Architecture Audit Matrix",
        "",
        "| Step | Module | Label | Evidence (File and Test) | What is Missing |",
        "| :---: | :--- | :---: | :--- | :--- |",
    ]

    for item in CANONICAL_STEPS:
        lines.append(
            f"| **{item.step}** | **{item.name}** (`{item.module}`) | **{item.label}** | {item.evidence} | {item.missing} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Auxiliary Components",
        "- **Canvas & Live Artifacts** (`canvas`): **PARTIAL** (Evidence: `canvas/core/canvas.py`, `canvas/tests/test_canvas.py` — tested with in-memory artifacts, live WebSocket collaboration missing).",
        "- **Audit Ledger** (`audit`): **REAL** (Evidence: `audit/ledger.py`, `audit/client.py`, `audit/tests/test_unified_audit.py` — cryptographically chained tamper-evident ledger with cross-module recording and automated verification).",
        "- **Console** (`console`): **SIMULATED** (Evidence: `console/server.py`, `console/index.html`, `console/tests/test_console.py` — local web management console UI preview; endpoints being wired to live service backends).",
        "- **Composer** (`agent_builder/composer`): **PARTIAL** (Evidence: `agent_builder/composer/layout_engine.py`, `agent_builder/composer/app_composer.py`, `agent_builder/tests/test_composer.py` — declarative layout solver and agent composer unit tested with in-memory specifications).",
        "- **Marketplace** (`skills_packaging/marketplace`): **PARTIAL** (Evidence: `skills_packaging/marketplace/catalog.py`, `skills_packaging/marketplace/license.py`, `skills_packaging/tests/test_ecosystem.py` — package discovery, category indexing, and licensing entitlement engine tested with mock catalogs).",
        "- **Migrations** (`storage/migrations`): **REAL** (Evidence: `storage/migrations.py`, `tests/test_schema_migrations_and_tenancy.py` — schema version tracking, automated migration runner, and backward-compatible tenant isolation).",
        "",
    ])



    return "\n".join(lines)


def check_status() -> bool:
    expected = generate_status_markdown().strip()
    actual = STATUS_MD.read_text(encoding="utf-8").strip()

    if expected != actual:
        print("[FAIL] STATUS.md does not match the canonical generated status table!")
        return False

    # Also verify ROADMAP.md statuses match
    roadmap_text = ROADMAP_MD.read_text(encoding="utf-8")
    for step in CANONICAL_STEPS:
        pattern = f"| **{step.step}** |"
        for line in roadmap_text.splitlines():
            if line.startswith(pattern):
                if f"**{step.label}**" not in line:
                    print(f"[FAIL] ROADMAP.md Step {step.step} status does not match canonical label **{step.label}**: {line}")
                    return False
                break

    print("[PASS] STATUS.md and ROADMAP.md are fully synchronized with canonical status.")
    return True


def update_status() -> None:
    content = generate_status_markdown()
    STATUS_MD.write_text(content, encoding="utf-8")
    print(f"[SUCCESS] Updated {STATUS_MD.relative_to(ROOT_DIR)} from canonical status model.")


def main():
    parser = argparse.ArgumentParser(description="Pheonix Status Table Generator & Drift Checker")
    parser.add_argument("--check", action="store_true", help="Check that STATUS.md matches canonical status")
    parser.add_argument("--update", action="store_true", help="Update STATUS.md from canonical status")

    args = parser.parse_args()

    if args.update:
        update_status()
    elif args.check:
        if not check_status():
            sys.exit(1)
    else:
        # Default: check and if drifted, print help
        if not check_status():
            sys.exit(1)


if __name__ == "__main__":
    main()
