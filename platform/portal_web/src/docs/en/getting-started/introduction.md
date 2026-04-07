# Introduction to DeepPool

## What is DeepPool?

DeepPool is an open-source distributed Large Language Model (LLM) inference computing pool platform. It aggregates idle computing resources from edge devices (Mac Apple Silicon, Linux NVIDIA GPU) into a unified pool, while also integrating cloud LLM APIs (OpenAI, Qianfan, etc.), delivering cost-effective, reliable LLM inference through intelligent scheduling via a standard OpenAI-compatible API.

## Key Features

- **OpenAI-Compatible API** — Fully compatible with Chat Completions API, supports streaming SSE, Function Calling, Reasoning Content — zero migration for existing SDKs
- **Three Model Sources** — Edge device inference (DeepNode), cloud API proxy (Provider), and hybrid smart dispatch (Hybrid)
- **Hybrid Smart Routing** — Auto-selects the optimal model based on request features (context length, FC, reasoning), with condition routing + round-robin + auto failover
- **Extreme Cost Efficiency** — Small models run locally at zero cost, large models scale to cloud on demand — 50%+ savings vs pure cloud
- **Multi-Engine Coverage** — Apple Silicon uses MLX Metal, NVIDIA GPUs use vLLM CUDA, generic devices use llama.cpp — hardware auto-detected
- **Share Power, Earn Income** — Install DeepNode to join the pool, idle GPUs auto-serve inference requests and earn token-based rewards

## Model Classification

DeepPool categorizes models into three vendor types, the foundation of intelligent routing:

| Type | Description | Use Case |
|------|-------------|----------|
| **DeepNode** | Edge device local inference | Low latency, zero data egress, small/mid models |
| **Provider** | Cloud API proxy (OpenAI, Qianfan, etc.) | Large models, high concurrency, no local GPU |
| **Hybrid** | Multi-model combo with smart dispatch + auto failover | Production recommended, balances cost and reliability |

## Architecture Overview

| Component | Description |
|-----------|-------------|
| **Manager + Gateway** | Platform core: user management, model registry, API Key auth, rate limiting, quota, OpenAI-compatible inference gateway |
| **NodeManager** | Device connection management: 256-shard connection table, gRPC bidirectional stream tunnels, least-connections scheduling |
| **DeepNode** | Desktop client: Tauri + Vue 3 + Python inference service, supports MLX / vLLM / llama.cpp |

## Next Steps

- [Provider Quickstart](./quickstart-provider) — Learn how to contribute device power and earn income
- [Consumer Quickstart](./quickstart-consumer) — Learn how to call the inference API
- [Model Routing & Hybrid Dispatch](../architecture/model-routing) — Understand the smart scheduling mechanism
