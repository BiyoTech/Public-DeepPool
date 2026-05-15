# DeepPool 技术架构文档

## 1. 产品定位

DeepPool 是一个 **AI 融合调度网关 & Token 治理平台**。为企业和开发者提供统一的大模型接入层，通过一个 API 入口、一套 API Key，即可调用 GPT、Claude、DeepSeek、Qwen、GLM 等全球主流大模型，并获得智能路由、安全护栏、用量追踪、质量评估等全方位 Token 治理能力。

### 五大核心能力

| # | 能力 | 说明 |
|---|------|------|
| 1 | **多模型融合调度，统一网关** | 一个 API 入口统一接入数十种大模型，支持 DeepNode 本地推理、云端 Provider API、Hybrid 混合调度三种模型来源 |
| 2 | **自定义融合调度策略** | 通过 YAML 配置灵活定义 Hybrid 路由规则，按上下文长度、Function Call、视觉内容、推理需求等条件智能分发 |
| 3 | **请求 Trace、AI 评估与分析** | 完整记录推理请求/响应日志，支持人工标注反馈与期望输出，AI Judge 自动评测模型输出质量 |
| 4 | **Guardrails 安全护栏** | 基于 LLM 的输入/输出内容安全评估，支持请求前拦截和响应后审计，可配置阻断或仅记录策略 |
| 5 | **DeepNode 本地推理** | 下载安装 DeepNode 客户端，一键部署 Qwen、Gemma 等开源模型，利用本地 GPU/Apple Silicon 提供推理算力 |

**核心价值链**：

```
调用方发起请求 → Gateway 鉴权限流 → Guardrails 输入护栏 → 融合调度路由
  → 推理执行 (DeepNode/Provider/Hybrid) → Guardrails 输出护栏
  → Trace 日志记录 → Token 用量统计 → 响应返回
```

---

## 2. 系统全景架构

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         DeepPool Platform                                    │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    Manager :8080 / :9090                                │  │
│  │                                                                        │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │  │
│  │  │              Gateway (AI 融合调度网关)                             │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌─────────────────── 请求处理流水线 ──────────────────────────┐  │  │  │
│  │  │  │                                                            │  │  │  │
│  │  │  │  Auth → RateLimit → Quota → Guardrails(输入)               │  │  │  │
│  │  │  │    → FusionRoute → Inference → Guardrails(输出) → Trace    │  │  │  │
│  │  │  │                                                            │  │  │  │
│  │  │  └────────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                                  │  │  │
│  │  │  ┌────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │  │  │
│  │  │  │  DeepNode   │  │  Provider   │  │       Hybrid            │  │  │  │
│  │  │  │  本地推理   │  │  云端 API   │  │  融合调度               │  │  │  │
│  │  │  │  gRPC →     │  │  HTTP →     │  │  条件路由 + RR + FO     │  │  │  │
│  │  │  │  NodeMgr    │  │  Cloud API  │  │                         │  │  │  │
│  │  │  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │  │  │
│  │  │         │                │                      │               │  │  │
│  │  └─────────┼────────────────┼──────────────────────┼───────────────┘  │  │
│  │            │                │                      │                  │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │  Token 治理层                                                   │  │  │
│  │  │  · Guardrails 安全护栏 (LLM 评估, 阻断/审计)                     │  │  │
│  │  │  · Trace 追踪 (异步写入用户外部 DB, TraceMatcher + TraceWriter)   │  │  │
│  │  │  · AI Judge 评测 (Experiment 服务, 自动评估输出质量)              │  │  │
│  │  │  · Token 用量统计 (按 Key/模型/日 汇总, 阶梯计费)                │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │  用户管理 · 模型仓库 · API Key 管理 · 钱包 · 支付                      │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                 │
│  │ NodeManager-A  │  │ NodeManager-B  │  │ Experiment     │                 │
│  │ :8082 / :9092  │  │ :8083 / :9093  │  │ gRPC :9093     │                 │
│  │ gRPC 隧道管理   │  │ gRPC 隧道管理   │  │ AI Judge       │                 │
│  │ Least-Conn 调度 │  │ Least-Conn 调度 │  │ Trace 标注     │                 │
│  └──────┬─────────┘  └──────┬─────────┘  └────────────────┘                 │
└─────────┼───────────────────┼────────────────────────────────────────────────┘
          │ gRPC BidiStream   │
          ▼                   ▼
┌─────────────────────────────────────────────────────┐
│              DeepNode (桌面客户端)                    │
│  本地部署 Qwen、Gemma 等开源模型                     │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌────────────────┐  │
│  │  Tauri UI  │  │  FastAPI   │  │ Inference      │  │
│  │  Vue 3     │  │  :8765     │  │ Engine         │  │
│  │            │  │            │  │ MLX/vLLM/GGUF  │  │
│  └───────────┘  └───────────┘  └────────────────┘  │
│     DeepNode ×N（多个设备节点提供本地推理算力）       │
└─────────────────────────────────────────────────────┘

外部接入:
  ┌───────────┐                    ┌───────────┐
  │ 外部调用方 │─ POST /v1/chat ──▶│  Gateway   │
  │ (OpenAI   │                    │  :8080     │
  │  兼容API) │                    └───────────┘
  └───────────┘
  ┌───────────┐                    ┌───────────┐
  │ portal_web│─ /api/v1/ ────────▶│  Manager   │
  │  :5174    │                    │  :8080     │
  └───────────┘                    └───────────┘
  ┌───────────┐                    ┌───────────┐
  │ 云端 API  │◀── HTTP 代理 ──────│  Provider  │
  │ GPT/Claude│                    │  代理模块  │
  │ DeepSeek  │                    └───────────┘
  └───────────┘
```

---

## 3. 项目工程结构

```
DeepPool/
├── go.work                          # Go Workspace（libs + platform 两个模块）
├── package.json                     # npm Workspace（platform/web + clients/deepnode/app）
├── build.sh                         # 全量构建（proto 生成 + Go 编译 + Tauri 打包）
├── dev.sh                           # 开发模式启动
├── run_platformserver.sh            # 单独启动平台后端组件
├── run_platformweb.sh               # 单独启动平台管控前端
├── run_client.sh                    # 单独启动 DeepNode 客户端
│
├── libs/                            # 共享协议层（Protobuf 定义 + 生成代码）
│   ├── proto/
│   │   ├── llm_infer.proto          #   LLM 推理协议（对齐 OpenAI API）
│   │   ├── manager_service.proto    #   Manager 管理服务协议
│   │   ├── node_tunnel.proto        #   设备隧道双向流协议
│   │   ├── llm/v1/                  #   Go 生成代码
│   │   ├── manager/v1/              #   Go 生成代码
│   │   └── nodetunnel/v1/           #   Go 生成代码
│   └── go.mod                       #   module: deeppool/libs
│
├── platform/                        # 平台后端
│   ├── cmd/                         #   微服务入口
│   │   ├── manager/main.go
│   │   ├── nodemanager/main.go
│   │   └── experiment/main.go
│   ├── config/                      #   YAML 配置文件
│   ├── internal/                    #   内部实现
│   │   ├── config/                  #     统一配置加载
│   │   ├── common/                  #     公共模块（错误、中间件、响应）
│   │   ├── storage/mysql/           #     MySQL 连接池 + 自动建表
│   │   ├── manager/                 #     Manager 业务实现
│   │   └── nodemanager/             #     NodeManager 业务实现
│   ├── web/                         #   管控前端（Vue 3，初始骨架）
│   ├── deploy_dev.sh                #   一键远程部署脚本
│   └── go.mod                       #   module: deeppool/platform
│
└── clients/
    └── deepnode/                    # DeepNode 桌面客户端
        ├── src-tauri/               #   Tauri 2.0 原生层（Rust）
        ├── app/                     #   前端 UI 层（Vue 3 + TypeScript）
        └── localserver/             #   本地推理服务层（Python 3.13）
```

---

## 4. 平台后端架构（Platform）

### 4.1 微服务划分

平台后端由独立可部署的 Go 微服务组成，每个服务同时暴露 HTTP 和 gRPC 两个端口：

| 服务 | HTTP | gRPC | 职责 |
|------|------|------|------|
| **Manager** | `:8080` | `:9090` | 用户管理、设备管理、模型配置下发 |
| **NodeManager** | `:8082` | `:9092` | 设备长连接管理、推理任务分发、OpenAI 兼容网关 |
| **Experiment** | — | `:9093` | AI 评判 (Judge)、数据集评测、Trace 标注 |

### 4.2 Manager — 用户/设备管理 + AI 融合调度网关

Manager 是平台的统一入口，对内管理用户、设备、模型和 API Key，**对外直接暴露 AI 融合调度网关**。Gateway 模块内嵌在 Manager 进程中，提供完整的请求处理流水线：鉴权 → 限流 → 配额 → Guardrails 输入护栏 → 融合调度路由 → 推理执行 → Guardrails 输出护栏 → Trace 日志记录。

#### 分层架构

```
manager/
├── server.go                   # HTTP + gRPC 双端口启动，依赖注入
├── types/types.go              # 请求/响应 DTO（含模型三分类 VendorType）
├── repository/                 # 数据访问层（MySQL 参数化查询）
│   ├── user_repository.go
│   ├── model_repository.go     # 模型仓库 + 设备-模型分配
│   └── apikey_repository.go    # API Key 管理
├── service/                    # 业务逻辑层
│   ├── user_service.go
│   ├── model_service.go        # 模型 CRUD + 设备自动分配 + hybrid 校验
│   ├── apikey_service.go       # API Key 鉴权 + AES-256-GCM 加密
│   ├── guardrail_service.go    # Guardrails 规则 CRUD + 评估结果存储
│   └── trace_service.go        # Trace 配置管理 + 日志查询
├── handler/                    # HTTP 路由（前端 / Admin）
│   ├── user_handler.go
│   ├── model_handler.go        # 模型仓库 Admin CRUD
│   ├── apikey_handler.go
│   └── guardrail_handler.go    # Guardrails 规则管理 + 评估记录查询
├── grpchandler/                # gRPC 服务（服务间 / 客户端通信）
│   └── manager_grpc.go
└── gateway/                    # ★ AI 融合调度网关
    ├── proxy.go                #   统一入口：鉴权 → 限流 → 配额 → 护栏 → 路由 → 追踪
    ├── provider.go             #   云端 Provider HTTP 代理
    ├── router.go               #   NodeManager 节点路由器（健康检查 + 轮询）
    ├── dispatch.go             #   Hybrid 混合模型分发 + 故障转移
    ├── routing_policy.go       #   YAML 路由策略引擎 + PolicyCache
    ├── rate_limiter.go         #   滑动窗口限流（RPM + TPM）
    ├── guardrail_evaluator.go  #   ★ Guardrails 运行时评估器（LLM 驱动）
    ├── trace_matcher.go        #   ★ Trace 匹配器（内存缓存 + 周期刷新）
    └── trace_writer.go         #   ★ Trace 异步写入器（外部 DB 连接池）
```

#### 模型三分类体系（VendorType）

系统将模型分为三种来源类型，是整个路由架构的基础：

| VendorType | 常量 | 说明 | 典型场景 |
|-----------|------|------|---------|
| **deepnode** | `VendorTypeDeepNode` | 由边缘设备节点提供推理算力 | Qwen3-0.6B 运行在 Mac M4 上 |
| **provider** | `VendorTypeProvider` | 云端 API（OpenAI/百度千帆等），HTTP 代理转发 | GPT-4o、Claude、DeepSeek-V3 |
| **hybrid** | `VendorTypeHybrid` | 组合多个子模型，智能路由 + 故障转移 | 大模型优先 deepnode，fallback 到 provider |

#### 模型注册表（model_registry）

| 字段类别 | 关键字段 | 说明 |
|---------|---------|------|
| 通用 | `model_name`(UK), `vendor_type`, `enabled`, `priority` | 模型唯一名称、类型、启停、优先级 |
| 通用 | `supports_reasoning`, `supports_function_call`, `supports_vision`, `max_context_length`, `param_scale` | 能力标签（推理/FC/视觉理解/上下文长度/参数量） |
| DeepNode | `repo_id`, `model_base_dir`, `engine`, `supported_engines`, `min_memory_gb`, `min_gpu_memory_gb` | HF 仓库、存储路径、引擎、硬件门槛 |
| Provider | `endpoint`, `api_key`(AES-256-GCM), `upstream_model`, `provider_type` | 上游 URL、密钥（加密存储）、上游模型名 |
| Hybrid | `child_models`(JSON), `routing_policy`(YAML) | 子模型名称列表（≥2）、路由策略 |

#### HTTP API（含 Gateway）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/chat/completions` | **★ OpenAI 兼容推理网关**（支持 deepnode/provider/hybrid） |
| `GET` | `/v1/models` | 列出所有可用模型 |
| `POST` | `/api/v1/users/register` | 用户注册 |
| `POST` | `/api/v1/users/login` | 用户登录 |
| `POST` | `/api/v1/admin/models` | 创建模型（Admin） |
| `PUT` | `/api/v1/admin/models/{id}` | 更新模型（Admin） |
| `POST` | `/api/v1/admin/devices/assign` | 手动分配模型到设备（Admin） |
| `POST` | `/api/v1/admin/devices/batch-assign` | 批量分配（Admin） |

#### gRPC 接口 (ManagerService)

| 方法 | 说明 |
|------|------|
| `GetModelDeployConfig` | 获取模型部署配置（model_name, repo_id, engine） |
| `RegisterDevice` | 注册设备（自动触发模型智能分配） |
| `GetDevice` / `UpdateDevice` | 查询/更新设备 |

#### 数据库 Schema

Manager 启动时通过 `EnsureSchema()` 幂等执行 DDL 自动建表：

| 表名 | 说明 | 关键字段 |
|------|------|---------|
| `users` | 用户表 | username(UK), password_hash, phone(UK), email(UK), identity, user_type |
| `user_sessions` | 会话表 | token(UK) → user_id, expires_at(7 天) |
| `user_devices` | 设备表 | simei(UK), user_id, device_config(JSON), registered_models(JSON) |
| `model_registry` | **模型仓库** | model_name(UK), vendor_type, child_models, routing_policy |
| `device_model_assignments` | 设备-模型分配 | device_id + model_id(UK), source(auto/manual) |
| `api_keys` | API Key | key_hash(UK), rate_limit_rpm, rate_limit_tpm, quota_total/used |
| `token_usage_daily` | Token 用量日汇总 | usage_date + user_id + model_name + source + api_key_id(UK) |
| `tunnel_infer_logs` | 隧道推理日志 | request_id, model_name, tokens, tool_call 指标 |
| `user_wallets` | 钱包 | balance, total_earned, total_spent |

---

### 4.3 Gateway — OpenAI 兼容推理网关

Gateway 是 Manager 内嵌的核心模块，负责将外部 `/v1/chat/completions` 请求路由到正确的后端。

#### 4.3.1 完整请求链路

```
客户端 POST /v1/chat/completions (Bearer API Key)
  │
  ├─ 1. API Key 鉴权 (SHA-256 哈希查库)
  │     → 返回: KeyID, UserID, RPM/TPM 限流配置, 配额信息, Guardrails 规则
  │
  ├─ 2. RPM 限流检查 (滑动窗口, 1s 精度, 60s 窗口)
  │
  ├─ 3. TPM 限流检查 (滑动窗口, 请求前检查上一窗口)
  │
  ├─ 4. 配额检查 (quota_used < quota_total, -1 = 不限)
  │
  ├─ 5. 解析 body → 提取 model + stream
  │
  ├─ 6. ★ Guardrails 输入护栏 (GuardrailEvaluator.RunInputGuardrails)
  │     → 对 input phase 的规则逐条评估
  │     → flagged + action=block → 返回 400 拒绝请求
  │     → flagged + action=log → 记录但放行
  │     → 异步写入评估结果到 guardrail_results 表
  │
  ├─ 7. 查库获取模型配置 (ModelService.GetModelByName)
  │
  ├─ 8. 融合调度路由 (resolveBackend)
  │     ├─ VendorTypeHybrid  → handleHybridChat (智能分发 + 故障转移)
  │     ├─ VendorTypeProvider → handleProviderChat (HTTP 代理)
  │     └─ VendorTypeDeepNode → NodeRouter.Route → gRPC 转发
  │
  ├─ 9. 响应转换
  │     ├─ DeepNode: gRPC proto → OpenAI JSON
  │     └─ Provider: 上游 JSON → 改写 model 字段 → 透传
  │
  ├─ 10. ★ Guardrails 输出护栏 (GuardrailEvaluator.RunOutputGuardrails)
  │      → 对 output phase 的规则逐条评估
  │      → flagged + action=block → 替换响应为安全提示
  │      → flagged + action=log → 记录但正常返回
  │      → 注意: 启用输出护栏时自动禁用流式响应
  │
  ├─ 11. ★ Trace 日志记录 (TraceMatcher.Match → TraceWriter.Write)
  │      → TraceMatcher 内存缓存匹配 (api_key_id + model_name)
  │      → 匹配成功 → 异步写入完整请求/响应到用户外部 DB
  │      → best-effort: 写入失败仅记录日志，不阻塞响应
  │
  └─ 12. 异步用量记录
        ├─ IncrQuotaUsed (更新配额)
        ├─ RecordTokens (更新 TPM 计数器)
        └─ InferLogService.RecordGatewayUsage (写 token_usage_daily 表)
```

#### 4.3.2 响应头标记

每个请求都附带以下响应头，便于调用方了解实际路由路径：

| Header | 说明 | 示例 |
|--------|------|------|
| `X-DeepPool-Backend` | 后端类型 | `deepnode` / `provider` / `hybrid` |
| `X-DeepPool-Model-Name` | 请求的模型名 | `gpt-4o-hybrid` |
| `X-DeepPool-Provider-Type` | 提供商类型（仅 provider） | `openai` / `custom` |
| `X-DeepPool-Route-Target` | 实际路由目标 | `localhost:9092` / `api.openai.com` |

#### 4.3.3 限流器（RateLimiter）

```
RateLimiter
├── 按 API Key 维度独立计数
├── 滑动窗口: 精度 1 秒, 窗口 60 秒
├── RPM (Requests/Min): 请求前检查, 允许则 +1
├── TPM (Tokens/Min): 请求前检查是否超限; 请求完成后记录实际消耗
└── 线程安全: sync.RWMutex + 分桶计数
```

---

### 4.3.4 Guardrails — 安全护栏

Guardrails 是网关的内容安全层，基于 LLM 对请求输入和模型输出进行实时安全评估。

#### 架构设计

```
GuardrailEvaluator
├── 按 API Key 维度配置护栏规则
├── 支持两个执行阶段:
│     ├─ input  (请求前): 评估用户输入内容
│     └─ output (响应后): 评估模型输出内容
├── 两种动作策略:
│     ├─ block: 标记为危险时阻断请求/替换响应
│     └─ log:   标记为危险时仅记录，不影响请求流程
├── 评估方式: 自引用 Gateway 调用 LLM 模型进行内容评估
├── 评估结果: {flagged, confidence, reason} JSON 结构
└── 异步存储: 评估结果异步写入 guardrail_results 表
```

#### 关键特性

| 特性 | 说明 |
|------|------|
| **LLM 驱动评估** | 使用用户配置的评估模型 + 自定义 Prompt 进行内容安全判断 |
| **双阶段护栏** | 输入阶段拦截危险请求，输出阶段审计模型响应 |
| **流式自动禁用** | 启用输出护栏时自动禁用流式响应，等待完整响应后评估 |
| **超时保护** | 单次评估 15s 超时，最多重试 1 次 |
| **异步存储** | 评估结果异步写入，不影响主请求延迟 |

---

### 4.3.5 Trace — 推理日志追踪

Trace 功能在网关层实现完整的推理请求/响应日志采集，为后续的 AI 评估和分析提供数据基础。

#### 架构设计

```
TraceMatcher (in-memory cache)
├── 周期性从 DB 加载活跃 Trace 配置 (10s 间隔)
├── 内存 map: api_key_id → []{trace_id, db_type, dsn, model_names}
├── 匹配逻辑: api_key_id 存在 AND (模型列表为空 OR model_name 在列表中)
└── 支持 ForceRefresh (Trace 状态变更时立即刷新)

          │ 匹配成功
          ▼
TraceWriter (async, best-effort)
├── 缓冲通道 (chan *TraceLogEntry, 解耦网关热路径)
├── 多 Worker 并发消费
├── 外部 DB 连接池 (sync.Map, 按 DSN 缓存)
├── 支持 MySQL / PostgreSQL / ClickHouse
└── 写入失败仅记录日志，不阻塞不重试
```

#### TraceLogEntry 字段

| 字段 | 说明 |
|------|------|
| TraceID | 关联的 Trace 配置 ID |
| RequestID | 请求唯一标识 |
| APIKeyID / UserID | 调用方信息 |
| ModelName | 使用的模型名称 |
| UserQuery | 用户输入 (截断 200 字符) |
| RequestBody / ResponseBody | 完整请求/响应 JSON |
| IsStream / FirstTokenMs | 流式标识 / TTFT |
| PromptTokens / CompletionTokens / ReasoningTokens | Token 用量明细 |
| DurationMs | 请求总耗时 |
| Success / ErrorMessage | 成功/失败状态 |

---

### 4.4 Provider — 云端 API 代理

当模型 `vendor_type = "provider"` 时，Gateway 将请求 HTTP 代理到云端 API（如 OpenAI、百度千帆、硅基等）。

#### 代理流程

```
客户端请求 → Gateway 鉴权/限流通过
  │
  ├─ 请求改写: model 字段替换为 upstream_model
  ├─ Endpoint 解析: base_url + "/chat/completions" (不自动插 /v1/)
  ├─ 认证: Authorization: Bearer <model.api_key>
  │
  ├─ 非流式: 读取完整响应 → 改写 model → 返回
  └─ 流式: SSE 逐行读取 → 改写每行 model → flush 转发
  │
  └─ Usage 提取: 从 usage 字段 (非流式) 或最后 chunk (流式) 中提取 token 用量
```

**关键设计**：
- **Endpoint 格式**: 用户配置完整 base URL (如 `https://api.openai.com/v1`)，系统只追加 `/chat/completions`
- **API Key 加密**: 数据库中 AES-256-GCM 加密存储，运行时解密使用
- **Model 改写**: 请求中替换为 upstream_model，响应中替换回 model_name（对调用方透明）

---

### 4.5 Hybrid — 混合模型智能调度

当模型 `vendor_type = "hybrid"` 时，系统根据**路由策略**将请求分发到多个子模型，支持**条件路由 + Round-Robin 负载均衡 + 自动故障转移**。

#### 4.5.1 架构概览

```
┌──────────────────────────────────────────────────────────────────┐
│                     Hybrid Model Dispatch                        │
│                                                                  │
│  请求 → extractRequestFeatures → PolicyCache.Get(model)          │
│           │                          │                           │
│           ▼                          ▼                           │
│    RequestFeatures            RoutingPolicy                      │
│    · InputTokens              · Rules (条件→目标)                 │
│    · ToolCount                · DefaultTargets                   │
│    · HasTools                 · Round-Robin LB                   │
│    · HasReasoning                    │                           │
│    · HasVision                       │                           │
│    · ImageCount                      ▼                           │
│                            policy.Match(features)                │
│                                      │                           │
│                              有序候选列表                         │
│                    [primary_0, primary_1, ..., fallback_0, ...]  │
│                                      │                           │
│              ┌───────────────────────┼────────────────────┐      │
│              ▼                       ▼                    ▼      │
│         candidate_0             candidate_1          candidate_N │
│         (try first)             (fallback)           (last)      │
│              │                       │                    │      │
│              ├─ provider → HTTP      ├─ deepnode → gRPC   │      │
│              └─ deepnode → gRPC      └─ provider → HTTP   │      │
│                                                                  │
│  成功 → 返回 | 失败 → 下一个 | 全部失败 → 503                     │
└──────────────────────────────────────────────────────────────────┘
```

#### 4.5.2 路由策略 YAML Schema

```yaml
load_balance: "round-robin"          # 负载均衡（当前仅支持 round-robin）
rules:                               # 条件规则列表（按顺序匹配, 首个命中生效）
  - name: "long_context_to_cloud"
    condition:                        # AND 组合条件
      min_input_tokens: 2000          # 长上下文请求
    targets: ["gpt-4o-provider"]      # 路由到云端

  - name: "tool_call_to_local"
    condition:
      has_tools: true                 # 包含 function calling
    targets: ["qwen3-deepnode", "gpt-4o-provider"]

  - name: "vision_to_cloud"
    condition:
      has_vision: true                # 包含图片内容
    targets: ["gpt-4o-provider"]

default_targets: ["qwen3-deepnode"]   # 无规则匹配时的默认目标
```

**条件字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `max_input_tokens` / `min_input_tokens` | int | 输入 token 数范围（≈ 字符数/4） |
| `max_tool_count` / `min_tool_count` | int | tools 数组长度范围 |
| `has_tools` | bool | 是否包含 function calling |
| `has_reasoning` | bool | 是否启用 enable_thinking |
| `has_vision` | bool | 最后一条 user 消息是否包含 image_url 类型内容 |

#### 4.5.3 匹配与故障转移逻辑

1. **提取请求特征** (`extractRequestFeatures`): 从请求体解析 InputTokens/ToolCount/HasReasoning
2. **规则匹配**: 遍历 rules，所有条件取 AND，首个匹配的 rule 生效
3. **Round-Robin 旋转**: 命中规则的 targets 使用原子计数器轮询 (如 `[A,B,C]` 第二次调用返回 `[B,C,A]`)
4. **追加 Fallback**: 将 `childModels` 中不在 primary 列表的模型追加到候选末尾
5. **逐个尝试**: 按候选顺序执行推理，成功则返回；失败则跳到下一个
6. **防递归**: 子模型若也是 hybrid 类型，直接跳过
7. **全部失败**: 返回 `503 all candidates failed`

#### 4.5.4 PolicyCache — 策略缓存

- 从 `model_registry` 表周期性轮询（默认 10 秒）加载所有 `vendor_type='hybrid' AND enabled=1` 的路由策略
- 仅在 `updated_at` 变化时重新解析 YAML（变更检测）
- 支持从文件加载默认策略 (`default_hybrid_policy.yaml`)
- 多 Manager 节点通过 DB polling 保持一致性

---

### 4.6 NodeManager — 设备连接管理与推理分发

NodeManager 管理所有在线设备的 gRPC 长连接，并将 Gateway 转发过来的推理请求路由到合适的设备执行。

#### 核心组件

```
nodemanager/
├── server.go               # HTTP + gRPC 双端口启动
├── connection_hub.go        # 分片连接表（百万级长连接管理）
├── tunnel_handler.go        # gRPC 双向流隧道处理
├── dispatch_service.go      # 推理任务分发与调度
└── nm_grpc_handler.go       # Gateway ↔ NodeManager gRPC 接口
```

#### 4.6.1 NodeRouter — Gateway 到 NodeManager 的路由

Gateway 中的 `NodeRouter` 管理到所有 NodeManager 节点的 gRPC 长连接：

```
NodeRouter
├── 初始化: 从配置加载 NodeManager 节点列表, 建立 gRPC 长连接
├── 路由: 健康节点间 Round-Robin 轮询选择
├── 健康检查: 后台 goroutine 每 15 秒 gRPC Health 探测
└── 降级: 所有节点不健康时 fallback 使用全部节点
```

#### 4.6.2 ConnectionHub — 高性能分片连接表

```
┌───────────────────────────────────────────────────────────┐
│                    ConnectionHub                          │
│                                                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐      ┌─────────┐ │
│  │ Shard 0  │  │ Shard 1  │  │ Shard 2  │ ... │Shard 255│ │
│  │ RWMutex  │  │ RWMutex  │  │ RWMutex  │      │ RWMutex │ │
│  │ map[simei│  │ map[simei│  │ map[simei│      │ map[simei│ │
│  │  →session│  │  →session│  │  →session│      │  →session│ │
│  └─────────┘  └─────────┘  └─────────┘      └─────────┘ │
│                                                           │
│  • 256 分片, FNV-1a 哈希分片, O(1) 查找                    │
│  • 按模型名称查找在线设备 FindByModel()                     │
│  • 10 秒间隔心跳巡检, 30 秒超时自动剔除                      │
│  • 同一 SIMEI 重连时自动替换旧会话                           │
└───────────────────────────────────────────────────────────┘
```

#### 4.6.3 TunnelHandler — gRPC 双向流隧道

```
阶段 1 — 注册鉴权:
  Client ──[RegisterRequest(simei, token, models, engine)]──▶ Server
  Client ◀──[RegisterResponse(session_id, heartbeat_interval)]── Server

阶段 2 — 事件循环:
  Client ──[Heartbeat]──▶ Server (更新时间戳, 回复 pong)
  Server ──[InferenceTask(task_id, request)]──▶ Client
  Client ──[TaskResult(task_id, response)]──▶ Server      (非流式)
  Client ──[TaskStreamChunk(task_id, chunk, done)]──▶ Server (流式)
  Server ──[TaskCancel(task_id, reason)]──▶ Client
```

#### 4.6.4 DispatchService — 设备级调度

```
Gateway gRPC 请求到达 → 按 model 查找在线设备 (ConnectionHub.FindByModel)
  → Least Connections: 选择 pendingCount 最小的设备
  → 多设备并列时原子轮询计数器打散 (避免惊群)
  → 通过隧道 stream 下发 InferenceTask
  → 等待结果:
      非流式 → 阻塞等待 TaskResult (120s 超时)
      流式   → 返回 chan *StreamChunk, goroutine 转发 chunk
```

### 4.7 公共模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 统一配置 | `config/config.go` | YAML 配置加载，支持环境变量覆盖 |
| 错误定义 | `common/errors.go` | 全局哨兵错误（ErrDuplicate/ErrNotFound/ErrInvalidToken/ErrInvalidRequest） |
| HTTP 中间件 | `common/middleware.go` | 请求日志记录 + CORS 跨域支持 |
| 响应封装 | `common/response.go` | 统一 JSON 响应结构 + 请求体解码 |
| 数据库 | `storage/mysql/mysql.go` | MySQL 连接池初始化 + 幂等自动建表 |

---

## 5. 共享协议层（Libs）

`libs/` 是整个系统的**协议契约层**，定义了三大 Protobuf 协议，供 Go（平台端）和 Python（客户端）共同使用。

### 5.1 协议依赖关系

```
llm_infer.proto (基础层 — LLM 推理数据模型)
      │
      ├──▶ node_tunnel.proto (隧道协议，复用 LLM 推理消息)
      │       InferenceTask.request   → llmv1.ChatCompletionRequest
      │       TaskResult.response     → llmv1.ChatCompletionResponse
      │       TaskStreamChunk.chunk   → llmv1.ChatCompletionChunk
      │
      └──  manager_service.proto (管理协议，独立)
```

### 5.2 llm_infer.proto — LLM 推理协议

**包名**：`deeppool.llm.v1`

完整对齐 OpenAI Chat Completions API，包含扩展字段：

| gRPC 方法 | 类型 | 说明 |
|-----------|------|------|
| `Health` | Unary | 健康检查 |
| `ChatCompletion` | Unary | 非流式推理 |
| `ChatCompletionStream` | Server-Streaming | 流式推理 |

核心消息类型：
- `ChatCompletionRequest` — 支持 messages, tools, tool_choice, response_format, seed, logprobs, **enable_thinking**
- `ChatMessage` — 支持 system/user/assistant/tool 角色，含 **reasoning_content** 字段（DeepSeek R1 / Qwen3）
- `ChatCompletionResponse` / `ChatCompletionChunk` — 含 Usage 和 **CompletionTokensDetails**（reasoning_tokens）

### 5.3 manager_service.proto — 管理服务协议

**包名**：`deeppool.manager.v1`

| gRPC 方法 | 说明 |
|-----------|------|
| `GetModelDeployConfig` | 获取模型部署配置（model_name, repo_id, engine, options） |
| `RegisterDevice` | 注册设备到平台 |
| `GetDevice` / `UpdateDevice` | 查询/更新设备信息 |

### 5.4 node_tunnel.proto — 设备隧道协议

**包名**：`deeppool.nodetunnel.v1`

| gRPC 方法 | 类型 | 说明 |
|-----------|------|------|
| `Tunnel` | **Bidirectional Streaming** | 设备与 NodeManager 之间的持久隧道 |

设计目标（proto 注释中明确定义）：
1. **长连接**：设备启动后建立并维持 TCP 级长连接
2. **安全鉴权**：首条消息完成身份验证
3. **心跳保活**：双向定时心跳，超时自动剔除
4. **任务通道**：NodeManager 下发推理任务，设备回传结果（支持流式）
5. **极致性能**：基于 gRPC 双向流，避免频繁连接建立开销

---

## 6. DeepNode 客户端架构

DeepNode 是一个三层架构的桌面应用，用户安装后将本地设备变为 DeepPool 网络的推理算力节点。

### 6.1 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│  Tauri Layer (Rust)  — 桌面外壳                               │
│  • 原生窗口 (1200×800)、系统菜单                               │
│  • 设备指纹 (simei) 生成：采集硬件特征 → SHA-256 哈希           │
│  • Tauri Command: get_device_fingerprint                      │
├──────────────────────────────────────────────────────────────┤
│  UI Layer (Vue 3 + TypeScript + Vite)  — 前端界面              │
│  • AuthView       → 登录/注册                                 │
│  • DeviceInitView → 设备初始化（模型下载进度、引擎启动）          │
│  • DeviceDetailView → 运行仪表板（GPU/温度/积分/流量/Token统计）│
│  • 国际化支持（中/英双语）                                      │
├──────────────────────────────────────────────────────────────┤
│  LocalServer (Python 3.13)  — 本地推理服务                     │
│  • FastAPI HTTP 服务 (:8765)                                  │
│  • 多引擎推理（MLX / vLLM / llama.cpp）                        │
│  • gRPC 推理服务（LLMInferService）                            │
│  • 平台 gRPC 客户端（Manager + NodeManager 隧道）              │
│  • 模型自动下载（HuggingFace）                                 │
│  • 凭证持久化（~/.deeppool/device_credential.json）            │
└──────────────────────────────────────────────────────────────┘
```

### 6.2 页面流转状态机

```
              ┌─────────────┐
              │   App.vue    │
              │ (状态路由器)  │
              └──────┬──────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
     未登录状态          已登录状态
     ┌──────────┐       ┌──────────────┐
     │ AuthView │       │ 检测设备状态... │
     │ 登录/注册 │       └──────┬───────┘
     └──────────┘              │
                      ┌────────┴────────┐
                      ▼                 ▼
               设备未就绪           设备已就绪
          ┌────────────────┐  ┌──────────────────┐
          │ DeviceInitView │  │ DeviceDetailView  │
          │ 初始化引导流程  │  │ 运行状态仪表板    │
          └────────────────┘  └──────────────────┘
```

### 6.3 设备指纹生成（Rust）

通过 Tauri Command 暴露给前端调用，跨平台采集硬件特征后生成确定性唯一标识：

| 平台 | 采集项 |
|------|--------|
| **macOS** | IOPlatformUUID、序列号、机型、CPU 品牌、NVMe/SATA 磁盘序列号、GPU 芯片型号、物理网卡 MAC |
| **Windows** | UUID、BIOS/主板序列号、CPU ID、磁盘序列号、GPU PNP ID、物理网卡 MAC（过滤虚拟适配器） |

所有值标准化（去重、排序、小写化）后拼接，经 **SHA-256** 哈希生成 64 位十六进制 SIMEI。

### 6.4 本地推理服务（Python LocalServer）

#### 模块结构

```
localserver/
├── main.py                    # FastAPI 入口 (uvicorn :8765)，启动时自动恢复
├── config.py                  # YAML 配置加载（数据类单例）
├── api/
│   └── init.py                # POST /api/init/device  GET /api/init/status
├── service/
│   ├── credential.py          # 凭证持久化 (~/.deeppool/device_credential.json)
│   └── manager.py             # ServiceManager — 推理服务完整生命周期管理
├── engine/                    # 多后端推理引擎抽象层
│   ├── base.py                # LLMEngine 抽象基类（对齐 OpenAI 语义）
│   ├── selector.py            # 根据平台/硬件自动选择引擎
│   ├── vllm_mlx.py            # MLX Metal 引擎（macOS Apple Silicon）
│   ├── vllm_engine.py         # vLLM CUDA 引擎（Linux NVIDIA GPU）
│   ├── llamacpp.py            # llama.cpp GGUF 引擎（通用 CPU/弱 GPU）
│   └── reasoning.py           # 推理模型思考内容解析（<think> 标签拆分）
├── model/
│   ├── downloader.py          # HuggingFace Hub 模型下载（默认国内镜像 hf-mirror.com）
│   └── registry.py            # 本地模型路径解析 (~/.deeppool/models/)
├── rpc/
│   ├── infer_server.py        # gRPC LLMInferService 实现（非流式+流式）
│   ├── platform_client.py     # Platform Manager gRPC 客户端
│   └── node_manager_client.py # NodeManager 双向流长连接客户端
└── generated/                 # Protobuf 自动生成代码
```

#### 推理引擎自动选择策略

```python
selector.py 决策逻辑:

if 平台下发指定 engine:
    使用指定引擎
elif macOS + Apple Silicon (M系列) + macOS >= 13.5:
    → VLLMMLXEngine (MLX Metal 加速)
elif macOS + Intel:
    → LlamaCppEngine (llama.cpp GGUF)
elif Linux:
    → VLLMEngine (vLLM CUDA)
```

| 引擎 | 适用平台 | 加速方式 | 模型格式 |
|------|---------|---------|---------|
| **VLLMMLXEngine** | macOS Apple Silicon | Metal GPU | HuggingFace 原生 |
| **LlamaCppEngine** | macOS Intel / 通用 | CPU / 弱 GPU | GGUF 量化 |
| **VLLMEngine** | Linux + NVIDIA | CUDA | HuggingFace 原生 |

#### 推理模型思考内容解析

支持解析 `<think>...</think>` 标签，自动拆分为 `reasoning_content` 和 `content`：

| 解析器 | 适用模型 | 触发方式 |
|--------|---------|---------|
| DeepSeekR1Parser | DeepSeek R1 系列 | 模型名自动推断 |
| Qwen3Parser | Qwen3 系列 | 模型名自动推断 |
| ThinkTagParser | 通用 | 兜底匹配 |

#### 设备初始化流程

`POST /api/init/device` 触发的完整编排：

```
1. gRPC → Manager.GetModelDeployConfig (获取模型部署配置)
2. HuggingFace 下载模型 (支持缓存跳过)
3. 引擎选择 + 模型加载 + 推理引擎启动
4. 启动本地 gRPC 推理服务 (LLMInferService)
5. gRPC → Manager.RegisterDevice (注册设备到平台)
6. 持久化凭证到 ~/.deeppool/device_credential.json
7. 启动 NodeManager 隧道客户端 (双向流长连接)
```

#### NodeManager 隧道客户端

建立 gRPC 双向流长连接，持续运行：

- **注册**：首条消息发送 simei + token + model_name + engine
- **心跳**：按服务端下发间隔定时发送 Heartbeat
- **任务执行**：收到 InferenceTask 后调用本地引擎，回传 TaskResult（非流式）或 TaskStreamChunk（流式）
- **自动重连**：指数退避（2s → 4s → 8s → ... → 60s max）

---

## 7. 端到端推理数据流

### 7.1 DeepNode 路径（非流式）

```
外部调用方                  Manager Gateway              NodeManager              DeepNode
    │                          │                            │                       │
    │ POST /v1/chat/completions│                            │                       │
    │ (JSON, stream=false)     │                            │                       │
    │─────────────────────────▶│                            │                       │
    │                          │ Auth + RateLimit + Quota   │                       │
    │                          │ resolveBackend → deepnode  │                       │
    │                          │                            │                       │
    │                          │ gRPC ChatCompletion        │                       │
    │                          │───────────────────────────▶│                       │
    │                          │                            │ FindByModel → pick    │
    │                          │                            │ Send(InferenceTask)   │
    │                          │                            │──────────────────────▶│
    │                          │                            │                       │ 本地推理
    │                          │                            │      TaskResult       │
    │                          │                            │◀──────────────────────│
    │                          │      gRPC Response         │                       │
    │                          │◀───────────────────────────│                       │
    │                          │                            │                       │
    │   JSON Response          │                            │                       │
    │◀─────────────────────────│                            │                       │
```

### 7.2 Provider 路径

```
外部调用方                  Manager Gateway                云端 API
    │                          │                              │
    │ POST /v1/chat/completions│                              │
    │─────────────────────────▶│                              │
    │                          │ Auth + RateLimit + Quota     │
    │                          │ resolveBackend → provider    │
    │                          │                              │
    │                          │ HTTP POST (model→upstream)   │
    │                          │─────────────────────────────▶│
    │                          │                              │
    │                          │     JSON Response            │
    │                          │◀─────────────────────────────│
    │                          │ rewrite model name           │
    │   JSON Response          │                              │
    │◀─────────────────────────│                              │
```

### 7.3 Hybrid 路径（含 Failover）

```
外部调用方                  Manager Gateway
    │                          │
    │ POST /v1/chat/completions│
    │─────────────────────────▶│
    │                          │ Auth + RateLimit + Quota
    │                          │ resolveBackend → hybrid
    │                          │
    │                          │ extractRequestFeatures
    │                          │ PolicyCache.Get → policy.Match
    │                          │ → candidates: [deepnode-A, provider-B]
    │                          │
    │                          │ try deepnode-A → gRPC → NodeManager
    │                          │   ├── 成功 → 返回
    │                          │   └── 失败 → try provider-B → HTTP
    │                          │       ├── 成功 → 返回
    │                          │       └── 失败 → 503
    │                          │
    │   JSON Response          │
    │◀─────────────────────────│
```

### 7.4 流式推理 (SSE)

```
外部调用方                  Manager Gateway              NodeManager              DeepNode
    │                          │                            │                       │
    │ POST /v1/chat/completions│                            │                       │
    │ (JSON, stream=true)      │                            │                       │
    │─────────────────────────▶│                            │                       │
    │                          │ gRPC ChatCompletionStream  │                       │
    │                          │───────────────────────────▶│                       │
    │                          │                            │ Send(InferenceTask)   │
    │                          │                            │──────────────────────▶│
    │  data: {"choices":[...]} │  gRPC Stream Chunk         │   TaskStreamChunk     │
    │◀─────────────────────────│◀───────────────────────────│◀──────────────────────│
    │  data: {"choices":[...]} │  gRPC Stream Chunk         │   TaskStreamChunk     │
    │◀─────────────────────────│◀───────────────────────────│◀──────────────────────│
    │  ...                     │  ...                       │   ...                 │
    │  data: [DONE]            │                            │   TaskStreamChunk(done│
    │◀─────────────────────────│                            │                       │
```

---

## 8. 通信协议矩阵

| 通道 | 协议 | 端口 | 方向 | 用途 |
|------|------|------|------|------|
| 前端 → Manager | HTTP REST | 8080 | 单向 | 用户认证、设备查询、模型管理 |
| 前端 → LocalServer | HTTP REST | 8765 | 单向 | 设备初始化触发、状态查询 |
| 外部调用方 → Manager Gateway | HTTP (OpenAI API) | 8080 | 单向 | **推理请求**（JSON / SSE） |
| Manager Gateway → NodeManager | gRPC (Unary/Stream) | 9092 | 单向 | DeepNode 推理转发 |
| Manager Gateway → 云端 Provider | HTTPS | 443 | 单向 | Provider 推理代理 |
| LocalServer → Manager | gRPC (Unary) | 9090 | 单向 | 模型配置获取、设备注册 |
| LocalServer ↔ NodeManager | gRPC (BidiStream) | 9092 | 双向长连接 | 鉴权、心跳、任务下发与结果回传 |

---

## 9. 技术栈总结

| 层面 | 技术选型 |
|------|---------|
| **平台后端** | Go 1.23，标准库 `net/http`（无框架），gRPC |
| **数据库** | MySQL 8（InnoDB, utf8mb4），go-sql-driver/mysql |
| **序列化 / RPC** | Protocol Buffers 3，gRPC（含双向流） |
| **密码学** | bcrypt（密码哈希），crypto/rand（Token 生成），SHA-256（设备指纹） |
| **配置管理** | YAML（gopkg.in/yaml.v3, PyYAML） |
| **桌面客户端** | Tauri 2.0（Rust 原生层 + Vue 3 Web 视图） |
| **前端** | Vue 3 (Composition API) + TypeScript + Vite 6 + vue-i18n |
| **本地推理服务** | Python 3.13，FastAPI + uvicorn，grpcio |
| **推理引擎** | MLX (Apple Metal)、vLLM (NVIDIA CUDA)、llama.cpp (CPU/通用) |
| **模型管理** | HuggingFace Hub（自动下载，国内镜像加速） |
| **打包发布** | PyInstaller (Python → 单文件) + cargo tauri build (.dmg / .nsis) |
| **部署** | Shell 脚本，交叉编译 linux/amd64，SCP 远程部署 |

---

## 10. 关键设计决策

### 10.1 OpenAI API 完全兼容

从 Protobuf 定义到 HTTP 接口，全面对齐 OpenAI Chat Completions API。外部调用方无需任何适配即可接入，只需将 base_url 指向 DeepPool Manager。支持 function calling、streaming SSE、reasoning_content 等高级特性。

### 10.2 模型三分类与统一融合调度

系统将模型分为 `deepnode`（本地推理）、`provider`（云端 API）、`hybrid`（融合调度）三种类型，通过统一的 Gateway 入口处理。调用方只需指定 model 名称，底层是本地推理还是云端代理完全透明。这一设计使得：
- **同一模型可同时有本地和云端两个来源**（hybrid 类型实现自动 failover）
- **新增 provider 只需在管控台注册**，无需修改任何代码
- **调用方体验一致**：无论实际后端是什么，API 行为和响应格式完全一致

### 10.3 Hybrid 融合调度与故障转移

Hybrid 模型是生产环境的推荐做法，核心优势：
- **条件路由**：根据请求特征（token 数、是否 FC、是否推理、是否视觉）自动选择最优子模型
- **Round-Robin 负载均衡**：同一组 targets 间轮询，避免单点压力
- **自动 Failover**：首选子模型失败时自动切换到下一个，全部失败才返回 503
- **YAML 策略可热更新**：路由策略存储在 DB，PolicyCache 每 10 秒 polling 同步，修改后 ~10 秒生效
- **防递归保护**：子模型不允许也是 hybrid 类型，避免无限嵌套

### 10.4 全链路 Token 治理

网关在请求全链路提供多层次治理能力：

```
Layer 1 — 接入控制
  职责: API Key 鉴权 + RPM/TPM 限流 + Token 配额
  粒度: API Key 维度

Layer 2 — 安全护栏 (Guardrails)
  职责: 输入/输出内容安全评估
  策略: LLM 驱动评估, 阻断/审计
  粒度: API Key + 规则维度

Layer 3 — 融合调度
  职责: 模型级路由 (deepnode/provider/hybrid)
  策略: 路由策略匹配 + Round-Robin + Failover
  粒度: 模型维度

Layer 4 — 追踪与评估 (Trace + AI Judge)
  职责: 完整日志采集 + AI 自动评测 + 人工标注
  策略: 异步 best-effort 写入用户外部 DB
  粒度: API Key + 模型维度

Layer 5 — 用量统计
  职责: Token 用量日汇总 + 阶梯计费 + 成本分析
  粒度: API Key + 模型 + 日期
```

### 10.5 gRPC 双向流隧道

设备通过 gRPC BidiStream 与 NodeManager 保持长连接。这一设计的关键优势：
- **无需设备暴露公网端口**：设备主动发起连接，穿透 NAT/防火墙
- **复用单一 TCP 连接**：注册、心跳、任务下发、结果回传全部在同一条流中完成
- **极低延迟**：避免为每次推理请求建立新连接

### 10.6 分片连接表（ConnectionHub）

256 分片 + FNV-1a 哈希的设计面向百万级长连接场景：
- 大幅降低锁竞争（相比全局锁，冲突概率降低 256 倍）
- O(1) 查找复杂度
- 独立心跳巡检，超时自动剔除

### 10.7 多引擎抽象 + 统一 FC 解析

统一的 `LLMEngine` 抽象基类使得推理后端可插拔。根据平台和硬件自动选择最优引擎，对上层完全透明。

Function Call 解析采用注册表架构，每种模型（GLM/Kimi/DeepSeek/Qwen/Gemma4/Llama/Mistral）有独立的 `ToolCallExtractor`，通过 `detect_model_type()` 自动选择，支持 auto fallback 尝试所有格式。

### 10.8 凭证持久化与自动恢复

设备初始化后将 simei + token 持久化到 `~/.deeppool/device_credential.json`。LocalServer 重启时自动读取凭证，恢复推理服务和 NodeManager 隧道连接，无需用户再次手动初始化。

### 10.9 安全设计

- **SQL 注入防护**：所有数据库操作均使用参数化查询（`?` 占位符）
- **密码安全**：bcrypt 哈希存储，不存明文
- **API Key 加密**：数据库中 AES-256-GCM 加密存储，运行时解密
- **IP 防伪造**：服务端主动从 gRPC Peer / X-Forwarded-For / X-Real-IP 提取真实 IP
- **输入校验**：JSON 请求体禁止未知字段，手机/邮箱/密码均有正则和长度校验
- **路径安全**：模型路径解析包含穿越检查，防止目录遍历攻击

---

## 11. 构建与部署

### 11.1 全量构建 (build.sh)

```
1. gen_proto    → protoc 生成 Go + Python 的 protobuf/gRPC 代码
2. build_backend → go build 编译平台微服务 (manager, nodemanager, experiment)
3. build_portal_web / build_control_web → npm build 编译前端
```

### 11.2 开发模式 (dev.sh)

同时启动所有组件：Manager + NodeManager + Experiment + LocalServer + Tauri Dev

### 11.3 远程部署 (deploy_dev.sh)

```
交叉编译 linux/amd64 (CGO_ENABLED=0)
 → SCP 上传至 root@<server>:/opt/deeppool/
 → nohup 启动后端服务
 → 健康检查验证
```

### 11.4 独立启动

| 脚本 | 用途 |
|------|------|
| `run_platformserver.sh manager` | 单独启动 Manager |
| `run_platformserver.sh nodemanager` | 单独启动 NodeManager |
| `run_platformweb.sh` | 单独启动管控前端 (Vite dev server) |
| `run_client.sh` | 启动 DeepNode（Python LocalServer + Tauri Dev） |
