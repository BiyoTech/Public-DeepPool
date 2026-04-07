# 系统架构概览

## 整体架构

DeepPool 采用 Gateway 统一入口 + 多后端路由的微服务架构：

```
                         ┌─────────────┐
                         │  外部调用方   │
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
              │  │ (gRPC)  │ │ (HTTP) │ │(智能分发│  │
              │  └────┬────┘ └───┬────┘ │+Failover│ │
              │       │          │      └────────┘  │
              └───────┼──────────┼──────────────────┘
                      │          │
           ┌──────────┘          └──────────┐
           ▼                                ▼
    ┌──────────────┐              ┌─────────────────┐
    │ NodeManager  │              │   云端 API       │
    │ 分片连接表    │              │ OpenAI / 千帆    │
    │ Least-Conn   │              └─────────────────┘
    └──────┬───────┘
           │ gRPC 双向流
           ▼
    ┌──────────────┐
    │   DeepNode   │
    │ (边缘设备)    │
    │ MLX/vLLM/cpp │
    └──────────────┘
```

## 组件职责

### Manager + Gateway

Manager 是平台核心，同时内嵌 OpenAI 兼容推理网关（Gateway）：

- **用户管理** — 注册、登录、Token 鉴权
- **模型仓库** — 三种类型（DeepNode / Provider / Hybrid）的模型 CRUD
- **API Key 管理** — SHA-256 鉴权、AES-256-GCM 加密存储、RPM/TPM 限流、配额管理
- **Gateway 路由** — 根据模型 `vendor_type` 自动路由到 DeepNode（gRPC）、Provider（HTTP 代理）或 Hybrid（智能分发）
- **设备管理** — 设备注册、模型自动/手动分配

### NodeManager

NodeManager 管理所有在线设备的 gRPC 长连接：

- **256 分片 ConnectionHub** — FNV-1a 哈希，O(1) 查找，支持百万级连接
- **心跳巡检** — 10 秒巡检，30 秒超时自动剔除
- **Least-Connections 调度** — 选择负载最低的设备，多设备并列时轮询打散
- **gRPC 双向流隧道** — 注册、心跳、任务下发、结果回传复用单一 TCP 连接

### DeepNode

桌面客户端应用（Tauri + Vue 3 + Python），部署在算力提供者设备上：

- **硬件检测** — 自动识别 GPU 型号、内存大小
- **模型下载** — 从 HuggingFace Hub（国内镜像加速）自动下载
- **多引擎推理** — MLX（Apple Metal）、vLLM（CUDA）、llama.cpp（CPU）
- **隧道连接** — gRPC 双向流长连接，穿透 NAT，指数退避自动重连

## 两层调度架构

推理请求经历两层调度：

```
Layer 1 — Gateway (模型级)
  根据 vendor_type 决定走哪条路:
  · DeepNode → gRPC 到 NodeManager
  · Provider → HTTP 代理到云端 API
  · Hybrid → 条件匹配 + Round-Robin + Failover

Layer 2 — NodeManager (设备级)
  在多台在线设备间选择:
  · Least Connections 策略
  · 轮询打散避免惊群
```

## 技术栈

| 层面 | 技术选型 |
|------|---------|
| 平台后端 | Go 1.23，标准库 `net/http`，gRPC |
| 数据库 | MySQL 8（InnoDB, utf8mb4） |
| 协议 | Protocol Buffers 3，gRPC 双向流 |
| 桌面客户端 | Tauri 2.0 (Rust) + Vue 3 + TypeScript |
| 推理服务 | Python 3.13, FastAPI, grpcio |
| 推理引擎 | MLX, vLLM, llama.cpp |
| 密码学 | bcrypt, AES-256-GCM, SHA-256 |
