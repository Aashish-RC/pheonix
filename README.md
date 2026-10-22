# Pheonix Core

Pheonix is a local-first, zero-trust AI operating ecosystem unifying intelligence, agency, sandboxing, and autonomous developer workflows.

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node.js 20+ & pnpm
- Docker & Docker Compose (for local containerized backends)

### Environment Configuration
Copy the example environment configuration:
```bash
cp .env.example .env
```

---

## Starting Docker Services

Pheonix leverages containerized local infrastructure for vector storage, search, local LLM inference, and gateway routing.

To start all services in the background:
```bash
docker compose up -d
```

To start only the core infrastructure services:
```bash
docker compose up -d qdrant ollama meilisearch model-gateway
```

To pull the default lightweight local LLM into Ollama:
```bash
docker compose exec ollama ollama pull llama3.2:1b
```

Check running container status:
```bash
docker compose ps
```

---

## Running Tests

### Unified Test Suite
Run the automated test suite across all 35 modules (Python and TypeScript):
```bash
python scripts/test_all.py
```
Or using pnpm / npm:
```bash
pnpm test
```

### Module-Specific Tests
To run tests for an individual module:
```bash
# Python module tests
python -m pytest <module_name>/tests -q

# Example: Guardrails test suite
python -m pytest guardrails/tests -q

# Example: Model Gateway (TypeScript / Vitest)
cd model-gateway && pnpm test
```

### Red-Team Regression
Run the guardrails red-team test suite:
```bash
python guardrails/tests/redteam_runner.py
```

---

## Status Labels

Every component and implementation step in Pheonix adheres to strict, objective status labels:

| Label | Meaning |
|---|---|
| **`REAL`** | Does the real work and is tested against the real thing. No core functionality is mocked. |
| **`PARTIAL`** | Real code path exists, but is tested with fakes/mocks, or live verification is pending external service execution. |
| **`SIMULATED`** | Mock or fake only; no real calls or external backends are invoked. |
| **`MISSING`** | Not built yet. |

> [!NOTE]
> For a complete 34-step breakdown of every module, evidence files, test coverage, and current gaps, refer to [STATUS.md](STATUS.md).

---

## Architecture & Planning

- [STATUS.md](STATUS.md): Current implementation status and evidence for all ecosystem modules.
- [ROADMAP.md](ROADMAP.md): Architecture roadmap and component domains.
- [docs/planning/](docs/planning/): Planning blueprints, parity register, and ecosystem specifications:
  - `V1-product-ecosystem-plan.md`
  - `User-built-AI-app-ecosystem-with-shared-components.md`
  - `Intelligence (10).txt`
  - `proprietary_and_oss_alternatives_directory.xlsx`
- [docs/security/](docs/security/): Threat model, data handling rules, and red-team plan.
