<p align="center">
  <h1 align="center">🌊 DeepPool</h1>
  <p align="center">
    <strong>分布式 LLM 推理算力池平台</strong>
  </p>
  <p align="center">
    将分散的个人设备组织成统一的推理算力网络，对外通过 OpenAI 兼容 API 提供大模型推理服务。
  </p>
  <p align="center">
    <a href="#快速开始">快速开始</a> •
    <a href="#架构概览">架构概览</a> •
    <a href="#项目结构">项目结构</a> •
    <a href="#部署">部署</a> •
    <a href="#api-文档">API 文档</a> •
    <a href="#贡献指南">贡献指南</a>
  </p>
</p>

---

## 📖 项目简介

DeepPool 是一个分布式 LLM 推理算力池平台，核心理念是**让每一台闲置设备都能成为 AI 推理节点**。

**工作原理**：设备贡献者安装 DeepNode 桌面客户端 → 本地自动部署推理引擎 → 通过 gRPC 隧道接入平台 → 平台对外暴露 OpenAI 兼容 API → 外部调用方像使用 OpenAI 一样发起推理请求 → 平台智能路由到空闲设备 → 设备本地执行推理并回传结果。

### ✨ 核心特性

- 🔌 **OpenAI API 完全兼容** — 标准 `/v1/chat/completions` 接口，支持流式 SSE、Function Calling、Reasoning Content
- 🌐 **gRPC 双向流隧道** — 单一 TCP 长连接承载注册/心跳/任务/结果，轻松穿透 NAT
- ⚡ **高性能连接管理** — 256 分片 ConnectionHub（FNV-1a 哈希），O(1) 查找，10s 心跳巡检，30s 超时剔除
- 🧠 **多推理引擎支持** — MLX（Apple Metal）、vLLM（CUDA）、llama.cpp（CPU），自动检测并选择最优引擎
- ☁️ **云端 Provider 代理** — 统一接入 OpenAI、百度千帆、硅基等云端 API，请求/响应自动改写，对调用方完全透明
- 🔀 **Hybrid 智能调度** — 混合模型将 deepnode 和 provider 组合，支持条件路由、Round-Robin 负载均衡、自动故障转移
- 🔑 **API Key + 限流 + 配额** — SHA-256 鉴权、滑动窗口 RPM/TPM 限流、Token 配额管理、AES-256-GCM 密钥加密
- 🖥️ **跨平台桌面客户端** — Tauri 2.0 + Vue 3 构建，支持 macOS（Apple Silicon / Intel），模型自动下载与管理
- 🔐 **安全设计** — 参数化查询、bcrypt 密码哈希、Token 鉴权、输入校验

---

## 🏗️ 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                      外部调用方                                │
│              POST /v1/chat/completions                        │
└─────────────────────────┬────────────────────────────────────┘
                          │ HTTP (OpenAI API, Bearer API Key)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                  Manager (平台核心)                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Gateway (OpenAI 兼容推理网关)              │   │
│  │  Auth → RateLimit(RPM/TPM) → Quota → Route           │   │
│  │                                                      │   │
│  │  ┌────────────┐ ┌─────────────┐ ┌─────────────────┐ │   │
│  │  │  DeepNode   │ │  Provider   │ │    Hybrid       │ │   │
│  │  │  gRPC →     │ │  HTTP →     │ │  条件路由 +     │ │   │
│  │  │  NodeMgr    │ │  Cloud API  │ │  Round-Robin +  │ │   │
│  │  │             │ │             │ │  Failover       │ │   │
│  │  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘ │   │
│  └─────────┼───────────────┼─────────────────┼──────────┘   │
│            │               │                 │               │
│  用户管理 · 设备管理 · 模型仓库 · API Key · 钱包              │
│  ┌─────────────┐  ┌──────────────┐                          │
│  │  Scheduler   │  │   MySQL 8    │                          │
│  │  (规划中)    │  │  数据存储     │                          │
│  └─────────────┘  └──────────────┘                          │
└────────────┬───────────────┬─────────────────────────────────┘
             │ gRPC          │ HTTPS
             ▼               ▼
┌────────────────────┐  ┌─────────────────────┐
│  NodeManager ×N    │  │  云端 API            │
│  分片连接表        │  │  OpenAI / 百度千帆   │
│  Least-Conn 调度   │  │  硅基 / 自定义       │
│  gRPC 隧道管理     │  └─────────────────────┘
└────────┬───────────┘
         │ gRPC 双向流
         ▼
┌─────────────────────────────────────────────────────┐
│              DeepNode (桌面客户端)                    │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌────────────────┐  │
│  │  Tauri UI  │  │  FastAPI   │  │ Inference      │  │
│  │  Vue 3     │  │  :8765     │  │ Engine         │  │
│  │            │  │            │  │ MLX/vLLM/GGUF  │  │
│  └───────────┘  └───────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 模型三分类

| VendorType | 说明 | 路由方式 |
|-----------|------|---------|
| **deepnode** | 边缘设备节点提供推理 | Manager → gRPC → NodeManager → 设备隧道 |
| **provider** | 云端 API（OpenAI 等） | Manager → HTTP 代理 → 云端 API |
| **hybrid** | 组合多个子模型 | 条件路由 + Round-Robin + 自动 Failover |

### 通信协议矩阵

| 通道 | 协议 | 端口 | 方向 | 用途 |
|------|------|------|------|------|
| 前端 → Manager | HTTP REST | 8080 | 单向 | 用户认证、设备/模型管理 |
| 前端 → LocalServer | HTTP REST | 8765 | 单向 | 设备初始化、状态查询 |
| 外部调用方 → Manager Gateway | HTTP (OpenAI API) | 8080 | 单向 | 推理请求（JSON / SSE） |
| Manager Gateway → NodeManager | gRPC | 9092 | 单向 | DeepNode 推理转发 |
| Manager Gateway → 云端 Provider | HTTPS | 443 | 单向 | Provider 推理代理 |
| LocalServer → Manager | gRPC Unary | 9090 | 单向 | 模型配置获取、设备注册 |
| LocalServer ↔ NodeManager | gRPC BidiStream | 9092 | 双向长连接 | 鉴权、心跳、任务下发与结果回传 |

---

## 📁 项目结构

```
DeepPool/
├── libs/                          # 共享协议层
│   └── proto/                     # Protobuf 定义 + 生成代码
│       ├── llm_infer.proto        #   LLM 推理协议 (对齐 OpenAI)
│       ├── manager_service.proto  #   Manager 管理服务协议
│       └── node_tunnel.proto      #   设备隧道双向流协议
│
├── platform/                      # 平台后端 + Web 前端
│   ├── cmd/
│   │   ├── manager/               #   Manager 服务入口
│   │   ├── scheduler/             #   Scheduler 服务入口
│   │   └── nodemanager/           #   NodeManager 服务入口
│   ├── internal/
│   │   ├── config/                #   统一配置加载
│   │   ├── common/                #   公共中间件、错误码、响应封装
│   │   ├── storage/mysql/         #   MySQL 连接池 + 幂等建表
│   │   ├── modules/health/        #   健康检查模块
│   │   ├── manager/               #   Manager 业务 (handler/service/repository)
│   │   └── nodemanager/           #   NodeManager 业务 (隧道/分发/OpenAI)
│   ├── config/                    #   YAML 配置文件
│   ├── control_web/               #   管控后台前端 (Vue 3 + TDesign)
│   ├── portal_web/                #   用户门户前端 (Vue 3 + TDesign)
│   └── deploy_dev.sh              #   一键远程部署脚本
│
├── clients/
│   └── deepnode/                  # DeepNode 桌面客户端
│       ├── app/                   #   前端 UI (Vue 3 + TypeScript)
│       ├── src-tauri/             #   Tauri 2.0 原生层 (Rust)
│       └── localserver/           #   本地推理服务 (Python 3.13 + FastAPI)
│
├── build.sh                       # 全量构建脚本
├── dev.sh                         # 开发模式启动
├── go.work                        # Go Workspace
└── package.json                   # npm Workspace
```

---

## 🛠️ 技术栈

| 层面 | 技术选型 |
|------|---------|
| **平台后端** | Go 1.23，标准库 `net/http`（零框架），gRPC |
| **推理网关** | Gateway 内嵌 Manager，API Key 鉴权（SHA-256）、滑动窗口限流（RPM/TPM）、配额管理 |
| **数据库** | MySQL 8（InnoDB, utf8mb4_unicode_ci） |
| **序列化 / RPC** | Protocol Buffers 3，gRPC（含双向流） |
| **密码学** | bcrypt（密码）、AES-256-GCM（API Key 加密）、SHA-256（设备指纹 + API Key 哈希） |
| **管控前端** | Vue 3 + TDesign + Pinia + Tailwind CSS |
| **门户前端** | Vue 3 + TDesign + markdown-it + vue-i18n |
| **桌面客户端** | Tauri 2.0 (Rust) + Vue 3 + TypeScript |
| **本地推理服务** | Python 3.13, FastAPI + uvicorn, grpcio |
| **推理引擎** | MLX（Apple Metal）、vLLM（CUDA）、llama.cpp（CPU） |
| **Function Call** | 注册表架构 ToolCallParser（支持 GLM/Kimi/DeepSeek/Qwen/Gemma4/Llama/Mistral） |
| **模型管理** | HuggingFace Hub（支持国内镜像） |

---

## 🚀 快速开始

### 前置依赖

| 依赖 | 版本要求 | 用途 |
|------|---------|------|
| **Go** | ≥ 1.23 | 平台后端编译 |
| **Node.js** | ≥ 18 | 前端构建 |
| **MySQL** | ≥ 8.0 | 数据存储 |
| **Python** | ≥ 3.13 | DeepNode 本地推理服务 |
| **protoc** | ≥ 3.x | Protobuf 编译（仅修改 proto 时需要） |
| **Rust / Cargo** | latest stable | Tauri 桌面客户端构建（可选） |

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/DeepPool.git
cd DeepPool
```

### 2. 准备数据库

创建 MySQL 数据库（表会在服务启动时自动创建）：

```sql
CREATE DATABASE deeppool CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. 修改配置

编辑平台配置文件，填入数据库连接信息：

```bash
# 编辑 Manager 配置
vim platform/config/manager.yaml
```

```yaml
server:
  http_addr: ":8080"
  grpc_addr: ":9090"

mysql:
  host: "127.0.0.1"
  port: 3306
  user: "root"
  password: "your_password"
  database: "deeppool"
```

> **提示**：NodeManager 和 Scheduler 配置结构类似，分别位于 `platform/config/nodemanager.yaml` 和 `platform/config/scheduler.yaml`。

### 4. 启动平台服务

**方式一：一键开发模式（推荐）**

```bash
# 启动所有平台组件 + 前端开发服务器
./dev.sh all
```

**方式二：分别启动各组件**

```bash
# 终端 1 — 启动 Manager
./run_platformserver.sh manager

# 终端 2 — 启动 NodeManager
./run_platformserver.sh nodemanager

# 终端 3 — 启动 Scheduler
./run_platformserver.sh scheduler

# 终端 4 — 启动管控前端 (dev server)
./run_platformweb.sh
```

### 5. 验证服务

```bash
# 健康检查
curl http://localhost:8080/api/v1/health
# 期望: {"code":0,"message":"ok","data":{"status":"healthy"}}

curl http://localhost:8082/api/v1/health
# 期望: {"code":0,"message":"ok","data":{"status":"healthy"}}
```

### 6. 启动 DeepNode 客户端（设备节点）

```bash
cd clients/deepnode

# 创建 Python 虚拟环境并安装依赖
python3.13 -m venv venv
source venv/bin/activate
pip install -r localserver/requirements.txt

# 启动本地推理服务
cd localserver && python main.py &

# 启动 Tauri 桌面应用（需要 Rust 环境）
cd ../app && npm install
cd .. && cargo tauri dev
```

> **独立运行模式**（无需 Tauri，通过浏览器访问）：
> ```bash
> cd clients/deepnode
> ./run_standalone.sh
> ```

---

## 🔌 API 文档

DeepPool 对外暴露 **OpenAI 兼容** 的推理接口，现有 OpenAI SDK 可零成本接入。支持三种模型类型：`deepnode`（边缘设备推理）、`provider`（云端 API 代理）、`hybrid`（智能混合调度）。

### Chat Completions

```bash
# 非流式请求
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{
    "model": "Qwen/Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    "stream": false
  }'
```

```bash
# 流式请求 (SSE)
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-api-key>" \
  -d '{
    "model": "Qwen/Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "写一首关于分布式计算的诗"}
    ],
    "stream": true
  }'
```

### 使用 OpenAI Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="your-api-key",
)

response = client.chat.completions.create(
    model="Qwen/Qwen3-0.6B-8bit",
    messages=[{"role": "user", "content": "Hello!"}],
    stream=True,
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### 查看可用模型

```bash
curl http://localhost:8080/v1/models \
  -H "Authorization: Bearer <your-api-key>"
```

---

## 📦 构建

项目提供统一的构建脚本，支持按模块构建：

```bash
# 构建所有组件
./build.sh all

# 仅重新生成 Protobuf 代码
./build.sh proto

# 仅构建平台后端 + 前端
./build.sh platform

# 仅构建 DeepNode 桌面客户端（含 PyInstaller 打包）
./build.sh deepnode
```

### 构建产物

```
dist/
├── platform/
│   ├── manager           # Manager 二进制
│   ├── scheduler         # Scheduler 二进制
│   ├── nodemanager       # NodeManager 二进制
│   └── web/              # 前端静态文件
└── deepnode/
    └── DeepNode.dmg      # macOS 安装包
```

---

## 🚢 部署

### 一键远程部署（开发环境）

```bash
cd platform
./deploy_dev.sh
```

该脚本自动完成以下步骤：
1. 交叉编译 Go 服务为 `linux/amd64` 二进制
2. 构建 `control_web` 和 `portal_web` 前端产物
3. SCP 上传至远程服务器
4. 配置 Nginx 反向代理（静态文件托管 + API 代理）
5. nohup 启动三个后端服务
6. 自动健康检查验证

### 部署后目录结构

```
/opt/deeppool/               # 远程服务器
├── manager                  # Manager 二进制
├── scheduler                # Scheduler 二进制
├── nodemanager              # NodeManager 二进制
├── config/                  # 配置文件
├── control_web/             # 管控后台前端 (:5173)
└── portal_web/              # 用户门户前端 (:5174)
```

### 端口一览

| 服务 | HTTP | gRPC | 说明 |
|------|------|------|------|
| Manager | 8080 | 9090 | 用户/设备管理 + **推理网关 (Gateway)** |
| Scheduler | 8081 | 9091 | 调度服务（规划中） |
| NodeManager | 8082 | 9092 | 设备隧道管理 + 推理分发 |
| control_web (Nginx) | 5173 | — | 管控后台 |
| portal_web (Nginx) | 5174 | — | 用户门户 |
| DeepNode LocalServer | 8765 | — | 本地推理服务 |

---

## 🗄️ 数据库

使用 MySQL 8，所有表在服务启动时**幂等创建**，无需手动执行 DDL。

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `users` | 用户表 | username (UK), password_hash, phone (UK), email (UK) |
| `user_sessions` | 会话表 | token (UK) → user_id, expires_at (7天有效期) |
| `user_devices` | 设备表 | simei (UK), user_id, device_ip, device_config (JSON) |

---

## 🧪 测试

```bash
# 运行平台后端单元测试
cd platform
go test ./...

# 运行指定模块测试
go test ./internal/nodemanager/...
go test ./internal/manager/...
```

项目包含以下测试用例：
- **ConnectionHub** — 分片并发注册/注销/查找
- **OpenAI Handler** — 请求解析与响应封装
- **User Handler** — HTTP 接口测试
- **User Service** — 业务逻辑测试

> 📝 完整的联调测试手册见 [mini_test.md](./mini_test.md)，覆盖用户注册/登录、模型配置、设备初始化、gRPC 推理（流式/非流式/多轮对话）、OpenAI 兼容接口等全链路场景。

---

## 🤝 贡献指南

欢迎参与 DeepPool 的开发！

### 开发流程

1. **Fork** 本仓库
2. 创建特性分支：`git checkout -b feature/your-feature`
3. 提交变更：`git commit -m 'feat: add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 **Pull Request**

### 代码规范

- **Go** — 遵循标准 Go 编码规范，`gofmt` 格式化
- **前端** — Vue 3 Composition API + TypeScript
- **提交信息** — 遵循 [Conventional Commits](https://www.conventionalcommits.org/)
- **安全** — 所有 SQL 使用参数化查询，密码使用 bcrypt 哈希
- **代码质量** — 注重良好抽象，补充必要注释与日志

### 开发环境推荐

```bash
# 一键启动开发环境（自动并行启动所有组件）
./dev.sh all
```

---

## 📜 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

---

<p align="center">
  <sub>Built with ❤️ by the DeepPool Team</sub>
</p>
