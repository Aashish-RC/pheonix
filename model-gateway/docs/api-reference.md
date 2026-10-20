# ra1 Model Gateway — API Reference & Quick Cheat-Sheet

The ra1 Model Gateway provides an OpenAI-compatible unified API that transparently maps to OpenAI, Anthropic Claude, Google Gemini, Amazon Bedrock, and local runtimes (Ollama, llama.cpp, LocalAI) with built-in resilience, virtual routing tiers, streaming failover, and telemetry.

Default Base URL: `http://localhost:4000`

---

## Table of Contents
1. [Chat Completions (`/v1/chat/completions`)](#1-chat-completions)
2. [Anthropic Native Messages (`/v1/messages`)](#2-anthropic-native-messages)
3. [Legacy Completions (`/v1/completions`)](#3-legacy-completions)
4. [Embeddings (`/v1/embeddings`)](#4-embeddings)
5. [Reranking for RAG (`/v1/rerank`)](#5-semantic-reranking)
6. [Token Counting (`/v1/tokenize`)](#6-token-counting)
7. [Image Generations & Edits (`/v1/images/*`)](#7-image-generations--edits)
8. [Audio Speech & Transcriptions (`/v1/audio/*`)](#8-audio-speech-tts--transcriptions-stt)
9. [Video Generations (`/v1/videos/generations`)](#9-video-generations)
10. [Realtime Voice Sessions (`/v1/realtime/sessions`)](#10-realtime-voice-sessions)
11. [Batch Processing (`/v1/batches`)](#11-batch-processing)
12. [Files & Fine-Tuning (`/v1/files`, `/v1/fine_tuning/jobs`)](#12-files--fine-tuning)
13. [Observability & Health (`/metrics`, `/health/*`)](#13-observability--health-probes)
14. [Control Console (`/console`)](#14-embedded-control-console)

---

### 1. Chat Completions
`POST /v1/chat/completions`

#### Unary Completion (Virtual Smart Tier)
```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "smart-tier",
    "messages": [
      { "role": "system", "content": "You are a concise engineering assistant." },
      { "role": "user", "content": "Explain dual stream failover in two sentences." }
    ],
    "temperature": 0.7
  }'
```

#### Streaming Completion (Server-Sent Events)
```bash
curl -N -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "fast-tier",
    "messages": [{ "role": "user", "content": "Stream a count from 1 to 5." }],
    "stream": true
  }'
```

---

### 2. Anthropic Native Messages
`POST /v1/messages`

```bash
curl -X POST http://localhost:4000/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-7-sonnet",
    "max_tokens": 1024,
    "messages": [{ "role": "user", "content": "Hello Claude!" }]
  }'
```

---

### 3. Legacy Completions
`POST /v1/completions`

```bash
curl -X POST http://localhost:4000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "prompt": "The future of distributed model gateways is",
    "max_tokens": 50
  }'
```

---

### 4. Embeddings
`POST /v1/embeddings`

```bash
curl -X POST http://localhost:4000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-3-small",
    "input": "High performance vector search across hybrid models"
  }'
```

---

### 5. Semantic Reranking
`POST /v1/rerank`

```bash
curl -X POST http://localhost:4000/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rerank-v1",
    "query": "Which database offers sub-millisecond vector indexing?",
    "documents": [
      "PostgreSQL with pgvector provides standard vector similarity search.",
      "Dedicated in-memory vector databases deliver sub-millisecond ANN lookups.",
      "Relational databases excel at ACID compliant transactions."
    ],
    "top_k": 2
  }'
```

---

### 6. Token Counting
`POST /v1/tokenize`

```bash
curl -X POST http://localhost:4000/v1/tokenize \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "text": "Preflight token calculation prevents surprise billings."
  }'
```

---

### 7. Image Generations & Edits
`POST /v1/images/generations`

```bash
curl -X POST http://localhost:4000/v1/images/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Futuristic cloud model gateway server room in neon cyan",
    "n": 1,
    "size": "1024x1024"
  }'
```

---

### 8. Audio Speech (TTS) & Transcriptions (STT)

#### Text-to-Speech (TTS)
```bash
curl -X POST http://localhost:4000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{
    "model": "tts-1",
    "input": "Gateway initialized successfully.",
    "voice": "alloy"
  }' --output gateway-status.mp3
```

#### Speech-to-Text (STT)
```bash
curl -X POST http://localhost:4000/v1/audio/transcriptions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "whisper-1",
    "audio": "UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
  }'
```

---

### 9. Video Generations
`POST /v1/videos/generations`

```bash
# 1. Submit video generation job
curl -X POST http://localhost:4000/v1/videos/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "An autonomous drone flying through a digital canyon",
    "duration_seconds": 5
  }'

# 2. Poll job status
curl -X GET http://localhost:4000/v1/videos/{video_id}
```

---

### 10. Realtime Voice Sessions
`POST /v1/realtime/sessions`

```bash
curl -X POST http://localhost:4000/v1/realtime/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "modalities": ["text", "audio"],
    "voice": "alloy",
    "temperature": 0.8
  }'
```

---

### 11. Batch Processing
`POST /v1/batches`

```bash
# 1. Create async batch job
curl -X POST http://localhost:4000/v1/batches \
  -H "Content-Type: application/json" \
  -d '{
    "input_file_id": "file-dataset-99",
    "endpoint": "/v1/chat/completions",
    "completion_window": "24h"
  }'

# 2. Check batch status
curl -X GET http://localhost:4000/v1/batches/{batch_id}
```

---

### 12. Files & Fine-Tuning
`POST /v1/files`

```bash
# 1. Upload training dataset
curl -X POST http://localhost:4000/v1/files \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "train_data.jsonl",
    "purpose": "fine-tune",
    "bytes": 20480
  }'

# 2. Start fine-tuning job
curl -X POST http://localhost:4000/v1/fine_tuning/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "training_file": "file-xxx"
  }'
```

---

### 13. Observability & Health Probes

```bash
# Prometheus exposition metrics
curl -X GET http://localhost:4000/metrics

# Kubernetes liveness probe
curl -X GET http://localhost:4000/health/liveness

# Kubernetes readiness probe
curl -X GET http://localhost:4000/health/readiness
```

---

### 14. Embedded Control Console
Navigate in browser to:
`http://localhost:4000/console`
or
`http://localhost:4000/public`
