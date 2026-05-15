# Release Note — DeepPool v1.0.0

**Release Date**: May 15, 2026

We are excited to announce the first open-source release of **DeepPool** — an AI Orchestration Gateway & Token Governance Platform!

DeepPool provides a unified access layer for large language models. With a single API endpoint and a single API Key, you can call GPT, Claude, DeepSeek, Qwen, GLM, and other leading LLMs worldwide, along with intelligent routing, guardrails, usage tracking, quality evaluation, and comprehensive token governance.

---

## Highlights

### Multi-Model Orchestration, Unified Gateway
Access dozens of LLMs through a single OpenAI-compatible API endpoint (`/v1/chat/completions`). Supports three model sources — DeepNode local inference, cloud Provider APIs, and Hybrid orchestration — completely transparent to callers. Zero-modification SDK integration with existing OpenAI SDKs.

### Custom Orchestration Policies
Define Hybrid routing rules via YAML configuration with intelligent dispatching by context length, Function Call, vision content, reasoning requirements, etc. Round-Robin load balancing + automatic failover.

### Request Tracing, AI Evaluation & Analysis
Complete inference request/response logging, human annotation feedback & expected output, AI Judge auto-evaluation of model output quality, data-driven continuous optimization.

### Guardrails — Safety Guardrails
LLM-based input/output content safety evaluation, pre-request interception and post-response auditing, configurable block or log-only policies, ensuring AI application security and compliance.

### DeepNode Local Inference
Download and install the DeepNode desktop client, deploy open-source models like Qwen, Gemma with one click, leverage local GPU/Apple Silicon for inference compute, data stays on-device.

---

## Feature List

#### Gateway Core
- OpenAI API fully compatible interface (`/v1/chat/completions`, `/v1/models`)
- Streaming SSE support
- Function Calling support (Registry-architecture ToolCallParser for GLM/Kimi/DeepSeek/Qwen/Gemma4/Llama/Mistral)
- Reasoning Content support (DeepSeek R1 / Qwen3 `reasoning_content`)
- Three-tier model classification: `deepnode` / `provider` / `hybrid`
- Request pipeline: Auth → RateLimit → Quota → Guardrails(Input) → Route → Inference → Guardrails(Output) → Trace

#### Authentication & Rate Limiting
- API Key authentication (SHA-256 hash)
- Sliding window RPM/TPM rate limiting
- Token quota management
- AES-256-GCM API Key encryption at rest

#### Hybrid Intelligent Orchestration
- YAML-configured conditional routing rules
- Request feature extraction (input tokens, tool count, vision, reasoning)
- Round-Robin load balancing with atomic counter rotation
- Automatic failover across candidates
- PolicyCache with 10s DB polling for hot-reload
- Anti-recursion protection

#### Guardrails
- LLM-driven input/output safety evaluation
- Dual-phase guardrails (input interception + output audit)
- Block and log-only action policies
- Automatic streaming disable when output guardrails enabled
- 15s evaluation timeout with 1 retry
- Async result storage

#### Tracing & AI Evaluation
- TraceMatcher in-memory cache with periodic refresh
- TraceWriter async best-effort write to external DB (MySQL/PostgreSQL/ClickHouse)
- AI Judge auto-evaluation (Experiment service)
- Human annotation feedback & expected output
- Complete request/response logging

#### Token Governance
- Usage statistics by API Key / model / time dimensions
- Cost analysis and tiered billing
- Quota management

#### DeepNode Desktop Client
- Tauri 2.0 (Rust) native shell + Vue 3 UI
- Device fingerprint generation (cross-platform hardware feature collection → SHA-256)
- Multi-engine inference: MLX (Apple Metal), vLLM (NVIDIA CUDA), llama.cpp (CPU)
- Auto engine selection based on platform and hardware
- HuggingFace model download with mirror support
- gRPC bidirectional stream tunnel to NodeManager
- Auto-reconnect with exponential backoff
- Credential persistence and auto-recovery on restart

#### Platform Backend
- Go 1.23, zero-framework stdlib `net/http`
- gRPC (unary + bidirectional streaming)
- MySQL 8 with idempotent auto table creation
- Database migration scripts with `update_db.sh`
- Unified `deploy.sh` with SSL, Nginx, health check
- One-click `dev.sh` for local development

#### Web Frontend
- Admin Dashboard (`control_web`) — Vue 3 + TDesign + Pinia + Tailwind CSS
- User Portal (`portal_web`) — Vue 3 + TDesign + markdown-it + vue-i18n

#### Security
- Parameterized queries (SQL injection prevention)
- bcrypt password hashing
- AES-256-GCM API Key encryption
- SHA-256 device fingerprint
- Input validation and path traversal protection

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Platform Backend | Go 1.23, stdlib `net/http`, gRPC |
| Database | MySQL 8 (InnoDB, utf8mb4_unicode_ci) |
| Serialization / RPC | Protocol Buffers 3, gRPC |
| Cryptography | bcrypt, AES-256-GCM, SHA-256 |
| Admin Frontend | Vue 3 + TDesign + Pinia + Tailwind CSS |
| Portal Frontend | Vue 3 + TDesign + markdown-it + vue-i18n |
| Desktop Client | Tauri 2.0 (Rust) + Vue 3 + TypeScript |
| Local Inference | Python 3.13, FastAPI + uvicorn, grpcio |
| Inference Engines | MLX (Apple Metal), vLLM (CUDA), llama.cpp (CPU) |
| Function Call | Registry-architecture ToolCallParser |
| Model Management | HuggingFace Hub (with mirror support) |

---

## Project Structure

```
DeepPool/
├── libs/                          # Shared protocol layer (Protobuf + generated code)
├── platform/                      # Platform backend + Web frontend
│   ├── cmd/                       #   Service entries (manager, nodemanager, experiment)
│   ├── internal/                  #   Business logic (handler/service/repository/gateway)
│   ├── config/                    #   YAML config files
│   ├── control_web/               #   Admin dashboard (Vue 3 + TDesign)
│   ├── portal_web/                #   User portal (Vue 3 + TDesign)
│   └── deploy.sh                  #   Unified deployment script
├── clients/
│   └── deepnode/                  # DeepNode desktop client
│       ├── app/                   #   Frontend UI (Vue 3 + TypeScript)
│       ├── src-tauri/             #   Tauri 2.0 native layer (Rust)
│       └── localserver/           #   Local inference service (Python 3.13 + FastAPI)
├── build.sh                       # Full build script
├── dev.sh                         # Dev mode launcher
└── go.work                        # Go Workspace
```

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/BiyoTech/Public-DeepPool.git
cd DeepPool

# 2. Prepare database
mysql -u root -p -e "CREATE DATABASE deeppool CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 3. Configure
vim platform/config/manager.yaml   # Set MySQL connection info

# 4. One-click start
./dev.sh all
```

Verify:

```bash
curl http://localhost:8080/api/v1/health
# {"code":0,"message":"ok","data":{"status":"healthy"}}
```

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

```
Copyright 2024-2026 DeepPool Team (Shenzhen Biyo Technology Co., Ltd.)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

<p align="center">
  <sub>Built with ❤️ by the DeepPool Team</sub>
</p>
