<p align="center">
  <h1 align="center"><img src="platform/portal_web/public/logo-28.png" alt="DeepPool Logo" width="36" valign="middle"> DeepPool</h1>
  <p align="center">
    <strong>AI 融合调度网关 & Token 治理平台</strong>
  </p>
  <p align="center">
    统一接入全球主流大模型，提供智能融合调度、请求追踪与评估分析、安全护栏、Token 用量治理的一站式 AI 网关。
  </p>
  <p align="center">
    <a href="https://deeppool.tech">🌐 立即体验 DeepPool</a> •
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

DeepPool 是一个 **AI 融合调度网关与 Token 治理平台**，为企业和开发者提供统一的大模型接入层。通过一个 API 入口、一套 API Key，即可调用 GPT、Claude、DeepSeek、Qwen、GLM 等全球主流大模型，并获得智能路由、安全护栏、用量追踪、质量评估等全方位 Token 治理能力。

### ✨ 核心能力

- 🔀 **多模型融合调度，统一网关** — 一个 API 入口统一接入数十种大模型，支持 DeepNode 本地推理、云端 Provider API、Hybrid 混合调度三种模型来源，对调用方完全透明
- 🎯 **自定义融合调度策略** — 通过 YAML 配置灵活定义 Hybrid 路由规则，支持按上下文长度、Function Call、视觉内容、推理需求等条件智能分发，Round-Robin 负载均衡 + 自动故障转移
- 📊 **请求 Trace、AI 评估与分析** — 完整记录推理请求/响应日志，支持人工标注反馈与期望输出，AI Judge 自动评测模型输出质量，数据驱动持续优化
- 🛡️ **Guardrails 安全护栏** — 基于 LLM 的输入/输出内容安全评估，支持请求前拦截和响应后审计，可配置阻断或仅记录策略，保障 AI 应用安全合规
- 🖥️ **DeepNode 本地推理** — 下载安装 DeepNode 桌面客户端，一键部署 Qwen、Gemma 等开源模型，利用本地 GPU/Apple Silicon 提供推理算力，数据不出本地

### 🔌 更多特性

- **OpenAI API 完全兼容** — 标准 `/v1/chat/completions` 接口，支持流式 SSE、Function Calling、Reasoning Content，现有 SDK 零改造接入
- **API Key + 限流 + 配额** — SHA-256 鉴权、滑动窗口 RPM/TPM 限流、Token 配额管理、AES-256-GCM 密钥加密
- **Token 用量治理** — 按 API Key / 模型 / 时间维度的用量统计、成本分析、阶梯计费
- **多推理引擎支持** — MLX（Apple Metal）、vLLM（CUDA）、llama.cpp（CPU），自动检测并选择最优引擎
- **gRPC 双向流隧道** — 单一 TCP 长连接承载注册/心跳/任务/结果，轻松穿透 NAT
- **安全设计** — 参数化查询、bcrypt 密码哈希、Token 鉴权、输入校验

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
│              DeepPool Gateway (AI 融合调度网关)                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   请求处理流水线                        │   │
│  │  Auth → RateLimit → Quota → Guardrails(输入)          │   │
│  │    → Route → Inference → Guardrails(输出) → Trace     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌────────────┐ ┌─────────────┐ ┌─────────────────┐        │
│  │  DeepNode   │ │  Provider   │ │    Hybrid       │        │
│  │  本地推理   │ │  云端 API   │ │  融合调度       │        │
│  │  gRPC →     │ │  HTTP →     │ │  条件路由 +     │        │
│  │  NodeMgr    │ │  Cloud API  │ │  Round-Robin +  │        │
│  │             │ │             │ │  Failover       │        │
│  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘        │
│         │               │                 │                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Token 治理层                                         │   │
│  │  用量统计 · 成本分析 · Trace 追踪 · AI 评估 · 护栏   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  用户管理 · 模型仓库 · API Key 管理 · 钱包                  │
│                        ┌──────────────┐                      │
│                        │   MySQL 8    │                      │
│                        │  数据存储     │                      │
│                        └──────────────┘                      │
└────────────┬───────────────┬─────────────────────────────────┘
             │ gRPC          │ HTTPS
             ▼               ▼
┌────────────────────┐  ┌─────────────────────┐
│  NodeManager ×N    │  │  云端 API            │
│  分片连接表        │  │  OpenAI / Claude     │
│  Least-Conn 调度   │  │  DeepSeek / Qwen     │
│  gRPC 隧道管理     │  │  GLM / Kimi / ...    │
└────────┬───────────┘  └─────────────────────┘
         │ gRPC 双向流
         ▼
┌─────────────────────────────────────────────────────┐
│              DeepNode (桌面客户端)                    │
│  本地部署 Qwen、Gemma 等开源模型                     │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌────────────────┐  │
│  │  Tauri UI  │  │  FastAPI   │  │ Inference      │  │
│  │  Vue 3     │  │  :8765     │  │ Engine         │  │
│  │            │  │            │  │ MLX/vLLM/GGUF  │  │
│  └───────────┘  └───────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 网关能力矩阵

| 能力 | 说明 |
|------|------|
| **融合调度** | 统一接入 DeepNode / Provider / Hybrid 三种模型来源，智能路由 |
| **自定义策略** | YAML 配置条件路由规则，按请求特征分发到最优子模型 |
| **Trace 追踪** | 完整记录推理请求/响应，支持按 API Key、模型、时间筛选 |
| **AI 评估** | AI Judge 自动评测 + 人工标注反馈，数据驱动质量优化 |
| **Guardrails** | LLM 驱动的输入/输出安全护栏，支持阻断和审计 |
| **Token 治理** | 用量统计、配额管理、阶梯计费、成本分析 |

### 模型三分类

| VendorType | 说明 | 路由方式 |
|-----------|------|---------| 
| **deepnode** | 本地设备推理（Qwen、Gemma 等） | Gateway → gRPC → NodeManager → 设备隧道 |
| **provider** | 云端 API（OpenAI、Claude、DeepSeek 等） | Gateway → HTTP 代理 → 云端 API |
| **hybrid** | 融合调度（组合多个子模型） | 条件路由 + Round-Robin + 自动 Failover |

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
│   │   ├── nodemanager/           #   NodeManager 服务入口
│   │   └── experiment/            #   Experiment 服务入口
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
│   └── deploy.sh                  #   统一远程部署脚本
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
| **推理网关** | Gateway 内嵌 Manager，API Key 鉴权（SHA-256）、滑动窗口限流（RPM/TPM）、配额管理、Guardrails 护栏 |
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

> **提示**：NodeManager 配置结构类似，位于 `platform/config/nodemanager.yaml`。

### 4. 启动平台服务

**方式一：一键开发模式（推荐）**

```bash
# 启动所有平台组件 + 前端开发服务器 + DeepNode 客户端
./dev.sh all
```

`dev.sh` 支持按模块启动：

```bash
./dev.sh platform      # 仅启动后端服务 (Manager)
./dev.sh platformweb   # 仅启动前端开发服务器
./dev.sh client        # 仅启动 DeepNode 客户端
./dev.sh all           # 全部启动（默认）
```

**方式二：分别启动各后端组件**

使用 `run_platformserver.sh` 启动指定的后端服务：

```bash
# Terminal 1 — 启动 Manager（默认）
./run_platformserver.sh manager

# Terminal 2 — 启动 NodeManager
./run_platformserver.sh nodemanager

# Terminal 3 — 启动 Experiment
./run_platformserver.sh experiment
```

> 支持通过环境变量 `DEEPPOOL_LOG_LEVEL` 控制日志级别（默认 `debug`）。

**方式三：分别启动前端开发服务器**

使用 `run_platformweb.sh` 启动前端：

```bash
# 同时启动管控后台 + 用户门户（默认）
./run_platformweb.sh all

# 仅启动管控后台 (端口 5173)
./run_platformweb.sh control

# 仅启动用户门户 (端口 5174)
./run_platformweb.sh portal
```

| 前端 | 端口 | 说明 |
|------|------|------|
| control_web | 5173 | 管控后台（管理员使用） |
| portal_web | 5174 | 用户门户（终端用户使用） |

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
# Build all components
./build.sh all

# Only regenerate Protobuf code
./build.sh proto

# Only build platform backend services
./build.sh backend

# Only build web frontends (portal_web + control_web)
./build.sh web
```

### 构建产物

```
dist/
└── platform/
    ├── manager           # Manager binary
    ├── nodemanager       # NodeManager binary
    ├── experiment        # Experiment binary
    ├── portal_web/       # Portal frontend assets
    └── control_web/      # Admin frontend assets
```

---

## 🚢 部署

### 统一部署脚本

项目提供统一的 `deploy.sh` 脚本，支持通过参数灵活控制部署目标：

```bash
cd platform

# 查看帮助
./deploy.sh --help

# 生产环境全量部署（本地 SSL 证书 + 密码认证）
./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \
            --config config_prod --ssl local --ssl-cert-dir ssl_cert

# 测试环境全量部署（Let's Encrypt 自动证书 + SSH Key 认证）
./deploy.sh --domain test.deeppool.tech --server root@<your-server-ip> \
            --config config_test --ssl letsencrypt

# 仅部署 manager 和 portal_web
./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \
            --components manager,portal_web

# 仅部署前端
./deploy.sh --domain deeppool.tech --server root@<your-server-ip> --password '<your-password>' \
            --components portal_web,control_web
```

### 部署参数

| 参数 | 必选 | 说明 | 默认值 |
|------|:----:|------|--------|
| `--domain` | ✅ | 部署域名 | — |
| `--server` | ✅ | 远程服务器 `user@host` | — |
| `--password` | — | SSH 密码（不指定则用 Key 认证） | — |
| `--config` | — | 配置文件目录名（相对 `platform/`） | `config_prod` |
| `--remote-dir` | — | 远程部署目录 | `/opt/deeppool` |
| `--components` | — | 逗号分隔的组件列表 | 全部 |
| `--ssl` | — | 证书模式：`local` / `letsencrypt` | 自动检测 |
| `--ssl-cert-dir` | — | 本地证书目录 | `ssl_cert` |
| `--admin-email` | — | Let's Encrypt 注册邮箱 | `admin@deeppool.tech` |

**可部署组件**：`manager`、`nodemanager`、`experiment`、`portal_web`、`control_web`

### 部署流程

脚本自动完成以下步骤：

1. **交叉编译** — Go 服务编译为 `linux/amd64` 二进制（`-trimpath -ldflags="-s -w"`）
2. **前端构建** — `control_web`（base=/admin/）和 `portal_web` 的 Vite 生产构建
3. **停止旧服务** — 远程 SIGTERM → 等待 → SIGKILL 优雅停机
4. **上传产物** — SCP 上传二进制、配置、前端资源、SSL 证书、支付证书
5. **SSL 证书** — 本地证书上传 或 Let's Encrypt 自动申请（含续期 cron）
6. **启动服务** — nohup 后台启动所有后端组件
7. **Nginx 配置** — 自动生成并加载 Ingress 配置（HTTPS 终止 + 反向代理）
8. **健康检查** — 验证各服务端口监听和 HTTP 响应

### Nginx Ingress 路由

| 域名 | 路径 | 后端 |
|------|------|------|
| `deeppool.tech` | `/` | portal_web（用户门户） |
| `deeppool.tech` | `/admin/` | control_web（管控后台） |
| `deeppool.tech` | `/api/` | Manager :8080 |
| `deeppool.tech` | `/v1/` | Manager :8080（Gateway SSE） |
| `api.deeppool.tech` | `/api/` `/v1/` | Manager :8080（独立 API 域名） |

### 部署后目录结构

```
/opt/deeppool/               # 远程服务器
├── manager                  # Manager 二进制
├── nodemanager              # NodeManager 二进制
├── experiment               # Experiment 二进制
├── manager.log              # Manager 运行日志
├── nodemanager.log          # NodeManager 运行日志
├── experiment.log           # Experiment 运行日志
├── config/                  # YAML 配置文件
│   ├── manager.yaml
│   ├── nodemanager.yaml
│   └── experiment.yaml
├── control_web/             # 管控后台前端资源
├── portal_web/              # 用户门户前端资源
├── alipay_cert/             # 支付宝证书
└── wechat_pay_cert/         # 微信支付证书
```

### 端口一览

| 服务 | HTTP | gRPC | 说明 |
|------|------|------|------|
| Manager | 8080 | 9090 | 用户/设备管理 + **AI 融合调度网关** |
| NodeManager | 8082 | 9092 | 设备隧道管理 + 推理分发 |
| Experiment | — | 9093 | AI Judge + 数据集评估 |
| control_web (Nginx) | 443 | — | 管控后台 (`/admin/`) |
| portal_web (Nginx) | 443 | — | 用户门户 (`/`) |
| DeepNode LocalServer | 8765 | — | 本地推理服务 |

---

## 🗄️ 数据库

使用 MySQL 8，核心表在服务启动时**幂等创建**，增量变更通过 `migrations/` 目录下的 SQL 脚本管理。

### 数据库迁移

项目提供 `update_db.sh` 脚本，用于执行 `platform/migrations/` 目录下的增量 SQL 迁移：

```bash
cd platform

# 查看帮助
./update_db.sh --help

# 从配置文件读取数据库连接，执行所有迁移
./update_db.sh --config config/manager.yaml

# 手动指定连接参数
./update_db.sh --host 127.0.0.1 --user root --password 'your_password' --database deeppool

# 仅执行指定的迁移文件
./update_db.sh --config config/manager.yaml --file 011_guardrails.sql

# 从指定编号开始执行
./update_db.sh --config config/manager.yaml --from 008

# 预览将要执行的文件（不实际执行）
./update_db.sh --config config/manager.yaml --dry-run
```

**迁移规则**：
- SQL 文件按文件名前缀数字排序执行（002, 003, 004, ...）
- 所有语句使用 `CREATE TABLE IF NOT EXISTS`、`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 等幂等写法，可安全重复执行
- 执行失败时自动中断，并提示从失败文件重新开始的命令

### 迁移文件列表

```
platform/migrations/
├── 002_billing_precision_yuan.sql        # 计费精度调整为元
├── 003_tunnel_logs_fen_to_yuan.sql       # 隧道日志金额分→元
├── 004_add_model_tags.sql                # 模型标签字段
├── 005_payment_orders.sql                # 支付订单表
├── 006_consumer_operations.sql           # 消费者操作记录
├── 007_add_supports_vision.sql           # 视觉能力标识
├── 008_user_custom_models.sql            # 用户自定义模型
├── 009_migrate_rename_model_family.sql   # 模型族重命名
├── 010_remove_legacy_provider_fields.sql # 移除旧 Provider 字段
└── 011_guardrails.sql                    # Guardrails 护栏表
```

### 核心表概览

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `users` | 用户表 | username (UK), password_hash, phone (UK), email (UK) |
| `user_sessions` | 会话表 | token (UK) → user_id, expires_at (7天有效期) |
| `user_devices` | 设备表 | simei (UK), user_id, device_ip, device_config (JSON) |
| `api_keys` | API Key 表 | key_hash (UK), user_id, rate_limit, quota |
| `model_registry` | 模型仓库 | model_name (UK), vendor_type, pricing_tiers (JSON) |
| `model_endpoints` | 模型端点 | model_id → endpoint, upstream_model |
| `user_custom_models` | 用户自定义模型 | user_id + model_name (UK), hybrid_policy (TEXT) |
| `guardrails` | 护栏规则 | api_key_id, phase, action, evaluator_model |
| `guardrail_results` | 护栏评估结果 | guardrail_id, request_id, flagged, blocked |
| `payment_orders` | 支付订单 | order_no (UK), user_id, amount, status |

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

> 📝 完整的联调测试手册正在整理中，后续会在本仓库发布，覆盖用户注册/登录、模型配置、设备初始化、gRPC 推理（流式/非流式/多轮对话）、OpenAI 兼容接口等全链路场景。

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

# 或者分别在不同终端启动，便于查看各组件日志
# Terminal 1: 后端
./run_platformserver.sh manager
# Terminal 2: 前端
./run_platformweb.sh all
# Terminal 3: DeepNode 客户端（可选）
./run_client.sh
```

**本地开发脚本一览**：

| 脚本 | 用途 | 参数 |
|------|------|------|
| `dev.sh` | 一键启动所有组件 | `platform` / `platformweb` / `client` / `all` |
| `run_platformserver.sh` | 启动后端服务 | `manager` / `nodemanager` / `experiment` |
| `run_platformweb.sh` | 启动前端开发服务器 | `control` / `portal` / `all` |
| `run_client.sh` | 启动 DeepNode 客户端 | — |

---

## 📜 许可证

本项目采用 [Apache License 2.0](LICENSE) 开源协议。

---

<p align="center">
  <sub>Built with ❤️ by the DeepPool Team</sub>
</p>
