# Pheonix — Actionable Engineering Task Backlog
*Repository Workspace: `D:\pheonix`*  
*Target: Resolve all architectural, wiring, engine, testing, and operational gaps*

---

## Prerequisite Task: Version Control Checkpoint

- [ ] **Task 0.1: Commit and Push Current Local State**
  - **Context:** `D:\pheonix` contains 25 modified files and 14 untracked files (e.g. `.env.example`, `docker-compose.yml`, guardrail security classes, `test_e2e_core.py`) not yet synced to GitHub.
  - **Action:**
    ```bash
    git add -A
    git commit -m "feat(core): complete initial wiring pass, e2e pipeline test, and guardrails expansion"
    git push origin main
    ```
  - **Done When:** Working tree is clean and `git status` reports up to date with `origin/main`.

---

## Track 1: Inter-Module Wiring & Communication

- [ ] **Task 1.1: Guardrails Pre-Write Filter for Memory Store**
  - **Target:** `memory/engine.py`, `memory/core/engine.py`
  - **Action:**
    - Import `GuardrailsClient` from `guardrails.client`.
    - Intercept all calls in `store()`, `_store_working()`, and `_consolidate_to_facts()`.
    - Run `guardrails.check(prompt=user_text)`.
    - If action is `redact`, store the sanitized content.
    - If action is `block` or `crisis_intervention`, reject insertion with `SecurityPolicyViolationError` and log to audit.
  - **Done When:** Writing a text with API keys or SSNs stores `[REDACTED_...]` in memory, and an adversarial prompt raises an exception without touching the vector or fact store.

- [ ] **Task 1.2: Cross-Module Observability Telemetry Injection**
  - **Target:**
    - `model-gateway/src/telemetry/tracing.ts`
    - `orchestrator/engine/dag_runner.py`
    - `memory/engine.py`
    - `serving/core/engine.py`
  - **Action:**
    - Define unified telemetry schema: `trace_id`, `span_id`, `module`, `operation`, `duration_ms`, `status_code`, `token_usage`, `cost_usd`.
    - Add hooks emitting traces on every LLM generation, DAG step transition, and memory retrieval.
    - Connect emitter to fallback local JSONL logger and remote Langfuse/OpenLLMetry collectors.
  - **Done When:** Triggering a multi-step task generates synchronized trace logs detailing latency and token metrics across gateway, orchestrator, and memory.

- [ ] **Task 1.3: Gateway Dynamic Recommender Hook**
  - **Target:** `model-gateway/src/routing/auto-selector.ts`, `recommender/`
  - **Action:**
    - Replace mock heuristic in `auto-selector.ts` with an HTTP/RPC client querying the recommender service at `RECOMMENDER_SERVICE_URL`.
    - Pass user tier, query task classification, latency sensitivity, and budget.
    - Receive recommended provider/model tuple with reasoning string.
  - **Done When:** Vitest test in `model-gateway/tests/auto-routing.test.ts` asserts that `autoSelectModel()` returns the model selected by the recommender endpoint.

---

## Track 2: Guardrails & Trust Hardening

- [ ] **Task 2.1: Crisis Intervention Taxonomy Completion**
  - **Target:** `guardrails/core/crisis.py`, `guardrails/tests/attack_vectors.json`
  - **Action:**
    - Ensure dedicated detection patterns and verified response messages (with official helpline URLs/hotlines) exist for:
      1. Self-harm / suicide
      2. Domestic violence / abuse
      3. Substance abuse / overdose
      4. Severe eating disorders
      5. Active crisis / disaster trauma
    - Add 15 corresponding regression vectors into `attack_vectors.json`.
  - **Done When:** `pytest guardrails/tests/test_guardrails.py` passes with explicit assertions verifying each crisis category triggers its dedicated intervention message.

- [ ] **Task 2.2: Dynamic Configurable Severity Thresholds**
  - **Target:** `guardrails/core/engine.py`, `guardrails/models.py`
  - **Action:**
    - Implement threshold parser reading `GUARDRAILS_SEVERITY_THRESHOLD` (`allow`, `warn`, `redact`, `block`, `strict`).
    - In `strict` mode, escalate `warn` to `block`.
    - Provide a programmatic method on `GuardrailsEngine.set_severity_threshold()`.
  - **Done When:** A prompt evaluated under `warn` passes with warnings, but evaluating the exact prompt under `strict` returns `action="block"`.

---

## Track 3: Real Open-Source Engine Adapters

- [ ] **Task 3.1: Firecrawl & Crawl4AI Real Scraper Adapter**
  - **Target:** `web_search/core/provider.py`, `web_search/pyproject.toml`
  - **Action:**
    - Implement `FirecrawlClient` connecting to `https://api.firecrawl.dev` (or self-hosted) using `FIRECRAWL_API_KEY`.
    - Implement local fallback adapter using `crawl4ai` when key is absent.
    - Extract clean Markdown and synthesize source citation metadata (`url`, `title`, `snippet`).
  - **Done When:** Executing `web_search.search("python latest release")` returns parsed web content and populated citations.

- [ ] **Task 3.2: E2B Cloud & Docker Local Sandbox Execution**
  - **Target:** `sandboxes/core/`, `sandboxes/manager.py`
  - **Action:**
    - Implement `E2BExecutionEngine` using `e2b-code-interpreter`.
    - Implement local Docker container executor as offline fallback.
    - Enforce execution timeout via `SANDBOX_TIMEOUT_SECONDS` (default: 30s) and memory caps (512MB).
  - **Done When:** Running a script that attempts `while True: pass` is killed after 30 seconds with `SandboxTimeoutError`, while valid code returns `stdout`.

- [ ] **Task 3.3: Browser Use Automation Adapter**
  - **Target:** `browser_automation/core/agent.py`
  - **Action:**
    - Integrate `browser-use` library controlling headless Playwright Chromium.
    - Add security interceptor callback: pause and yield confirmation request if DOM action matches buttons like `Submit`, `Delete`, `Pay`, `Confirm`.
  - **Done When:** Browser agent can open a page, extract text, and pauses execution waiting for approval when encountering an input form submission.

- [ ] **Task 3.4: Novu In-App & Multi-Channel Notification Integration**
  - **Target:** `notifications/core/dispatcher.py`
  - **Action:**
    - Wire `NovuBackend` to trigger events via `@novu/node` or Novu REST API (`POST /v1/events/trigger`).
    - Add local mock inbox repository for running without external Novu cloud dependency.
  - **Done When:** Calling `notify(user_id="u1", event="task_completed")` writes to the user's notification feed.

- [ ] **Task 3.5: Langfuse Observability Exporter**
  - **Target:** `observability/core/tracer.py`
  - **Action:**
    - Implement `LangfuseExporter` connecting via `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`.
    - Map gateway spans and generation tokens to Langfuse API payload format.
    - Ensure background async flush so model generation is never blocked by telemetry timeouts.
  - **Done When:** Running `test_e2e_core.py` successfully sends trace batches to the Langfuse mock/endpoint without latency penalty.

- [ ] **Task 3.6: Meilisearch Global Search Indexer**
  - **Target:** `search/core/index.py`, `search/core/ingestion.py`
  - **Action:**
    - Wire client to `MEILISEARCH_URL` using `MEILISEARCH_MASTER_KEY`.
    - Create schemas and indexes for `conversations`, `notes`, and `artifacts`.
    - Subscribe to memory write events to update index documents in real time.
  - **Done When:** Adding a conversation turn makes it queryable via `search.query("needle")` within 500ms.

- [ ] **Task 3.7: WireGuard & Relay Path Selection in Remote Access**
  - **Target:** `remote_access/core/pairing.py`, `remote_access/core/relay.py`
  - **Action:**
    - Implement cryptographic key-exchange handshake generating client WireGuard configuration files.
    - Implement path probe logic: Attempt direct connection → attempt local LAN ping → fallback to WebSocket encrypted relay.
  - **Done When:** Remote access tests simulate NAT failure and verify transparent fallback to the relay channel.

---

## Track 4: Module Test Suites Expansion

- [ ] **Task 4.1: Vault Security & Concurrency Tests**
  - **Target:** `vault/tests/test_vault.py`
  - **Tests to Add:** Key rotation, file tampering detection, 20 concurrent threads accessing leases without deadlock, automatic lease expiration, zero plaintext in audit dumps.

- [ ] **Task 4.2: Auth Session Hardening Tests**
  - **Target:** `auth/tests/test_auth.py`
  - **Tests to Add:** Token expiry boundaries, device blacklisting, concurrent session enforcement (max 5 sessions per user), replay attack rejection.

- [ ] **Task 4.3: Rules Engine Propagation Tests**
  - **Target:** `rules/tests/test_rules.py`
  - **Tests to Add:** Dynamic rule propagation to running agents, conflicting rule resolution, rule version rollback.

- [ ] **Task 4.4: Providers Quarantine & Recovery Tests**
  - **Target:** `providers/tests/test_providers.py`
  - **Tests to Add:** Automatic quarantine of provider after 3 failed pings, token refresh failure handling, key reactivation.

- [ ] **Task 4.5: Storage Quota & Deduplication Tests**
  - **Target:** `storage/tests/test_storage.py`
  - **Tests to Add:** Hard quota rejection, SHA-256 deduplication on identical uploads, atomic file deletion.

- [ ] **Task 4.6: Tracker Renewal & Expiry Tests**
  - **Target:** `tracker/tests/test_tracker.py`
  - **Tests to Add:** Expiry countdown triggers, multi-account license aggregation, expired key purge.

- [ ] **Task 4.7: Voice, Media & Translation Edge Case Tests**
  - **Target:** `voice_speech/tests/`, `media_gen/tests/`, `translation/tests/`
  - **Tests to Add:** Duplex barge-in state transition, generation safety blocking, language fallback on unsupported locale.

---

## Track 5: Developer Tooling & CI Hardening

- [ ] **Task 5.1: Upgrade CI Workflow for Monorepo Dep Resolution**
  - **Target:** `.github/workflows/ci.yml`
  - **Action:** Replace hardcoded `pip install ...` line with `pip install -e ".[all]"`.
  - **Done When:** GitHub Actions builds a matrix job across Python 3.11 & 3.12 without missing dependency errors.

- [ ] **Task 5.2: Secret Leak Scanning in CI**
  - **Target:** `.github/workflows/ci.yml`
  - **Action:** Add `gitleaks-action` or `trufflehog` step to scan repository commits for leaked API tokens.
  - **Done When:** Pushing a mock key `sk-proj-1234567890abcdef1234567890` fails the CI check.

- [ ] **Task 5.3: Pre-commit Hook Suite**
  - **Target:** `/.pre-commit-config.yaml`
  - **Action:** Configure `ruff` (formatting & linting), `mypy` (type-checking on `vault`, `auth`, `guardrails`), and trailing whitespace cleaners.
  - **Done When:** `pre-commit run --all-files` runs cleanly.

- [ ] **Task 5.4: Complete All-Module Test Runner**
  - **Target:** `scripts/test_all.py`
  - **Action:** Add the remaining 17 modules to the test execution sequence and format output into an aligned terminal matrix.
  - **Done When:** `python scripts/test_all.py` runs all 34 modules and reports individual test counts, durations, and status.

---

## Track 6: Wave 8 Capabilities (Voice & Media Engines)

- [ ] **Task 6.1: Faster-Whisper Local STT Adapter**
  - **Target:** `voice_speech/stt/dictation_engine.py`
  - **Action:** Integrate `faster-whisper` for local CPU/GPU speech-to-text with auto-punctuation and timestamp extraction.
  - **Done When:** Sending a 5-second `.wav` file yields matching transcript text.

- [ ] **Task 6.2: TTS Audio Synthesis Engine**
  - **Target:** `voice_speech/tts/synthesis_engine.py`
  - **Action:** Integrate Coqui TTS / OpenAI TTS client returning streaming audio chunks (`audio/wav`, `audio/mp3`).
  - **Done When:** Calling `synthesize("Hello world")` produces non-empty audio byte buffer.

- [ ] **Task 6.3: LiveKit Real-Time Full-Duplex Voice Session**
  - **Target:** `voice_speech/duplex/voice_session_runner.py`
  - **Action:** Integrate LiveKit Python RTC client to connect to voice rooms with VAD (Voice Activity Detection) and barge-in cancellation.
  - **Done When:** Incoming microphone audio automatically silences ongoing bot TTS playback.

- [ ] **Task 6.4: Image Route Safety & Generation Pipe**
  - **Target:** `media_gen/core/image_route.py`
  - **Action:** Connect to Stability AI / local ComfyUI API and wrap generation through `guardrails.core.output_guard`.
  - **Done When:** Generating a prompt produces an image; prompt containing forbidden content returns safety error.

- [ ] **Task 6.5: Offline Machine Translation Adapter**
  - **Target:** `translation/core/engine.py`
  - **Action:** Add adapter for local LibreTranslate container with automatic language detection and caching.
  - **Done When:** `translate("Bonjour", target="en")` returns `"Hello"`.
