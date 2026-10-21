# Pheonix Core Data Rules & Handling Specification
*Directly Derived from [Intelligence (10).txt](file:///d:/pheonix/Intelligence%20%2810%29.txt)*

---

## 1. Core Principles: Local-First & Zero-Leak Invariant

The Pheonix ecosystem is designed around four non-negotiable data rules:
1. **Local-First Processing:** All conversations, vector embeddings, retrieved memory facts, and personal documents reside locally on the user's host by default.
2. **Explicit Consent for Remote Transit:** No user prompt, context window, or document content may leave the local boundary to a third-party cloud provider unless the user explicitly configured and activated that provider route.
3. **No Unauthenticated Telemetry:** Core components must never phone home or send analytical tracking metrics to external endpoints. Telemetry (e.g. Langfuse, Helicone) is strictly self-hosted or user-directed.
4. **Immediate Deletion & Right to Forget:** Memory, vector embeddings, chat logs, and cached outputs must support instant hard deletion by project or item ID.

---

## 2. Data Classification Matrix

| Classification Level | Examples | Storage Location | Encryption Requirement | Ingress / Egress Rules |
|---|---|---|---|---|
| **Class 0: Secrets & Credentials** | API Keys, OAuth tokens, master passphrases, SSH keys. | Encrypted Vault (`vault.enc`) | **AES-256-GCM** (Argon2id KDF). Zero plaintext on disk or in logs. | Egress strictly prohibited except to authenticated target provider endpoint via TLS 1.3. |
| **Class 1: Personal Knowledge & Memories** | Long-term memory facts, vector indices, retrieved context, user files, notes. | Local DB / Vector Store (`facts.db`, Qdrant/Chroma) | At-rest encryption / User filesystem permissions. | Never sent to remote servers except when explicitly injected as prompt context to activated LLM. |
| **Class 2: Ephemeral Operational State** | Request traces, token counts, latency metrics, routing decisions. | In-memory cache / Local SQLite traces | Plaintext local / redacted auth headers. | Stays on host; viewable in personal usage console only. |
| **Class 3: Public Manifests & Rules** | Component registry catalog, routing capability matrix, rule policies. | Public repository files | None (Integrity hashed via SHA-256). | Read-only access by all local subsystems. |

---

## 3. Per-Project Isolation & Namespace Boundaries

* **Multi-Project Scoping:**
  * Every memory entry, agent run, file upload, and vector embedding must be tagged with an immutable `project_id`.
  * Queries and retrieval requests without matching `project_id` must return zero results. Cross-project data bleeding is classified as a security violation.
* **Sandbox Confinement:**
  * Agent code execution in sandboxes (E2B / container / runner) has zero access to host memory databases, secrets vaults, or host network interfaces unless granted by an explicit user permission token.

---

## 4. Memory Retention & Right-to-Forget Protocol
1. **Source Tracking:** Every stored memory fact MUST record its source (`conversation_id`, `document_id`, or `manual_entry`).
2. **Hard Deletion:** When a user requests deletion of a memory item, all derived vector chunks, SQLite fact records, and cached embeddings must be purged immediately (not merely soft-deleted).
3. **Audit Trail:** Deletions emit an auditable event with timestamp and memory ID, confirming complete purge.
