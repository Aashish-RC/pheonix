# Key Store & Core System Threat Model
*Specification for Pheonix Trust & Operations Foundation*
*Target Component: Key Store & Secrets (Wave 1, Step 2)*

---

## 1. System Context & Objective
The Pheonix ecosystem provides an autonomous intelligence layer requiring access to third-party model provider keys (OpenAI, Anthropic, Gemini, Mistral, Eden AI), OAuth tokens, vector database credentials, and local encryption keys. 

**Primary Security Mandate:** 
> **Zero Plaintext Invariant:** Cryptographic secrets and API credentials must NEVER appear in plaintext on disk, in unencrypted memory dumps, in system traces, logs, git repositories, or in outgoing client telemetry.

---

## 2. Threat Classification & Attack Vectors

| Threat ID | Threat Vector | Description | Severity | Mitigation Strategy |
|---|---|---|---|---|
| **THREAT-01** | **Disk Persistence Leak** | Storing API keys or access tokens in plaintext `.env` files, SQLite tables, or cache files accessible via local file read. | **CRITICAL** | Per-user AES-256-GCM envelope encryption with Argon2id key derivation. No keys persisted unencrypted to SQLite or flat files. |
| **THREAT-02** | **Memory Inspection / Dump** | Secrets lingering in runtime heap memory after usage, accessible to core dumps, swap files, or memory scanning malware. | **HIGH** | Ephemeral decrypted buffers wiped/zeroized (`memzero`) immediately post-usage. Secure memory allocators where available. |
| **THREAT-03** | **Process Environment Snooping** | Exposing master secrets via `process.env` or `os.environ`, readable by child processes, rogue subprocesses, or debuggers. | **HIGH** | Strict ban on passing raw provider secrets through global process environment variables. Keys are resolved on-demand per request. |
| **THREAT-04** | **Subprocess / Sandbox Escape** | Malicious or untrusted code executed in agent sandboxes attempting to read local credential stores or loopback APIs. | **CRITICAL** | Network namespace isolation, strict filesystem containerization, loopback firewalling, and permission gates (Always Ask mode). |
| **THREAT-05** | **Logging & Telemetry Exfiltration** | Tracing libraries (Langfuse, OpenLLMetry, Sentry, Pino/Console) inadvertently logging authorization headers or payload keys. | **HIGH** | Centralized redaction filter (`Bearer ***`, `sk-***`) intercepting all outbound loggers and telemetry exporters. |
| **THREAT-06** | **Credential Compromise & Replay** | Stolen client session token used to issue unauthorized agent or model gateway calls. | **MEDIUM** | Ephemeral cryptographically signed sessions (HMAC/Ed25519) with per-device binding and immediate revocation lists. |

---

## 3. Cryptographic Design Principles

### 3.1 Key Derivation Function (KDF)
* **Algorithm:** Argon2id
* **Parameters:**
  * Memory: 64 MB minimum
  * Iterations (Time cost): 3 passes
  * Parallelism: 4 lanes
  * Salt: 32 bytes cryptographically secure random (`os.urandom(32)` / `crypto.randomBytes(32)`), generated per user vault.

### 3.2 Envelope Encryption Architecture
```
User Passphrase / Hardware Key
             │
             ▼ (Argon2id)
     Key Encryption Key (KEK)
             │
             ├── Encrypts ──► Data Encryption Key (DEK) [AES-256-GCM]
                                        │
                                        └── Encrypts ──► Provider Secrets / Tokens
```
* **Master Key (KEK):** Held only in active session memory; never persisted.
* **Data Encryption Key (DEK):** Encrypted with KEK and stored in encrypted vault header.
* **Cipher:** AES-256-GCM with authenticated tag validation (128-bit authentication tag) and unique 96-bit IV per secret entry.

---

## 4. Key Lifecycle & Revocation
1. **Enrollment:** User enters provider key; ping-test verifies validity against upstream API; key is encrypted and stored in vault.
2. **Access:** Component requests temporary credential with token lifetime <= 60 seconds; memory zeroized after request completion.
3. **Revocation:** 
   - Immediate tombstone marker in vault index.
   - Associated active sessions purged.
   - Upstream credential verification marks provider as inactive across gateway routing tables.
