const n=`# DeepPool 介绍

## 什么是 DeepPool？

DeepPool 是一个开源的分布式大语言模型（LLM）推理算力池平台。它将分散在各地的闲置设备（Mac Apple Silicon、Linux NVIDIA GPU）的计算资源汇聚成统一算力池，同时对接云端大模型 API（OpenAI、百度千帆等），通过智能调度对外提供标准 OpenAI 兼容 API。

## 核心特性

- **OpenAI 兼容 API** — 完全兼容 Chat Completions API，支持流式 SSE、Function Calling、Reasoning Content，现有 SDK 零改造接入
- **三种模型来源** — 支持边缘设备推理（DeepNode）、云端 API 代理（Provider）、混合智能调度（Hybrid）
- **Hybrid 智能路由** — 根据请求特征（上下文长度、是否 FC、是否推理）自动选择最优模型，支持条件路由 + Round-Robin + 自动故障转移
- **极致性价比** — 小模型本地推理零成本，大模型按需上云，相比纯云端方案成本降低 50%+
- **多引擎覆盖** — Apple Silicon 走 MLX Metal、NVIDIA GPU 走 vLLM CUDA、通用设备走 llama.cpp，自动识别硬件匹配引擎
- **一键共享赚收益** — 安装 DeepNode 客户端即可将闲置设备接入算力池，按 Token 计费获得收入

## 模型三分类

DeepPool 将模型分为三种来源类型，是智能路由的基础：

| 类型 | 说明 | 适用场景 |
|------|------|---------|
| **DeepNode** | 边缘设备本地推理 | 低延迟、零数据出境、小/中型模型 |
| **Provider** | 云端 API 代理（OpenAI、百度千帆等） | 大模型、高并发、无本地 GPU |
| **Hybrid** | 组合多个子模型，智能调度 + 自动故障转移 | 生产环境推荐，兼顾成本与可靠性 |

## 架构概览

| 组件 | 说明 |
|------|------|
| **Manager + Gateway** | 平台核心：用户管理、模型仓库、API Key 鉴权、限流、配额、OpenAI 兼容推理网关 |
| **NodeManager** | 设备连接管理：256 分片长连接表、gRPC 双向流隧道、Least-Connections 调度 |
| **DeepNode** | 桌面客户端：Tauri + Vue 3 + Python 推理服务，支持 MLX / vLLM / llama.cpp |

## 下一步

- [算力提供者快速开始](./quickstart-provider) — 了解如何贡献设备算力赚取收益
- [API 使用者快速开始](./quickstart-consumer) — 了解如何调用推理 API
- [模型路由与 Hybrid 调度](../architecture/model-routing) — 了解智能调度机制
`;export{n as default};
