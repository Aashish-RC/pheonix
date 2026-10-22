# Pheonix Master Architecture & Execution Roadmap
*Directly Derived from [Intelligence (10).txt](file:///d:/pheonix/docs/planning/Intelligence%20%2810%29.txt)*

---

## 1. Architectural Strategy & Design System

The Pheonix core framework implements a two-option strategy for every layer:
* **Option 1 (Pure Custom):** Built natively from scratch to enforce strict zero-trust, clean abstractions, and zero upstream baggage.
* **Option 2 (Unified Layer):** A unified abstraction layer whose sub-branches plug into vetted open-source engines (OSS) and/or custom implementations, bound together by strict custom routing, telemetry, and security policies.

---

## 2. Functional Domains & Component Catalog (32 Core Modules)

### Domain A: Intelligence (10 Components)
| Component | Option | Sub-Branches & Source Candidates | Custom Built Scope |
|---|---|---|---|
| **Model Gateway** | Opt 2 | LiteLLM, Portkey AI Gateway, Bifrost, Envoy AI Gateway. Connectors: OpenRouter, Requesty, Eden AI. | Capability matrix, Auto-selection with one-line reason, fallback policy, manual override. |
| **Model Serving** | Opt 2 | Runtimes: Ollama, llama.cpp, GPT4All, LocalAI. | Device profiles, model download/storage, resource limiters. |
| **Memory & Retrieval** | Opt 2 | Memory manager: Mem0, Letta. Vector: Milvus, Qdrant, Chroma, Weaviate. Hybrid: Typesense. | Storage filter policies, memory-sources view, edit/delete, per-project scope. |
| **Knowledge & Docs** | Opt 2 | Notes/Docs: Memos, Outline, AppFlowy, Affine, Joplin. Grounded notebooks: Open-Notebook. | Direct linking of knowledge notes into unified memory/retrieval pipeline. |
| **Voice & Speech** | Opt 2 | Real-time voice: LiveKit, Dograh. Dictation: Handy, OpenWispr, FluidVoice, VoiceInk, Amical. | Voice-mode behavior, turn-taking, audio streaming pipes. |
| **Media Generation** | Opt 2 | Gateway connectors (Eden AI, image/video/audio routes). | Generation queue, templates, results gallery, safety filters. |
| **Guardrails & Safety** | Opt 1 | Pure Custom. | Rule set, automated test suite of known bad cases, notices, crisis responses. |
| **Rules Layer** | Opt 1 | Pure Custom. | Centralized rule format, cross-component distribution, enforcement hooks. |
| **Recommender** | Opt 1 | Pure Custom (References: Router, Requesty, OpenRouter; Telemetry: Langfuse, Helicone). | Usage-based auto-scoring, second-opinion verification rule. |
| **Resource Optimizer** | Opt 2 | Telemetry: Prometheus, NetData. Rate limits/Balancing: LiteLLM, Bifrost. Queues: Temporal, Trigger, Inngest. | Throttling policy, device-load awareness, adaptive concurrency. |

### Domain B: Agency (10 Components)
| Component | Option | Sub-Branches & Source Candidates | Custom Built Scope |
|---|---|---|---|
| **Orchestrator** | Opt 2 | Durable execution: Temporal, Trigger, Hatchet, Inngest. Scheduled/event: Kestra, Prefect. | Multi-step planner, parallel fan-out/fan-in, approvals & stop, budget/cost checks. |
| **Agent Builder** | Opt 2 | Agent definition: Langflow, Flowise, Parlant, Botpress, Typebot. Prompt management: Agenta. | Describe-to-agent generator, rules binding, system prompt synthesis. |
| **Agent Execution & Sandboxes** | Opt 2 | Agent runtimes: OpenClaw, Hermes Agent, NanoClaw, Suna, Omnigent. Sandboxes: E2B, OpenComputer. | Sandbox policy, device runner, execution containment. |
| **Internal Agents** | Opt 1 | Pure Custom (built atop the core layers). | Provider-health agent, guardrail-review agent, resource-monitoring agents. |
| **Workflow Builder** | Opt 2 | Engine & canvas: n8n, Kestra, ActivePieces, Windmill, Automatisch. | Describe-to-workflow generator, orchestration handoff. |
| **Tool & MCP Registry** | Opt 2 | Connector auth & sync: Nango, ACI.dev. Fine-grained access: Cerbos, Permify. | Curated catalog, request queue, idle-until-needed lazy-loading. |
| **Web Search & Scraping** | Opt 2 | Crawl/Scrape: Firecrawl, Crawl4AI, Maxun. Search aggregation: Swirl Search, OpenSERP. | Source-support validator, citation synthesizer. |
| **Browser Automation** | Opt 2 | Browser agents: Browser Use, Skyvern, ego lite, Browser Operator. Infrastructure: Lightpanda, Steel. | User confirmation rules, sandboxed headless/headful profiles. |
| **Skills & Plugin Packaging** | Opt 1 | Pure Custom. | Skill manifest format, plugin packager, sandboxed loader. |
| **Permission Modes** | Opt 1 | Pure Custom. | 3 distinct security tiers: Always ask, Ask on changes, Auto-review. |

### Domain C: Trust & Operations (8 Components)
| Component | Option | Sub-Branches & Source Candidates | Custom Built Scope |
|---|---|---|---|
| **Key Store & Secrets** | Opt 1 | Pure Custom (References: HashiCorp Vault, Infisical, KeePassXC, Bitwarden, Passbolt). | Encrypted per-user zero-leak store, key rotation, revocation engine. |
| **Auth & Identity** | Opt 1 | Pure Custom (References: Keycloak, Better Auth, Logto, Ory, Hanko). | Single-user local sign-in, device pairing, session management. |
| **Provider Activation** | Opt 1 | Pure Custom. | Key / OAuth entry, automated ping test, periodic health recheck. |
| **Subscription & Key Tracker** | Opt 1 | Pure Custom (References: Maybe, Actual, Firefly III). | Plans, quotas, renewal dates, active status dashboard. |
| **Observability & Evals** | Opt 2 | Tracing: Langfuse, Phoenix, OpenLLMetry, Helicone. Evals: Latitude, Agenta. Dashboards: Grafana, SigNoz. Errors: Sentry. | Personal usage & cost view, local privacy-respecting metrics. |
| **Component Registry & Update Channel** | Opt 2 | Staged rollout: Unleash, GrowthBook, Flagsmith, Flipt. | Version manifest, changelog, compatibility validator, export packaging. |
| **Remote Access & Pairing** | Opt 2 | Direct & mesh: Tailscale, Netbird, FireZone, WireGuard. Remote: RustDesk. | Relay service, path selector, pairing, end-to-end encryption. |
| **Sync** | Opt 2 | File sync: Nextcloud, Seafile, OpenCloud, ownCloud. | Cross-device state sync for chats, memory, and configuration. |

### Domain D: Shared Services (4 Components)
| Component | Option | Sub-Branches & Source Candidates | Custom Built Scope |
|---|---|---|---|
| **Storage & Files** | Opt 2 | Object store: MinIO, Ceph, Garage. File library: Spacedrive, Filestash. Cloud drive: Nextcloud, OpenCloud. | Library model, per-project quotas, sharing, export. |
| **Notifications** | Opt 2 | Engines: Novu, Listmonk, Dittofeed. | Unified inbox, routing rules, quiet-hours scheduler. |
| **Translation** | Opt 2 | Engines: LibreTranslate, Weblate, Lingo.dev, Tolgee, Languine. | Auto-translate gateway middleware. |
| **Global Search** | Opt 2 | Search index: Elasticsearch, Meilisearch, Typesense, OpenSearch, Quickwit. Semantic: Qdrant. Cross-source: Onyx, Pipeshub. | Unified multi-index query engine, unified permissions and scopes. |

---

## 3. Current Baseline Audit in `d:\pheonix`

An inspection of the workspace reveals three existing directories:
1. `model-gateway`: TypeScript/Node gateway with LiteLLM/provider abstractions and tests.
2. `memory`: Python memory engine with tiered storage (hot/warm/cold), SQLite facts, and API server.
3. `agent`: Python agent framework with builder, executor, sandbox, and guardrail scaffolding.

**Gaps to address before proceeding:**
* No unified root project orchestrator (shared configuration, root CI, monorepo scripts).
* No centralized Key Store & Secrets vault (currently credentials run via raw `.env` files).
* No native Auth & Identity system.
* No Component Registry v0 managing dependency versions, compatibility rules, or manifest definitions.

---

## 4. Master 8-Wave Execution Roadmap (34 Steps)

### Wave 1: Foundations (19 Days)
*Goal: Ensure keys are stored safely and all components are formally versioned and verifiable.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **1** | **Repo, CI, Test Harness, Threat Model & Data Rules** | Opt 1 | Nothing | Unified workspace harness, CI scripts, key-store threat model, and data handling rules. | Fresh clone builds in one command (`pnpm/python run all:test`), data rules documented and approved. | **REAL** |
| **2** | **Key Store and Secrets** | Opt 1 | Step 1 | Per-user encrypted key vault (AES-GCM/Argon2id), secure memory wiping, key rotation & revocation engine. | Keys never appear in plaintext anywhere in logs, traces, or disk. | **REAL** |
| **3** | **Auth and Identity** | Opt 1 | Step 2 | Single-user local sign-in, cryptographic session management, device signature binding. | You can sign in locally, inspect active sessions and registered device keys. | **REAL** |
| **4** | **Component Registry v0** | Opt 2 | Step 1 | Version manifest schema, changelog generator, semantic compatibility rules engine. | An incompatible or corrupt update is blocked with an explicit diagnostic reason. | **REAL** |

---

### Wave 2: Rules and Model Access (28 Days)
*Goal: A prompt runs against any activated provider (local or remote) with usage tracked and rules enforced.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **5** | **Rules Layer, Minimal** | Opt 1 | Step 4 | Universal rule schema, event hooks, and propagation protocol to client modules. | A single rule update propagates to all connected apps/modules immediately. | **REAL** |
| **6** | **Provider Activation** | Opt 1 | Step 2 | Key/OAuth credential onboarding, automated ping test, background health re-check. | A revoked or depleted provider key immediately transitions to inactive. | **PARTIAL** |
| **7** | **Model Gateway Integration** | Opt 2 | Step 6 | Integrate routing engine, capability matrix, custom Auto with one-line reason, fallback cascades, and external routes. | A prompt succeeds across any activated provider with automatic fallback. | **PARTIAL** |
| **8** | **Model Serving** | Opt 2 | Step 7 | Local runtime adapter (Ollama/llama.cpp), hardware detection profiles, RAM/VRAM resource limits. | A local quantized model completes inference completely offline. | **PARTIAL** |
| **9** | **Observability, Basic** | Opt 2 | Step 7 | Token usage logging, cost estimator, privacy-respecting personal usage dashboard. | Logged metrics match exact upstream provider billing counts. | **PARTIAL** |

---

### Wave 3: Protect and Store (14 Days)
*Goal: Real users are protected by automated guardrails, and persistent files are managed with quotas.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **10** | **Guardrails and Safety v0** | Opt 1 | Steps 5, 7 | Curated rule set, automated test harness of known attack vectors, notices, crisis response handler. | All known bad cases are blocked in automated CI testing. | **REAL** |
| **11** | **Subscription & Key Tracker** | Opt 1 | Steps 6, 9 | Subscription plans, quota alerts, renewal dates, and active key monitoring. | Active keys, quotas, and renewal countdowns are clearly listed. | **REAL** |
| **12** | **Storage and Files** | Opt 2 | Step 3 | Storage engine adapter (MinIO/local FS), file library model, per-project storage quotas. | Files can be uploaded, indexed, reused across projects, and quota-enforced. | **PARTIAL** |

---

### Wave 4: Knowledge (28 Days)
*Goal: The intelligence brain reliably remembers and grounds answers from local files and the web.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **13** | **Memory and Retrieval** | Opt 2 | Steps 7, 12 | Vector store integration (Qdrant/Chroma), memory manager (Mem0/facts engine), sources view, edit/delete controls. | Memory recalls context with citation, and items can be inspected and deleted. | **PARTIAL** |
| **14** | **Knowledge and Docs** | Opt 2 | Step 13 | Notes and documents engine, source-grounded notebook linking into memory. | Generated answers cite local documents and notebook entries. | **PARTIAL** |
| **15** | **Global Search** | Opt 2 | Steps 13, 14 | Keyword index (Typesense/Meilisearch), semantic search, unified multi-source query planner. | A single query searches across chats, files, notes, and memory simultaneously. | **PARTIAL** |
| **16** | **Web Search and Scraping** | Opt 2 | Steps 7, 10 | Crawl and scrape adapter (Firecrawl/Crawl4AI), search aggregator, citation validator. | Agent outputs cite verified, live external web sources. | **PARTIAL** |

---

### Wave 5: Control and Orchestration (35 Days)
*Goal: Multi-step, parallel tasks run safely within strict resource, sandbox, and permission constraints.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **17** | **Resource Optimizer** | Opt 2 | Steps 8, 9 | System telemetry signals, rate-limit awareness, dynamic queue & concurrency caps. | Host system remains completely responsive even under peak model inference load. | **PARTIAL** |
| **18** | **Permission Modes** | Opt 1 | Step 5 | 3-mode security policy engine: "Always ask", "Ask on changes", "Auto-review". | Each mode predictably gates or permits privileged actions. | **REAL** |
| **19** | **Orchestrator** | Opt 2 | Steps 7, 17, 18 | Custom multi-step planner, parallel fan-out/fan-in, pause/resume, human approval gate, cost checks. | A complex multi-step parallel workflow executes, reports status, and halts on command. | **REAL** |
| **20** | **Agent Execution & Sandboxes** | Opt 2 | Steps 18, 19 | Isolated code sandbox (Docker/Wasm/E2B), runtime container, device runner. | Untrusted code executes cleanly without escaping sandbox limits. | **PARTIAL** |

---

### Wave 6: Tools and Agents (27 Days)
*Goal: Curated tools, MCP connectors, and autonomous internal agents function smoothly with smart routing.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **21** | **Tool and MCP Registry** | Opt 2 | Steps 2, 18, 19 | Curated catalog, idle-until-needed lazy loader, connector auth (Nango), request queue. | A tool asks for credentials only at the instant it is invoked. | **PARTIAL** |
| **22** | **Internal Agents** | Opt 1 | Steps 19, 20, 21 | Provider-health agent, guardrail-evaluator agent, resource-monitoring agent. | Background maintenance agents run autonomously with full audit logs. | **REAL** |
| **23** | **Recommender, Full** | Opt 1 | Steps 9, 21 | Empirical performance scoring from usage telemetry, automated second-opinion rule. | Auto model/tool selections systematically outperform manual picks on benchmark test suite. | **REAL** |
| **24** | **Browser Automation** | Opt 2 | Steps 18, 20, 21 | Browser agent engine (Browser Use), headless browser profile, confirmation policy. | Browser agent navigates workflows and pauses for confirmation before sensitive actions. | **SIMULATED** |

---

### Wave 7: Builders (24 Days)
*Goal: Users can assemble customized agents and multi-step workflows using plain language descriptions.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **25** | **Agent Builder** | Opt 2 | Steps 5, 19, 20, 21 | Agent definition schema, describe-to-agent compiler, dynamic rules binding. | A plain English prompt generates a fully configured, functional agent. | **REAL** |
| **26** | **Workflow Builder** | Opt 2 | Steps 19, 25 | Workflow graph canvas/engine, describe-to-workflow synthesis, orchestrator dispatcher. | A described workflow compiles and executes cleanly via the orchestrator. | **REAL** |
| **27** | **Skills & Plugin Packaging** | Opt 1 | Steps 4, 21, 25 | Portable skill manifest format, cryptographic packaging, hot-reload installer. | A custom skill or plugin packages, installs, and runs in isolated runtime. | **REAL** |

---

### Wave 8: Reach and Finishing (53 Days)
*Goal: Multi-channel reach, voice, media, sync, remote pairing, and production release distribution.*

| Step | Component | Opt | Needs First | Build First | Done When (Verification Gate) | Status |
|:---:|---|---|---|---|---|:---:|
| **28** | **Notifications** | Opt 2 | Step 19 | Unified notification inbox, channel dispatchers (Web/Desktop/Email), quiet hours rule. | A completed asynchronous background task sends a timely alert. | **PARTIAL** |
| **29** | **Voice and Speech** | Opt 2 | Steps 7, 12 | Local/streamed dictation engine (Whisper), real-time conversational voice pipeline (LiveKit). | User can hold a low-latency voice conversation with the system. | **PARTIAL** |
| **30** | **Media Generation** | Opt 2 | Steps 7, 10, 12, 19 | Image route, audio route, video route, generation queue, safety checks. | A generated image or audio file renders and passes automated safety filters. | **SIMULATED** |
| **31** | **Translation** | Opt 2 | Step 7 | Auto-translation gateway middleware, multi-language detection. | Toggle button translates conversational sessions on-the-fly. | **SIMULATED** |
| **32** | **Remote Access & Pairing** | Opt 2 | Steps 2, 3 | Cryptographic device pairing, end-to-end encrypted relay, mesh network routing. | A paired external client securely connects to the host machine across networks. | **SIMULATED** |
| **33** | **Sync** | Opt 2 | Steps 3, 12, 13, 32 | Settings sync, conversation history sync, distributed vector memory sync. | Two paired nodes maintain deterministic consistency. | **PARTIAL** |
| **34** | **Component Registry Finishing** | Opt 2 | Steps 4, and all | Production update channel, staged rollout controller, user-app export packager. | An exported user application updates strictly when its underlying components update. | **REAL** |

