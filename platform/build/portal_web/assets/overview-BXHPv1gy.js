const e=`# Architecture Overview

## Overall Architecture

DeepPool uses a Gateway-centric microservice architecture with unified API entry and multi-backend routing:

\`\`\`
                         ┌─────────────┐
                         │  Caller      │
                         │ (OpenAI SDK) │
                         └──────┬──────┘
                                │ HTTP (Bearer API Key)
                                ▼
              ┌──────────────────────────────────────┐
              │         Manager + Gateway             │
              │                                      │
              │  Auth → RateLimit → Quota → Route    │
              │       ┌──────────┬──────────┐        │
              │       ▼          ▼          ▼        │
              │  ┌─────────┐ ┌────────┐ ┌────────┐  │
              │  │DeepNode │ │Provider│ │ Hybrid │  │
              │  │ (gRPC)  │ │ (HTTP) │ │(Smart  │  │
              │  └────┬────┘ └───┬────┘ │Dispatch│  │
              │       │          │      │+Failovr│  │
              │       │          │      └────────┘  │
              └───────┼──────────┼──────────────────┘
                      │          │
           ┌──────────┘          └──────────┐
           ▼                                ▼
    ┌──────────────┐              ┌─────────────────┐
    │ NodeManager  │              │   Cloud API      │
    │ Shard Hub    │              │ OpenAI / Qianfan │
    │ Least-Conn   │              └─────────────────┘
    └──────┬───────┘
           │ gRPC BidiStream
           ▼
    ┌──────────────┐
    │   DeepNode   │
    │ (Edge Device)│
    │ MLX/vLLM/cpp │
    └──────────────┘
\`\`\`

## Component Responsibilities

### Manager + Gateway

Manager is the platform core, embedding an OpenAI-compatible inference gateway:

- **User Management** — Registration, login, token auth
- **Model Registry** — Three types (DeepNode / Provider / Hybrid) model CRUD
- **API Key Management** — SHA-256 auth, AES-256-GCM encrypted storage, RPM/TPM rate limiting, quota management
- **Gateway Routing** — Auto-route based on model \`vendor_type\` to DeepNode (gRPC), Provider (HTTP proxy), or Hybrid (smart dispatch)
- **Device Management** — Device registration, auto/manual model assignment

### NodeManager

NodeManager manages all online device gRPC long connections:

- **256-Shard ConnectionHub** — FNV-1a hashing, O(1) lookup, supports millions of connections
- **Heartbeat Patrol** — 10s interval checks, 30s timeout auto-eviction
- **Least-Connections Scheduling** — Select lowest-load device, round-robin tie-breaking
- **gRPC BidiStream Tunnel** — Registration, heartbeat, task dispatch, result return over a single TCP connection

### DeepNode

Desktop client application (Tauri + Vue 3 + Python), deployed on provider devices:

- **Hardware Detection** — Auto-detect GPU model, memory size
- **Model Download** — Auto-download from HuggingFace Hub (domestic mirror acceleration)
- **Multi-Engine Inference** — MLX (Apple Metal), vLLM (CUDA), llama.cpp (CPU)
- **Tunnel Connection** — gRPC bidirectional stream, NAT traversal, exponential backoff reconnect

## Two-Layer Scheduling Architecture

Inference requests go through two scheduling layers:

\`\`\`
Layer 1 — Gateway (Model-level)
  Route based on vendor_type:
  · DeepNode → gRPC to NodeManager
  · Provider → HTTP proxy to cloud API
  · Hybrid → Condition matching + Round-Robin + Failover

Layer 2 — NodeManager (Device-level)
  Select among online devices:
  · Least Connections strategy
  · Round-robin tie-breaking to avoid thundering herd
\`\`\`

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Platform Backend | Go 1.23, stdlib \`net/http\`, gRPC |
| Database | MySQL 8 (InnoDB, utf8mb4) |
| Protocol | Protocol Buffers 3, gRPC BidiStream |
| Desktop Client | Tauri 2.0 (Rust) + Vue 3 + TypeScript |
| Inference Service | Python 3.13, FastAPI, grpcio |
| Inference Engines | MLX, vLLM, llama.cpp |
| Cryptography | bcrypt, AES-256-GCM, SHA-256 |
`;export{e as default};
