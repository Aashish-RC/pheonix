# Pheonix Localhost Run Manual

This guide explains how to install the monorepo, start its local infrastructure, and run its separately-available APIs on your own computer.

## What you will be running

Pheonix is a monorepo of Python components and a TypeScript model gateway, with a unified web management console and optional modular microservices. The root Docker Compose file starts infrastructure and the model gateway. The Pheonix Unified Console provides an interactive web dashboard for conversation, live canvas, prompt tuning, telemetry, and audit inspection.

| Service | How it starts | Local address |
|---|---|---|
| Pheonix Unified Console | `python console/server.py` or uvicorn | `http://localhost:8080` |
| Model Gateway | Root Docker Compose, or run from `model-gateway/` | `http://localhost:4000` |
| Qdrant vector database | Root Docker Compose | `http://localhost:6333` |
| Ollama local model server | Root Docker Compose | `http://localhost:11434` |
| Meilisearch | Root Docker Compose | `http://localhost:7700` |
| Novu API | Root Docker Compose | `http://localhost:3001` |
| Novu WebSocket | Root Docker Compose | `http://localhost:3002` |
| Novu dashboard | Root Docker Compose | `http://localhost:3005` |
| Mailpit SMTP test inbox | Root Docker Compose | `http://localhost:8025` (SMTP: `localhost:1025`) |
| Memory REST API | Start manually (optional) | `http://localhost:8001` |
| Agent REST API | Start manually (optional) | `http://localhost:8002` |
| Model-serving REST API | Start manually (optional) | `http://localhost:8003` |

The remaining component directories (for example `auth/`, `guardrails/`, `orchestrator/`, `search/`, and `workflow_builder/`) are Python packages with their own tests; they are not separate web servers in the root Compose stack. See [STATUS.md](../STATUS.md) for the component-by-component implementation inventory.

## 1. Prerequisites

Install:

- Git
- Python 3.12 or newer (the project metadata declares Python 3.10 as its minimum)
- Node.js 20 or newer and pnpm
- Docker Engine with the Docker Compose plugin, if you want the containerized services

The root Compose file publishes ports `3001`, `3002`, `3005`, `4000`, `6333`, `6334`, `7700`, `8025`, `1025`, and `11434`. Make sure those ports are available. The optional Python APIs use ports `8001`-`8003`.

## 2. Get the code and install dependencies

From a terminal:

```bash
git clone https://github.com/Aashish-RC/pheonix.git
cd pheonix
```

Create and activate a virtual environment, then install the root Python package and optional integrations:

```bash
python -m venv .venv
source .venv/bin/activate              # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[all]"
```

Install the Model Gateway's Node dependencies:

```bash
pnpm --dir model-gateway install
```

The checked-in `.env.example` is a configuration template containing placeholder credentials and development defaults. It is not required for the basic local setup and its example keys are not real provider credentials. Do not use those defaults for a deployed or publicly exposed service. Python processes do not automatically load `.env`; export any values they need in the shell where you start them.

The Novu API, worker, WebSocket, and dashboard use Novu's supported self-hosted images with MongoDB and Redis. Compose supplies development-only secrets by default; set `NOVU_MONGO_PASSWORD`, `NOVU_JWT_SECRET`, `NOVU_STORE_ENCRYPTION_KEY` (exactly 32 characters), and `NOVU_SECRET_KEY` in `.env` before using the stack beyond local development. The dashboard is on port `3005` so it does not conflict with the Model Gateway on port `4000`.

## 3. Start the local infrastructure and gateway

From the repository root, start the core development services:

```bash
docker compose up -d qdrant ollama meilisearch model-gateway
docker compose ps
```

The root Compose file also defines Novu and Mailpit. Start every defined service, including those optional services, with:

```bash
docker compose up -d
```

For a local model, download the small Ollama model used by the gateway's local alias:

```bash
docker compose exec ollama ollama pull llama3.2:1b
```

The model download can take a while and needs an internet connection. The gateway container is configured to reach Ollama at `http://ollama:11434` on the Compose network. The first model request may take longer while Ollama loads the model.

Check service health:

```bash
curl -fsS http://localhost:4000/health
curl -fsS http://localhost:11434/api/tags
curl -fsS http://localhost:6333/healthz
curl -fsS http://localhost:7700/health
```

If a particular health URL is not supported by the installed image version, use `docker compose ps` and `docker compose logs <service>` to check that service.

Try a chat completion through the gateway using the local model:

```bash
curl -sS http://localhost:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "llama3.2:1b",
    "messages": [{"role": "user", "content": "Reply with: Pheonix is running"}],
    "stream": false
  }'
```

The gateway also exposes `GET /v1/models`. Cloud model routes require real provider credentials. The root Compose service currently does not pass the root `.env` provider keys through to the gateway container. To use a cloud provider, either configure the gateway service's environment in `docker-compose.yml`, or run the gateway on the host with the required provider key exported and the appropriate provider base URL.

### Run the gateway on the host instead of in Docker

Use this option if you want to set provider credentials in your shell. Do not start the `model-gateway` Compose service at the same time, because both modes use port `4000`:

```bash
docker compose up -d qdrant ollama meilisearch
pnpm --dir model-gateway build
export PORT=4000
export OLLAMA_BASE_URL=http://localhost:11434
# Optional, only if using a cloud provider:
export OPENAI_API_KEY=your-real-key
pnpm --dir model-gateway start
```

The gateway listens on `http://localhost:4000`. For other providers, export that provider's real key and any required custom base URL before starting it. In PowerShell, use `$env:PORT = "4000"`, `$env:OLLAMA_BASE_URL = "http://localhost:11434"`, and `$env:OPENAI_API_KEY = "your-real-key"` instead of `export`.

## 4. Run the Pheonix Unified Console & Optional APIs

### Pheonix Unified Console & Web Dashboard

Pheonix includes a built-in web management console with live canvas, conversational core, instruction tuner, owner telemetry, and tamper-evident audit ledger.

**How to start the Console:**

From the repository root (with virtual environment active):

```bash
python console/server.py
```
Or via uvicorn:
```bash
python -m uvicorn console.server:app --host 127.0.0.1 --port 8080 --reload
```

Open `http://localhost:8080` in your web browser.

**What to check to verify it works:**

1. **Header & Module Health**: Check the top-right status pulse indicating `36 Modules Healthy` (queried live from `/api/health`).
2. **Conversational Core (`#nav-btn-chat`)**: Type a message (e.g. `Analyze security audit log`) and click **Dispatch** or press Enter. Verify the message bubble renders along with verified tool chips (`vault:load_credentials`).
3. **Live Canvas (`#nav-btn-canvas`)**: Click the **Live Canvas** tab in the sidebar. Click **Run / Update** (`#btn-canvas-render`); verify that the HTML/CSS markup in the editor executes and renders immediately inside the sandboxed preview iframe (`#canvas-iframe`).
4. **Prompt Assistant (`#nav-btn-prompt`)**: Click **Prompt Assistant**, modify or keep the draft instruction, and click **Optimize Prompt** (`#btn-optimize-prompt`). Verify the synthesized few-shot system prompt appears in the output pane via `/api/prompt/optimize`.
5. **Owner Console (`#nav-btn-owner`)**: Click **Owner Console**. Check the live telemetry cards: Module Health (`36 / 36`), Automated Tests Verified (`658+`), and click **Check Channel Updates** (`#btn-check-updates`).
6. **Audit Ledger (`#nav-btn-audit`)**: Click **Audit Ledger** to view recent tamper-evident hash-chained events.
7. **Multi-Tenant & Role Switcher**: In the sidebar footer, switch the **Tenant Scope** (`Enterprise Alpha`, `R&D Lab`, `Sandbox Demo`) and **Active Role** (`Owner`, `Admin`, `Member`, `Auditor`).

---

### Optional Python APIs

Open a separate terminal for each optional API, activate `.venv` in that terminal, and run the command from the indicated directory. Bind to `127.0.0.1` for local-only access.

### Memory API


```bash
cd memory
python -m uvicorn server.app:app --host 127.0.0.1 --port 8001 --reload
```

Visit `http://localhost:8001/docs` for interactive API documentation. Its defaults use in-memory working memory, SQLite facts, local embeddings, and in-memory Qdrant; it does not require the root Qdrant container for a basic smoke test. The service creates its local database/WAL data relative to its working directory.

Check it and optionally store a sample memory:

```bash
curl -fsS http://localhost:8001/health
curl -sS http://localhost:8001/api/v1/remember \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"local-user","text":"I am testing Pheonix locally","session_id":"manual-test"}'
```

### Agent API

```bash
cd agent
MODEL_GATEWAY_URL=http://127.0.0.1:4000 \
python -m uvicorn server.api:app --host 127.0.0.1 --port 8002 --reload
```

On Windows PowerShell, set the variable first with `$env:MODEL_GATEWAY_URL = "http://127.0.0.1:4000"`, then run the `python -m uvicorn ...` command. Setting the gateway URL is useful when an agent needs model inference; the module's default is port `8000`, while the root Compose gateway listens on port `4000`.

Open `http://localhost:8002/docs`. A simple health check and template listing do not require a model provider:

```bash
curl -fsS http://localhost:8002/health
curl -fsS http://localhost:8002/agents/templates
```

### Model-serving API

From the repository root:

```bash
python -m uvicorn serving.server:app --host 127.0.0.1 --port 8003 --reload
```

Open `http://localhost:8003/docs`. This API is a separate serving component; starting the root Compose stack does not start it.

## 5. Run tests

The repository's unified runner executes the component test suites, including the TypeScript gateway tests. Run it from the repository root with the Python virtual environment active and gateway dependencies installed:

```bash
python scripts/test_all.py
```

For a focused check:

```bash
python -m pytest memory/tests -q
python -m pytest agent/tests -q
pnpm --dir model-gateway test
```

Most tests use local fakes or mocks and do not require the Compose services. The audited scope and live-integration gaps are described in [STATUS.md](../STATUS.md).

## 6. Stop services

Stop the root Compose services from the repository root:

```bash
docker compose down
```

This stops and removes the containers but preserves named data volumes, including downloaded Ollama models and database data. Stop manually launched Python servers with `Ctrl+C` in their terminals.

## Troubleshooting and safety

- **A port is already in use:** Stop the other service using it, or change the corresponding port mapping/command before starting Pheonix.
- **Gateway health works but generation fails:** Confirm the model was pulled (`docker compose exec ollama ollama list`), wait for it to load, and check `docker compose logs model-gateway ollama`.
- **Cloud inference fails:** Configure a real provider API key for the process/container running the gateway. Placeholder values in `.env.example` will not authenticate.
- **A Python module import fails:** Confirm the root package was installed into the active virtual environment and run the API command from its module directory as shown above.
- **Container errors:** Inspect `docker compose logs <service>`; use `docker compose logs -f <service>` to follow logs.

These Compose settings are for development: ports are published on host interfaces, and some services use development credentials or have no application authentication. Run them only on a trusted machine/network and do not expose them directly to the public internet. Keep real credentials out of source control.
