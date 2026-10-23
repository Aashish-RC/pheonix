# Pheonix — GitHub Codespaces Run Guide

This manual walks you step-by-step through running the Pheonix project in **GitHub Codespaces**. 

Running in Codespaces executes the entire stack inside a dedicated Linux cloud virtual machine with a native Docker daemon, completely bypassing local Windows Docker Desktop freezes and RAM exhaustion.

---

## 1. Launching GitHub Codespaces

1. Open the repository on GitHub: [https://github.com/Aashish-RC/pheonix](https://github.com/Aashish-RC/pheonix)
2. Click the green **`<> Code`** button.
3. Switch to the **Codespaces** tab.
4. Click the three dots (**`...`**) next to the Codespace creation button and select **"New with options..."**:
   - **Branch:** `main`
   - **Devcontainer configuration:** `Pheonix Development Environment`
   - **Machine type:** Choose **4-core** (or 8-core) to ensure adequate memory for Ollama, Qdrant, Meilisearch, and Node.
5. Click **Create codespace**.

> [!TIP]
> Codespaces will load in your browser (or in local VS Code if connected via the GitHub Codespaces extension).

---

## 2. Environment Initialization

The pre-configured [devcontainer.json](file:///.devcontainer/devcontainer.json) automatically runs the setup script upon launch.

If you ever need to rerun or verify the environment manually in the Codespaces terminal:

```bash
# 1. Ensure environment file exists
cp -n .env.example .env

# 2. Install Python ecosystem in editable mode
pip install -e ".[all]"

# 3. Install Model Gateway Node dependencies
pnpm --dir model-gateway install
```

---

## 3. Starting Infrastructure Services (Docker)

Codespaces has Docker and Docker Compose installed natively.

### Start All Services:
```bash
docker compose up -d
```

### Start Only Core Services (Resource-friendly):
If you want to conserve memory, launch only the core services:
```bash
docker compose up -d qdrant ollama meilisearch model-gateway
```

### Check Container Status:
```bash
docker compose ps
```

### Pull Local LLM Model (Ollama):
To enable offline local model inference without remote API keys:
```bash
docker compose exec ollama ollama pull llama3.2:1b
```
*(Or use `tinyllama` for minimal RAM usage).*

---

## 4. Running the Test Suite

### Unified Suite (All 35 Modules + Gateway):
```bash
python scripts/test_all.py
```

### Module-Specific Python Tests:
```bash
# Guardrails suite
python -m pytest guardrails/tests -q

# Memory subsystem suite
python -m pytest memory/tests -q

# Orchestrator suite
python -m pytest orchestrator/tests -q

# Red-team regression benchmark
python guardrails/tests/redteam_runner.py
```

### TypeScript Model Gateway Tests:
```bash
pnpm --dir model-gateway test
```

---

## 5. Accessing Forwarded Web Services & APIs

Codespaces automatically forwards exposed ports to public/private preview URLs. You can find them under the **Ports** tab in the VS Code bottom panel:

| Port | Service | Description |
|---|---|---|
| **`4000`** | Model Gateway | High-performance routing & OpenAI-compatible proxy |
| **`6333`** | Qdrant | Vector database REST API & dashboard |
| **`7700`** | Meilisearch | Fast search engine endpoint |
| **`8025`** | Mailpit Web UI | In-browser test email inbox (local SMTP mock) |
| **`11434`** | Ollama | Local LLM inference server |
| **`3001`** | Novu | Notification server |

To open any service in your browser, hover over the port row in the **Ports** tab and click the **Globe / Open in Browser** icon.

---

## 6. Stopping and Managing Codespaces

- When you close your browser tab, Codespaces pauses automatically after 30 minutes of inactivity to preserve your free monthly hours.
- To explicitly stop the containers and save resources before exiting:
  ```bash
  docker compose down
  ```
- To manage or delete running codespaces at any time, visit: [https://github.com/codespaces](https://github.com/codespaces).
