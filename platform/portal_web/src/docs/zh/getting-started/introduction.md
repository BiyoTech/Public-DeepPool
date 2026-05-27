# DeepPool 介绍

## 什么是 DeepPool？

DeepPool 是一个 **AI 编排网关与 Token 治理平台**（AI Orchestration Gateway & Token Governance Platform）。它提供统一的大语言模型接入层——通过一个 API 端点和一个 API Key，即可调用 GPT、Claude、DeepSeek、Qwen、GLM 等全球主流 LLM，同时具备智能路由、安全护栏、请求追踪与质量评估、用量治理等完整能力。

## 核心能力

- 🔀 **多模型编排，统一网关** — 通过单一 API 端点接入数十种 LLM。支持三种模型来源：DeepNode 本地推理、云端 Provider API 代理、Hybrid 智能编排——对调用方完全透明
- 🎯 **自定义编排策略** — 通过 YAML 配置定义 Hybrid 路由规则，支持按上下文长度、Function Call、视觉内容、推理需求等维度智能调度。Round-Robin 负载均衡 + 自动故障转移
- 📊 **请求追踪、AI 评估与分析** — 完整的推理请求/响应记录，人工标注反馈与期望输出，AI Judge 自动评估模型输出质量，数据驱动持续优化
- 🛡️ **安全护栏（Guardrails）** — 基于 LLM 的输入/输出内容安全评估，请求前拦截和响应后审计，可配置拦截或仅记录策略，确保 AI 应用安全合规
- 🖥️ **DeepNode 本地推理** — 下载安装 DeepNode 桌面客户端，一键部署 Qwen、Gemma 等开源模型，利用本地 GPU/Apple Silicon 进行推理计算，数据不出设备

## 更多特性

- **OpenAI API 完全兼容** — 标准 `/v1/chat/completions` 接口，支持流式 SSE、Function Calling、Reasoning Content，现有 SDK 零改造接入
- **API Key + 限流 + 配额** — SHA-256 鉴权、滑动窗口 RPM/TPM 限流、Token 配额管理、AES-256-GCM 密钥加密
- **Token 用量治理** — 按 API Key / 模型 / 时间维度的用量统计、成本分析、分级计费
- **多推理引擎支持** — MLX (Apple Metal)、vLLM (CUDA)、llama.cpp (CPU)，自动检测硬件并选择最优引擎
- **gRPC 双向流隧道** — 单条 TCP 长连接承载注册/心跳/任务/结果，轻松穿越 NAT
- **安全设计** — 参数化查询、bcrypt 密码哈希、Token 鉴权、输入验证

## 模型三分类

DeepPool 将模型分为三种来源类型，是智能路由的基础：

| 类型 | 说明 | 路由方式 |
|------|------|---------|
| **DeepNode** | 边缘设备本地推理（Qwen、Gemma 等） | Gateway → gRPC → NodeManager → 设备隧道 |
| **Provider** | 云端 API 代理（OpenAI、Claude、DeepSeek 等） | Gateway → HTTP 代理 → 云端 API |
| **Hybrid** | 组合多个子模型的智能编排 | 条件路由 + Round-Robin + 自动故障转移 |

## 网关能力矩阵

| 能力 | 说明 |
|------|------|
| **编排** | 统一接入 DeepNode / Provider / Hybrid 模型来源，智能路由 |
| **自定义策略** | YAML 配置条件路由规则，按请求特征调度到最优子模型 |
| **追踪** | 完整推理请求/响应记录，支持按 API Key、模型、时间筛选 |
| **AI 评估** | AI Judge 自动评估 + 人工标注反馈，数据驱动质量优化 |
| **安全护栏** | 基于 LLM 的输入/输出安全评估，支持拦截和审计模式 |
| **Token 治理** | 用量统计、配额管理、分级计费、成本分析 |

## 架构概览

| 组件 | 说明 |
|------|------|
| **Manager + Gateway** | 平台核心：用户管理、模型仓库、API Key 鉴权、限流、配额、安全护栏、OpenAI 兼容推理网关 |
| **NodeManager** | 设备连接管理：256 分片长连接表、gRPC 双向流隧道、Least-Connections 调度 |
| **Experiment** | AI 评估服务：AI Judge 自动评估 + 数据集评估 |
| **DeepNode** | 桌面客户端：Tauri + Vue 3 + Python 推理服务，支持 MLX / vLLM / llama.cpp |

## 请求处理流水线

```
Auth → RateLimit → Quota → Guardrails(Input) → Route → Inference → Guardrails(Output) → Trace
```

每个请求按此流水线依次处理，完成鉴权、限流、配额检查、输入安全评估、智能路由、模型推理、输出安全审计、请求追踪的完整链路。

## 下一步

- [算力提供者快速开始](./quickstart-provider) — 了解如何贡献设备算力赚取收益
- [自定义 Hybrid 模型](./custom-hybrid-model) — 了解如何创建个人智能路由模型
- [模型路由与 Hybrid 调度](../architecture/model-routing) — 了解智能调度机制
