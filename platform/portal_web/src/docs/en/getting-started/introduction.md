# Introduction to DeepPool

## What is DeepPool?

DeepPool is an **AI Orchestration Gateway & Token Governance Platform**. It provides a unified access layer for large language models — with a single API endpoint and a single API Key, you can call GPT, Claude, DeepSeek, Qwen, GLM, and other leading LLMs worldwide, along with intelligent routing, guardrails, usage tracking, quality evaluation, and comprehensive token governance.

## Core Capabilities

- 🔀 **Multi-Model Orchestration, Unified Gateway** — Access dozens of LLMs through a single API endpoint. Supports three model sources — DeepNode local inference, cloud Provider APIs, and Hybrid orchestration — completely transparent to callers
- 🎯 **Custom Orchestration Policies** — Define Hybrid routing rules via YAML configuration with intelligent dispatching by context length, Function Call, vision content, reasoning requirements, etc. Round-Robin load balancing + automatic failover
- 📊 **Request Tracing, AI Evaluation & Analysis** — Complete inference request/response logging, human annotation feedback & expected output, AI Judge auto-evaluation of model output quality, data-driven continuous optimization
- 🛡️ **Guardrails** — LLM-based input/output content safety evaluation, pre-request interception and post-response auditing, configurable block or log-only policies, ensuring AI application security and compliance
- 🖥️ **DeepNode Local Inference** — Download and install the DeepNode desktop client, deploy open-source models like Qwen, Gemma with one click, leverage local GPU/Apple Silicon for inference compute, data stays on-device

## More Features

- **OpenAI API Fully Compatible** — Standard `/v1/chat/completions` interface, supports streaming SSE, Function Calling, Reasoning Content, zero-modification SDK integration
- **API Key + Rate Limiting + Quota** — SHA-256 authentication, sliding window RPM/TPM rate limiting, Token quota management, AES-256-GCM key encryption
- **Token Usage Governance** — Usage statistics, cost analysis, tiered billing by API Key / model / time dimensions
- **Multi-Inference Engine Support** — MLX (Apple Metal), vLLM (CUDA), llama.cpp (CPU), auto-detect and select optimal engine
- **gRPC Bidirectional Stream Tunnel** — Single TCP long connection carrying registration/heartbeat/task/result, easy NAT traversal
- **Security Design** — Parameterized queries, bcrypt password hashing, Token authentication, input validation

## Model Three-Tier Classification

DeepPool categorizes models into three vendor types, the foundation of intelligent routing:

| Type | Description | Routing |
|------|-------------|---------|
| **DeepNode** | Edge device local inference (Qwen, Gemma, etc.) | Gateway → gRPC → NodeManager → Device Tunnel |
| **Provider** | Cloud API proxy (OpenAI, Claude, DeepSeek, etc.) | Gateway → HTTP Proxy → Cloud API |
| **Hybrid** | Multi-model orchestration combining sub-models | Conditional Routing + Round-Robin + Auto Failover |

## Gateway Capability Matrix

| Capability | Description |
|-----------|-------------|
| **Orchestration** | Unified access to DeepNode / Provider / Hybrid model sources with intelligent routing |
| **Custom Policies** | YAML-configured conditional routing rules, dispatch by request characteristics to optimal sub-model |
| **Trace** | Complete inference request/response logging, filterable by API Key, model, time |
| **AI Evaluation** | AI Judge auto-evaluation + human annotation feedback, data-driven quality optimization |
| **Guardrails** | LLM-driven input/output safety guardrails, supporting block and audit modes |
| **Token Governance** | Usage statistics, quota management, tiered billing, cost analysis |

## Architecture Overview

| Component | Description |
|-----------|-------------|
| **Manager + Gateway** | Platform core: user management, model registry, API Key auth, rate limiting, quota, guardrails, OpenAI-compatible inference gateway |
| **NodeManager** | Device connection management: 256-shard connection table, gRPC bidirectional stream tunnels, least-connections scheduling |
| **Experiment** | AI evaluation service: AI Judge auto-evaluation + dataset evaluation |
| **DeepNode** | Desktop client: Tauri + Vue 3 + Python inference service, supports MLX / vLLM / llama.cpp |

## Request Pipeline

```
Auth → RateLimit → Quota → Guardrails(Input) → Route → Inference → Guardrails(Output) → Trace
```

Every request follows this pipeline — authentication, rate limiting, quota check, input safety evaluation, intelligent routing, model inference, output safety audit, and request tracing.

## Next Steps

- [Provider Quickstart](./quickstart-provider) — Learn how to contribute device power and earn income
- [Custom Hybrid Models](./custom-hybrid-model) — Learn how to create personal smart-routing models
- [Model Routing & Hybrid Dispatch](../architecture/model-routing) — Understand the smart scheduling mechanism
