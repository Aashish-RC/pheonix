# Pheonix — Gap-Closing Task List
*Created: Oct 21, 2026 | Assignee: Aashish | Source: Status report gaps*

---

> [!NOTE]
> The model-gateway is **much deeper than initially measured** — 122 TypeScript files with 50+ Vitest tests covering auto-routing, BYOK, budgets, credits, guardrails, MCP, rate limits, streaming, shadow routing, session affinity, GeoIP, SSRF, PII, and more. It is the most complete module in the repo. The gaps below are real but narrower on the gateway side.

---

## Track 1 — Inter-Module Wiring (Most Critical)
*Nothing runs end-to-end until these are done.*

| # | Task | Files to create/edit | Done when |
|---|---|---|---|
| **W1** | Create root `.env.example` listing every env var needed across all modules (API keys, DB URLs, ports, vector store endpoints) | `/.env.example` | `grep -r "os.environ\|os.getenv" .` has no surprise vars |
| **W2** | Create root `requirements.txt` (or `uv` workspace `pyproject.toml`) that pulls in all module dependencies in one `pip install` | `/pyproject.toml` or `/requirements.txt` | `pip install -e ".[all]"` succeeds from repo root |
| **W3** | Wire **auth → vault**: auth session token creation must call vault's key-lease API to store session signing key | `auth/core/session.py` → `vault/` API call | Auth tests pass with vault as the backend key store |
| **W4** | Wire **providers → gateway**: provider activation result (ping status, key lease) must be fed into gateway's capability matrix | `providers/` → `model-gateway/src/routing/capability-matrix.ts` | Activating a provider key makes it selectable in gateway Auto mode |
| **W5** | Wire **gateway → memory**: after every response, gateway must push a memory-write event to the memory engine (conversation record) | `model-gateway/src/telemetry/` → `memory/core/` | After a chat turn, memory stores the exchange retrievably |
| **W6** | Wire **orchestrator → sandboxes**: orchestrator's code-execution step must call the sandbox module's execution API | `orchestrator/engine/dag_runner.py` → `sandboxes/` | A multi-step plan that includes a code step runs it in isolation |
| **W7** | Wire **orchestrator → tools_mcp**: orchestrator tool-call steps must route through the MCP registry's dispatch layer | `orchestrator/` → `tools_mcp/` | An orchestrator plan can call a registered MCP tool |
| **W8** | Wire **guardrails → gateway**: every inbound prompt to the gateway must pass through the guardrails client before dispatch | `model-gateway/src/guardrails/` → Python guardrails client (HTTP or embedded) | A known jailbreak prompt is blocked at the gateway layer |
| **W9** | Wire **guardrails → memory**: memory writes of user input must be checked by guardrails before storing | `memory/core/engine.py` → `guardrails/client.py` | PII in a stored memory is redacted, not stored raw |
| **W10** | Wire **observability → all modules**: each module must emit structured events (latency, errors, cost) to the observability collector | Add `observability` client calls to gateway, memory, orchestrator, agent, serving | Grafana/Langfuse dashboard shows per-module traces |
| **W11** | Wire **recommender → gateway**: gateway's Auto model selection must call the recommender's scoring API | `model-gateway/src/routing/auto-selector.ts` → recommender HTTP endpoint | Auto mode picks the model the recommender scores highest |
| **W12** | Wire **resource_optimizer → orchestrator**: orchestrator must check the optimizer before launching parallel steps | `orchestrator/engine/dag_runner.py` → resource optimizer | A burst of 10 parallel steps is throttled to the optimizer's cap |
| **W13** | Wire **notifications → orchestrator**: when an orchestrator task finishes or needs approval, it fires a notification event | `orchestrator/` → `notifications/` | A finished long-running task shows in the notification inbox |
| **W14** | Write the first **end-to-end integration test** that chains the full path: `.env` loaded → auth login → key stored in vault → provider activated → gateway routes a real call → memory stores the turn → orchestrator runs a 2-step plan | `/tests/integration/test_e2e_core.py` | Test passes green against a real Ollama instance |

---

## Track 2 — Guardrails Expansion (Safety-Critical Launch Blocker)
*370 lines is not enough. This must pass a red-team session before any real user.*

| # | Task | Files to create/edit | Done when |
|---|---|---|---|
| **G1** | Expand `attack_vectors.json` — add at minimum: indirect prompt injection via tool output, multi-turn jailbreak (context builds over several turns), role confusion attacks, Unicode/homoglyph obfuscation, token-smuggling, and base64-encoded instructions | `guardrails/tests/attack_vectors.json` | File has ≥ 60 attack vectors, each with expected action |
| **G2** | Add **multi-turn context guardrail**: accumulate conversation history and re-evaluate the running context, not just the last message | `guardrails/core/context_guard.py` (new) | A jailbreak spread across 3 turns is detected on turn 3 |
| **G3** | Add **tool-output injection detector**: scan tool/connector return values for prompt injection before they are fed back into the model context | `guardrails/core/tool_output_guard.py` (new) | A malicious web-search result that contains `[SYSTEM OVERRIDE]` is flagged |
| **G4** | Expand crisis responses — add: eating disorder, abuse/domestic violence, substance crisis, disaster, and a generic distress fallback. Each response must include a resource link | `guardrails/core/crisis.py` | Each crisis category has a distinct, tested response with a resource |
| **G5** | Add **output guardrail**: scan model responses before they are returned to the user (not just inputs) — detect hallucinated harmful instructions | `guardrails/core/output_guard.py` (new) | A response containing bomb-making steps is blocked post-generation |
| **G6** | Expand test suite to ≥ 50 named test cases covering all attack types, including expected action for each | `guardrails/tests/test_guardrails.py` | CI runs all 50+ cases on every push |
| **G7** | Add **severity levels** (allow / warn / redact / block / crisis) with configurable thresholds per deployment context | `guardrails/models.py`, `engine.py` | Admin can set severity threshold via config; lower environments are stricter |
| **G8** | Add a guardrails **admin audit log**: every block/redact/crisis event is written to an append-only log with timestamp, actor, rule matched, and truncated input | `guardrails/core/audit.py` (new) | Audit log file exists and appends on every non-allow event |

---

## Track 3 — OSS Engine Integration
*Modules reference OSS tools but don't instantiate them. These make the unified layers real.*

| # | Task | Files to create/edit | Done when |
|---|---|---|---|
| **O1** | **Memory / Vector store — Qdrant**: wire `memory/embeddings/qdrant_adapter.py` to a real Qdrant instance; add connection health check on startup | `memory/embeddings/qdrant_adapter.py` | `pytest memory/tests/test_engine.py -k qdrant` passes against a local Qdrant container |
| **O2** | **Model serving — Ollama**: wire `serving/` to a running Ollama instance; expose a `/generate` endpoint that proxies to Ollama with device-profile checks | `serving/core/` | `curl` to serving's `/generate` returns a streamed response from `llama3.2` |
| **O3** | **Web search — Firecrawl**: wire `web_search/core/` to Firecrawl's `/scrape` and `/search` APIs; add a fallback to Crawl4AI if Firecrawl key is absent | `web_search/core/provider.py` | A query returns cited results from at least one provider |
| **O4** | **Sandboxes — E2B**: wire `sandboxes/` to E2B's sandbox API; the execute endpoint must time-box and kill on timeout | `sandboxes/core/` | Running `print(2+2)` in the sandbox returns `4` without escaping the container |
| **O5** | **Browser automation — Browser Use**: wire `browser_automation/` to Browser Use's agent API; add confirmation-required mode for consequential actions (form submit, click "Buy") | `browser_automation/core/` | A browse-to-URL task executes and returns page content; a form-submit asks for approval |
| **O6** | **Notifications — Novu**: wire `notifications/` to Novu's API or run Novu self-hosted; add an in-app inbox channel and an email fallback | `notifications/core/` | A `notify(user_id, "Task done")` call results in a real inbox entry |
| **O7** | **Observability — Langfuse**: wire `observability/` to Langfuse's `/api/public/ingestion` endpoint; emit a trace on every gateway call | `observability/core/tracer.py` | Langfuse UI shows a trace with model, latency, cost, and token counts |
| **O8** | **Search — Typesense/Meilisearch**: wire `search/` to a running Typesense instance; index conversation history and notes | `search/core/` | A search query returns ranked results from indexed conversations |
| **O9** | **Remote access — Tailscale/WireGuard**: wire `remote_access/` to generate a WireGuard config or Tailscale auth key for device pairing | `remote_access/core/` | Two Docker containers pair and exchange encrypted traffic through the relay path |

---

## Track 4 — Test Coverage (Thin Modules)
*Modules with only 1 test file need coverage before Gate 0.*

| # | Task | Target module | Add tests for |
|---|---|---|---|
| **T1** | Vault | `vault/tests/` | Key rotation, tamper detection, concurrent access, revocation cascade, no-plaintext-in-logs invariant |
| **T2** | Auth | `auth/tests/` | Token expiry, invalid credentials, device revocation, concurrent session limit, session replay attack |
| **T3** | Rules | `rules/tests/` | Rule propagation to a consumer module, conflicting rules, rule versioning, rollback |
| **T4** | Providers | `providers/tests/` | Ping failure handling, OAuth token refresh, key missing vs key invalid, provider quarantine after N failures |
| **T5** | Serving | `serving/tests/` | Device-profile enforcement (phone can't run 70B), resource-limit kill, model not found, concurrent requests |
| **T6** | Observability | `observability/tests/` | Missing trace fields, high-volume buffering, cost calculation accuracy, Langfuse write failure graceful degradation |
| **T7** | Storage | `storage/tests/` | Quota enforcement, duplicate file handling, concurrent upload, deletion cascades, version conflict |
| **T8** | Tracker | `tracker/tests/` | Renewal alert timing, key expiry warning, multiple provider tracking, stale-key cleanup |
| **T9** | Guardrails | `guardrails/tests/` | (See Track 2 above — G6 covers this) |
| **T10** | Translation | `translation/tests/` | Unsupported language fallback, gateway provider switch mid-session, glossary injection |
| **T11** | Remote access | `remote_access/tests/` | Pairing rejection, relay fallback, session timeout, revocation mid-session |
| **T12** | Sync engine | `sync_engine/tests/` | Conflict resolution (two devices write same key simultaneously), offline then sync, partial sync failure |
| **T13** | Release finishing | `release_finishing/tests/` | Compatibility block (semver major mismatch), staged rollout percentage, rollback trigger |
| **T14** | Media gen | `media_gen/tests/` | Queue ordering, safety filter blocks a result, provider timeout, multi-format output |
| **T15** | Voice speech | `voice_speech/tests/` | STT language detection, duplex barge-in, synthesis provider fallback, silence timeout |

---

## Track 5 — CI / Dev Setup Hardening

| # | Task | Files | Done when |
|---|---|---|---|
| **C1** | Update `.github/workflows/ci.yml` to install all Python modules (not just `pytest pytest-asyncio fastapi httpx pydantic pyyaml cryptography psutil`) — each module needs its own pip install from its `pyproject.toml` | `ci.yml` | CI green on a fresh Ubuntu runner with no manual pre-install |
| **C2** | Add a `docker-compose.yml` at repo root that spins up: Qdrant, Ollama (CPU image), Novu, Meilisearch, and a local SMTP server — for integration tests locally | `/docker-compose.yml` | `docker compose up -d` + `pytest tests/integration/` passes |
| **C3** | Add a secret-scan step to CI that checks for hardcoded tokens matching known patterns (API key formats) in all files | `ci.yml` — new step using `gitleaks` or `trufflehog` | A commit with a fake `sk-test123...` key fails CI |
| **C4** | Add `pre-commit` hooks: ruff linting, mypy type check (at least on vault, auth, guardrails), and the secret scan | `/.pre-commit-config.yaml` | `pre-commit run --all-files` passes |
| **C5** | Add a GitHub Actions step that verifies every module's `pyproject.toml` has the correct module name, version ≥ 0.1.0, and required deps | `ci.yml` | A malformed `pyproject.toml` fails CI with a named error |
| **C6** | Expand `scripts/test_all.py` to run **all 34 modules** (currently only runs 3: gateway, memory, agent) | `scripts/test_all.py` | Running `python scripts/test_all.py` tests all 34 modules and prints a summary table |

---

## Track 6 — Voice & Media Completion (Wave 8 thin modules)

| # | Task | Files | Done when |
|---|---|---|---|
| **V1** | Wire `voice_speech/stt/dictation_engine.py` to a real Whisper endpoint (local via `faster-whisper` or OpenAI Whisper API) | `voice_speech/stt/` | An audio file uploaded returns a transcript |
| **V2** | Wire `voice_speech/tts/synthesis_engine.py` to a TTS provider (OpenAI TTS or Coqui XTTS locally) | `voice_speech/tts/` | A text string returns playable audio bytes |
| **V3** | Wire `voice_speech/core/duplex/` to LiveKit's Python SDK for real-time full-duplex voice | `voice_speech/core/duplex/` | Two clients can hold a voice conversation via the LiveKit room |
| **V4** | Wire `media_gen/` image route to a real provider (Stability AI via gateway, or a local ComfyUI endpoint) — include safety filter before returning | `media_gen/core/` | An image prompt returns a base64 image that passes the safety filter |
| **V5** | Wire `translation/` to LibreTranslate self-hosted (fallback: gateway call to a model with a translation system prompt) | `translation/core/` | A Spanish string is translated to English without a paid API key |

---

## Summary — Task Count

| Track | Tasks | Priority |
|---|---|---|
| Track 1 — Wiring | 14 | 🔴 Highest — nothing works without this |
| Track 2 — Guardrails | 8 | 🔴 High — launch blocker |
| Track 3 — OSS engines | 9 | 🟠 High — makes layers real |
| Track 4 — Test coverage | 15 | 🟡 Medium — needed before Gate 0 |
| Track 5 — CI / Dev setup | 6 | 🟡 Medium — catches regressions |
| Track 6 — Voice & media | 5 | 🟢 Lower — Wave 8, can follow |
| **Total** | **57 tasks** | |

---

## Suggested Order to Attack

```
W2 (deps) → W1 (.env.example) → C2 (docker-compose) →
W3+W4 (auth+providers wired) → G1+G2+G6 (guardrails expanded) →
O1+O2 (Qdrant+Ollama) → W5+W8 (memory+guardrails into gateway) →
W6+W7 (orchestrator→sandbox+tools) → W14 (first e2e test) →
T1–T8 (thin module tests) → C1+C4+C6 (CI hardening) →
O3–O9 (remaining OSS engines) → W9–W13 (remaining wiring) →
V1–V5 (voice/media) → G3–G5+G7–G8 (guardrails depth) →
C3+C5 (secret scan + manifest check)
```
