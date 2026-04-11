# DeepNode 技术设计文档

> **版本**：v1.0 &nbsp;|&nbsp; **更新日期**：2026-03-25

## 1. 产品定位

DeepNode 是 **DeepPool 分布式 LLM 推理算力池** 的桌面客户端应用。用户安装 DeepNode 后，本地设备将自动成为 DeepPool 网络的推理算力节点——对外提供 LLM 推理服务，对内通过 gRPC 隧道与平台保持常驻连接、接收推理任务并回传结果。

**核心价值**：将闲置的 Mac Apple Silicon、Linux GPU 服务器等硬件算力组网成分布式推理集群，无需用户配置环境、手动下载模型，一键启动即可贡献算力。

---

## 2. 整体架构

### 2.1 三层架构总览

DeepNode 采用 **三层分离架构**，每一层以独立技术栈实现，层间通过 IPC / HTTP / 事件进行通信：

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 1 — Tauri Desktop Shell (Rust)                                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  • 原生窗口管理 (1200×800)、系统菜单 (Settings)                │  │
│  │  • 设备指纹 (SIMEI) 生成 — 硬件特征 → SHA-256                  │  │
│  │  • Sidecar 生命周期管理 — 启动/监控/清理 LocalServer 进程       │  │
│  │  • Tauri Commands: get_device_fingerprint, stop_localserver    │  │
│  │  • 事件机制: localserver-ready / localserver-failed            │  │
│  └────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 2 — Frontend UI (Vue 3 + TypeScript + Vite)                   │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  • AuthView       — 登录 / 注册                                │  │
│  │  • DeviceInitView — 设备初始化引导（进度条 + 日志面板）          │  │
│  │  • DeviceDetailView — 实时运行仪表板（GPU/温度/流量/Token 统计） │  │
│  │  • 国际化 (i18n) — 中 / 英双语                                 │  │
│  │  • 跨平台 HTTP 封装 — Tauri Fetch (prod) / native fetch (dev)  │  │
│  └────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│  Layer 3 — LocalServer (Python 3.13 + FastAPI + gRPC)                │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  • FastAPI HTTP 服务 (:8765) — 设备初始化/状态/统计 API         │  │
│  │  • 多引擎推理 — MLX Metal / vLLM CUDA / llama.cpp              │  │
│  │  • gRPC 推理服务 — LLMInferService (非流式 + 服务端流式)        │  │
│  │  • 平台通信 — Manager gRPC 客户端 + NodeManager 双向流隧道      │  │
│  │  • 模型管理 — HuggingFace 自动下载 + 本地缓存                  │  │
│  │  • 推理统计 — SQLite 持久化 + 定时上报                          │  │
│  │  • 凭证管理 — ~/.deeppool/device_credential.json 持久化         │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 2.2 系统交互全景

```
                           Platform (远端服务器)
                     ┌──────────┬───────────────┐
                     │ Manager  │  NodeManager   │
                     │ :9090    │  :9092         │
                     └────┬─────┴──────┬────────┘
                          │            │
         gRPC 请求/响应    │            │  gRPC 双向流 (BidiStream)
    (配置获取/设备注册     │            │  (注册/心跳/任务下发/结果回传)
     /日志上报)            │            │
                          │            │
                     ┌────┴────────────┴────────┐
                     │   LocalServer (Python)    │
                     │   FastAPI :8765           │
                     │   gRPC InferServer :动态  │
                     └──────────┬────────────────┘
                                │
                          HTTP / Tauri IPC
                                │
                     ┌──────────┴────────────────┐
                     │    Vue.js Frontend         │
                     │    (Tauri WebView)         │
                     └──────────┬────────────────┘
                                │
                          Tauri Commands
                                │
                     ┌──────────┴────────────────┐
                     │    Tauri Shell (Rust)      │
                     │    原生桌面窗口 + Sidecar   │
                     └───────────────────────────┘
```

---

## 3. 目录结构

```
clients/deepnode/
├── app/                          # 前端 Vue.js 应用 (Tauri WebView 内嵌)
│   ├── src/
│   │   ├── App.vue               #   根组件 — 页面状态机入口
│   │   ├── config.ts             #   全局 API 地址配置
│   │   ├── http.ts               #   跨平台 HTTP 请求封装
│   │   ├── main.ts               #   Vue 应用启动
│   │   ├── i18n/                  #   国际化 (中/英)
│   │   └── views/
│   │       ├── AuthView.vue      #     登录/注册页
│   │       ├── DeviceInitView.vue#     设备初始化引导页
│   │       └── DeviceDetailView.vue#   运行仪表板
│   └── vite.config.ts
│
├── localserver/                  # Python 后端服务 (FastAPI + gRPC)
│   ├── main.py                   #   FastAPI 入口，启动/恢复/关停编排
│   ├── config.py                 #   YAML 配置加载（数据类 + 三级结构）
│   ├── config.yaml               #   运行时配置文件
│   ├── log_setup.py              #   日志初始化（控制台 + 文件双输出）
│   ├── requirements.txt          #   Python 依赖
│   ├── api/                      #   HTTP API 路由
│   │   ├── __init__.py           #     路由注册
│   │   ├── init.py               #     设备初始化/停止/状态查询
│   │   └── stats.py              #     推理统计 + 硬件信息
│   ├── engine/                   #   推理引擎抽象层
│   │   ├── __init__.py           #     引擎包导出
│   │   ├── base.py               #     LLMEngine 抽象基类 + 全套数据结构
│   │   ├── selector.py           #     引擎自动选择（按 OS/芯片/版本）
│   │   ├── vllm_mlx.py           #     MLX Metal 引擎 (Apple Silicon)
│   │   ├── vllm_engine.py        #     vLLM 引擎 (Linux NVIDIA GPU)
│   │   ├── llamacpp.py           #     llama.cpp 引擎 (Intel Mac / 兼容)
│   │   └── reasoning.py          #     推理思考内容解析器 (<think> 标签)
│   ├── model/                    #   模型管理
│   │   ├── downloader.py         #     HuggingFace 模型下载
│   │   └── registry.py           #     本地路径解析
│   ├── rpc/                      #   gRPC 通信层
│   │   ├── infer_server.py       #     gRPC 推理服务端
│   │   ├── platform_client.py    #     Platform Manager gRPC 客户端
│   │   └── node_manager_client.py#     NodeManager 双向流隧道客户端
│   ├── service/                  #   业务服务层
│   │   ├── manager.py            #     ServiceManager — 引擎生命周期管理
│   │   ├── credential.py         #     设备凭证持久化
│   │   ├── statistics.py         #     SQLite 推理统计数据库
│   │   └── log_reporter.py       #     推理日志定时上报
│   └── generated/                #   Protobuf 生成的 gRPC 代码
│       ├── llm_infer_pb2*.py
│       ├── manager_service_pb2*.py
│       └── node_tunnel_pb2*.py
│
├── src-tauri/                    # Rust Tauri 桌面壳
│   ├── src/
│   │   ├── main.rs               #   Tauri 应用入口 — sidecar 生命周期
│   │   └── utils/
│   │       └── device_fingerprint.rs  # 设备指纹 (SIMEI) 生成
│   ├── Cargo.toml
│   └── tauri.conf.json
│
└── build_mac.sh                  # macOS DMG 一键构建脚本
```

---

## 4. 启动流程

DeepNode 的启动是一个 **级联式** 过程，从 Tauri 桌面壳逐层触发直至推理服务就绪：

```
┌──────────────────────────────────────────────────────────────────────┐
│ Phase 1: Tauri 桌面壳启动 (main.rs)                                  │
│                                                                      │
│  1. 构建原生菜单 (Settings)                                          │
│  2. cleanup_stale_localserver()                                      │
│     └─ lsof -ti tcp:8765 → kill 残留进程                              │
│  3. start_localserver_sidecar()                                      │
│     └─ 以子进程启动 PyInstaller 打包的 localserver 二进制              │
│  4. 后台线程: wait_for_localserver()                                  │
│     └─ TCP 探测 127.0.0.1:8765 (200ms 间隔, 120s 超时)               │
│     └─ 就绪 → emit "localserver-ready"                               │
│     └─ 超时 → emit "localserver-failed"                              │
│  5. 注册 Tauri Commands: get_device_fingerprint, stop_localserver    │
│  6. 打开 WebView 窗口 (1200×800)                                     │
└──────────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────────┐
│ Phase 2: Vue 前端启动 (App.vue)                                      │
│                                                                      │
│  1. 检查 localStorage 中的 token                                     │
│     └─ 无 token → 显示 AuthView (登录/注册)                          │
│  2. 监听 "localserver-ready" 事件                                    │
│  3. 查询 platform API 检测设备注册状态                                │
│     └─ 未注册/服务未就绪 → 显示 DeviceInitView                       │
│     └─ 已就绪 → 显示 DeviceDetailView                                │
└──────────────────────────────────────────────────────────────────────┘
                               ↓
┌──────────────────────────────────────────────────────────────────────┐
│ Phase 3: LocalServer 启动 (main.py)                                  │
│                                                                      │
│  1. FastAPI + Uvicorn 启动 HTTP 服务 (:8765)                         │
│  2. on_startup 事件 → 后台线程 _try_restore_and_connect():           │
│     a. 读取持久化凭证 (~/.deeppool/device_credential.json)           │
│     b. gRPC → Manager.GetModelDeployConfig (获取部署配置)             │
│     c. ServiceManager.ensure_service()                               │
│        ├─ 下载模型 (HuggingFace, 支持缓存跳过)                       │
│        ├─ 自动选择引擎 (MLX / vLLM / llama.cpp)                      │
│        ├─ 加载模型到 GPU/CPU                                         │
│        └─ 启动 gRPC 推理服务 (LLMInferService)                       │
│     d. 建立 NodeManager 双向流隧道长连接                              │
│     e. 启动推理日志定时上报 (LogReporter)                             │
│  3. 凭证缺失时静默跳过, 等待前端触发初始化                            │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.1 页面状态机

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
     │ AuthView │       │ 等待 localserver │
     │ 登录/注册 │       └──────┬───────┘
     └──────────┘              │
                      ┌────────┴────────┐
                      ▼                 ▼
               设备未就绪           设备已就绪
          ┌────────────────┐  ┌──────────────────┐
          │ DeviceInitView │  │ DeviceDetailView  │
          │ 初始化引导     │  │ 实时统计仪表板    │
          └────────────────┘  └──────────────────┘
```

### 4.2 窗口关闭行为

Tauri 层拦截窗口关闭事件，提供两种策略：
- **彻底退出**：清除 WebView localStorage → kill sidecar 进程树 → 退出应用
- **后台运行**：仅隐藏窗口，sidecar 持续运行，设备保持在线

---

## 5. 核心模块设计

### 5.1 推理引擎层 (engine/)

#### 5.1.1 架构模式

采用 **策略模式 + 工厂模式**，通过统一抽象基类屏蔽底层引擎差异：

```
                    ┌─────────────────────┐
                    │   LLMEngine (ABC)   │  ← 抽象基类 (base.py)
                    │                     │
                    │  + load()           │
                    │  + unload()         │
                    │  + chat_complete()  │  ← 非流式推理
                    │  + stream_chat_complete() │ ← 流式推理 (Generator)
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
    │ VLLMMLXEngine   │ │ VLLMEngine   │ │ LlamaCppEngine  │
    │ (vllm_mlx.py)   │ │(vllm_engine) │ │ (llamacpp.py)   │
    │                 │ │              │ │                 │
    │ Apple Silicon   │ │ Linux NVIDIA │ │ Intel Mac /     │
    │ Metal GPU       │ │ CUDA GPU     │ │ 通用 CPU        │
    │ SafeTensors     │ │ SafeTensors  │ │ GGUF 量化       │
    └─────────────────┘ └──────────────┘ └─────────────────┘
```

#### 5.1.2 引擎自动选择 (selector.py)

```python
# 决策逻辑伪代码
if 平台下发指定 engine:
    使用指定引擎
elif macOS + Apple Silicon (M系列) + macOS >= 13.5:
    → VLLMMLXEngine  # Metal 硬件加速, 最优性能
elif macOS + Intel:
    → LlamaCppEngine  # GGUF 量化, CPU 兼容模式
elif Linux:
    → VLLMEngine      # vLLM + CUDA, 企业级吞吐
```

| 引擎 | 适用环境 | 底层库 | 模型格式 | 加速方式 |
|------|---------|--------|---------|---------|
| **VLLMMLXEngine** | macOS Apple Silicon, macOS ≥ 13.5 | mlx-lm / mlx-vlm | SafeTensors | Metal GPU |
| **VLLMEngine** | Linux + NVIDIA GPU | vLLM | SafeTensors/bin | CUDA |
| **LlamaCppEngine** | macOS Intel / 低版本 macOS / 通用 | llama-cpp-python | GGUF | CPU |

#### 5.1.3 数据结构体系 (base.py)

完整对齐 OpenAI Chat Completions API 的数据结构：

```
请求侧:
  ChatCompletionRequest
  ├── messages: List[ChatMessage]     # system / user / assistant / tool
  ├── tools: List[ToolDef]            # Function Calling 工具定义
  ├── response_format: ResponseFormat  # json_object / text
  ├── temperature, top_p, max_tokens  # 采样参数
  └── enable_thinking: bool           # 扩展字段: 启用推理思考

响应侧 (非流式):
  ChatCompletionResult
  ├── choices: List[ChatChoice]
  │   └── message: ChatMessage
  │       ├── content: str            # 回答内容
  │       └── reasoning_content: str  # 思考内容 (DeepSeek R1 / Qwen3)
  └── usage: UsageStats
      └── completion_tokens_details: CompletionTokensDetails
          └── reasoning_tokens: int

响应侧 (流式):
  ChatCompletionChunkResult
  ├── choices: List[StreamChoice]
  │   └── delta: StreamDelta
  └── usage: UsageStats (最后一个 chunk)
```

#### 5.1.4 推理思考内容解析器 (reasoning.py)

支持 `<think>...</think>` 标签的自动拆分，将思考过程和最终回答分离：

```
                     ┌───────────────────┐
                     │ ThinkTagParser    │  ← 基类 (模板方法模式)
                     │ (通用 <think> 解析)│
                     └────────┬──────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          ┌──────────────────┐ ┌─────────────────┐
          │ DeepSeekR1Parser │ │ Qwen3Parser     │
          │ (DeepSeek R1 系列)│ │ (Qwen3 系列)    │
          └──────────────────┘ └─────────────────┘
```

- **非流式模式**：完整文本一次性拆分为 `reasoning_content` + `content`
- **流式模式**：逐 token 状态机，实时判断当前在 thinking 还是 content 阶段

### 5.2 服务管理器 (service/manager.py)

**`ServiceManager` 单例** — 推理服务的完整生命周期控制中心：

```
                  ensure_service(deploy_cfg)
                           │
                  ┌────────▼────────┐
                  │ 相同模型?        │──是──→ 复用现有服务 (幂等)
                  └────────┬────────┘
                           │ 否
                  ┌────────▼────────┐
                  │ shutdown()      │
                  │ 停止旧引擎+gRPC │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 引擎选择        │  ← selector.select_engine()
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ auto_fill_defaults│  ← 按硬件自适应配置
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 下载模型        │  ← HuggingFace (支持缓存)
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 创建引擎 + 加载  │  ← engine.load()
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │ 启动 gRPC Server│  ← LLMInferServicer
                  └────────┬────────┘
                           │
                      服务就绪 ✓
```

**关键特性**：
- **幂等操作**：相同模型配置不会重复加载
- **安全关停**：先停 gRPC Server（优雅等待请求完成），再 unload 引擎（释放 GPU 资源）
- **状态暴露**：`RunningService` 数据类记录当前运行模型、引擎类型、端口、启动时间

### 5.3 gRPC 通信层 (rpc/)

#### 5.3.1 三个 gRPC 协议

| 协议 | 文件 | 方向 | 功能 |
|------|------|------|------|
| **manager_service** | `platform_client.py` | Node → Platform Manager | 设备注册、获取模型部署配置、上报推理日志、更新设备状态 |
| **llm_infer** | `infer_server.py` | 外部 → Node gRPC Server | Chat Completions 推理服务（非流式 + 服务端流式） |
| **node_tunnel** | `node_manager_client.py` | Node ↔ NodeManager | 双向流长连接 — 注册/心跳/接收推理任务/回传结果 |

#### 5.3.2 NodeManager 隧道 — 核心通信机制

```
┌─────────────────────────────────────────────────────────────────┐
│                NodeManagerClient                                 │
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────────────────────┐  │
│  │ _MessageQueue    │     │ 连接生命周期                      │  │
│  │ (线程安全队列)    │     │                                  │  │
│  │                  │     │  Register ──→ Heartbeat Loop     │  │
│  │  put(msg) ───┐   │     │      │                           │  │
│  │              │   │     │      ▼                           │  │
│  │  __next__() ◀┘   │     │  Event Loop:                     │  │
│  │  (gRPC iterator) │     │    • inference_task → 独立线程执行│  │
│  │                  │     │    • task_cancel → 取消推理      │  │
│  └──────────────────┘     │    • 心跳超时 → 自动重连         │  │
│                           └──────────────────────────────────┘  │
│                                                                  │
│  重连策略: 指数退避 (2s → 4s → 8s → ... → 60s max)              │
└─────────────────────────────────────────────────────────────────┘
```

**协议交互时序**：

```
Phase 1 — 注册鉴权:
  Node ──[RegisterRequest(simei, token, model, engine)]──▶ NodeManager
  Node ◀──[RegisterResponse(session_id, heartbeat_interval)]── NodeManager

Phase 2 — 事件循环:
  Node ──[Heartbeat]──▶ NodeManager  (定时心跳, 服务端回复 pong)
  NodeManager ──[InferenceTask(task_id, request)]──▶ Node  (下发推理任务)
  Node ──[TaskResult(task_id, response)]──▶ NodeManager    (非流式结果)
  Node ──[TaskStreamChunk(task_id, chunk, done)]──▶ NodeManager (流式结果)
  NodeManager ──[TaskCancel(task_id, reason)]──▶ Node       (取消任务)
```

**设计要点**：
- **`_MessageQueue`**：线程安全消息队列，实现 gRPC 双向流的 request iterator 接口，解耦消息发送和流迭代
- **独立线程执行**：每个推理任务在独立 `threading.Thread` 中运行，避免阻塞事件循环
- **自动重连**：连接断开后指数退避重试（初始 2s，翻倍增长，上限 60s），重连成功后重置退避计数

#### 5.3.3 gRPC 推理服务端 (infer_server.py)

本地 gRPC 推理服务，对外提供 OpenAI 语义兼容的接口：

| gRPC 方法 | 类型 | 说明 |
|-----------|------|------|
| `Health` | Unary | 健康检查 |
| `ChatCompletion` | Unary | 非流式推理 |
| `ChatCompletionStream` | Server-Streaming | 流式推理（逐 chunk 返回） |

**数据转换流程**：
```
gRPC Proto Request → Engine 内部数据结构 → 引擎推理 → Engine 结果 → gRPC Proto Response
```

#### 5.3.4 Platform Manager 客户端 (platform_client.py)

| gRPC 方法 | 说明 |
|-----------|------|
| `GetModelDeployConfig` | 获取模型部署配置（model_name, repo_id, engine, options） |
| `RegisterDevice` | 注册设备（上报硬件信息、模型状态） |
| `UpdateDevice` | 更新设备状态 |
| `ReportInferLogs` | 批量上报推理日志 |

### 5.4 模型管理 (model/)

#### 5.4.1 模型下载 (downloader.py)

```
download_model_hf(repo_id, model_path)
        │
        ▼
  _is_model_cached(model_path)
        │
        ├─ 已缓存 (存在 safetensors/bin/gguf 文件) → 跳过下载
        │
        └─ 未缓存 → huggingface_hub.snapshot_download()
                     └─ 镜像: hf-mirror.com (国内加速)
                     └─ 存储: ~/.deeppool/models/<model_name>/
```

#### 5.4.2 模型路径解析 (registry.py)

- 基础路径：`~/.deeppool/models/`
- 路径计算：`base_path / model_name`
- **安全措施**：路径穿越检查，防止目录遍历攻击

### 5.5 推理统计 (service/statistics.py)

**SQLite 持久化存储**，记录每一次推理请求的详细数据：

```
┌───────────────────────────────────────────────────┐
│ StatisticsDB (SQLite, WAL 模式)                   │
│                                                    │
│ 表: infer_records                                  │
│ ┌────────────────────────────────────────────────┐ │
│ │ id | model | source | prompt_tokens |          │ │
│ │    | completion_tokens | total_tokens |         │ │
│ │    | first_token_ms | total_ms | status |       │ │
│ │    | created_at | reported                      │ │
│ └────────────────────────────────────────────────┘ │
│                                                    │
│ 索引: created_at, source, reported                 │
│ 特性:                                              │
│   • WAL 日志模式 (并发读不阻塞写)                   │
│   • threading.Lock 线程安全                         │
│   • 自动模式迁移 (_migrate_reported_column)         │
│   • 按时间/来源聚合统计快照                          │
└───────────────────────────────────────────────────┘
```

**聚合统计**（`StatsSnapshot`）：
- 总请求数、总 Token 数、平均首 Token 延迟、平均总延迟
- 按 source 分组（local / tunnel）的细分统计
- 按时间窗口过滤

### 5.6 日志上报 (service/log_reporter.py)

**定时批量上报**机制：
- 间隔：60 秒
- 流程：查询 `reported=0` 的记录 → gRPC 批量上报到 Manager → 标记为已上报
- **容错**：上报失败仅记录日志，不影响推理服务正常运行

### 5.7 凭证管理 (service/credential.py)

设备凭证（`simei` + `token`）持久化到 `~/.deeppool/device_credential.json`：
- `save(simei, token)` — 写入凭证
- `load()` → `DeviceCredential | None` — 读取凭证
- LocalServer 启动时自动恢复凭证，用于免交互重连

---

## 6. 资源管理

### 6.1 引擎性能参数自适应 (config.py → EngineConfig)

`auto_fill_defaults()` 根据系统硬件自动推荐最优配置：

| 参数 | 含义 | 自适应策略 |
|------|------|-----------|
| `num_workers` | gRPC 线程池大小 | CPU 核数，llamacpp 上限 4，其他上限 8 |
| `tokenizer_workers` | Tokenizer CPU 线程池 | CPU 核数 / 2，llamacpp 忽略 |
| `prefill_step_size` | Prompt 分步编码大小 | ≥64GB→1024, ≥32GB→512, 其他→256 |
| `max_kv_size` | KV Cache 上限 | ≥64GB→16384, ≥32GB→8192, 其他→4096 |

### 6.2 GPU 显存管理

**MLX 引擎 (Apple Silicon Metal)**：
- `RotatingKVCache` 分页 KV Cache，控制 Metal 显存峰值
- `prefill_step_size` 防止大 prompt 单次 Metal eval OOM
- 推理完成后 `mx.clear_cache()` 释放 Metal 缓存
- Tokenizer 编码/解码卸载到 CPU 线程池，不占 GPU
- `_infer_lock` 互斥锁串行化所有 GPU 推理请求（Metal 线程安全限制）

**vLLM 引擎 (NVIDIA CUDA)**：
- KV Cache 由 vLLM 内部管理
- unload 时调用 `torch.cuda.empty_cache()` 释放显存

**llama.cpp 引擎**：
- `max_kv_size` 映射为 `n_ctx`（上下文长度）
- 内部线程锁保护推理并发

### 6.3 硬件信息采集 (api/stats.py)

| 平台 | GPU 信息来源 | CPU/内存来源 |
|------|-------------|-------------|
| **macOS** | `system_profiler SPDisplaysDataType` | `psutil` |
| **Linux** | `nvidia-smi` (名称/利用率/温度) | `psutil` |

---

## 7. 任务处理系统

### 7.1 两类推理任务来源

| 来源 | 标识 | 入口 | 说明 |
|------|------|------|------|
| **本地直连** | `source=local` | gRPC `LLMInferServicer` | 外部通过 gRPC 直接调用本地推理服务 |
| **隧道下发** | `source=tunnel` | `NodeManagerClient._execute_task()` | NodeManager 通过双向流下发 `InferenceTask` |

### 7.2 任务执行流程

```
接收请求 (gRPC proto / tunnel proto)
    │
    ▼
Proto → Engine 数据结构转换
    │
    ▼
engine.chat_complete() / stream_chat_complete()
    │
    ├─ 非流式: 等待完整结果 → 返回 ChatCompletionResult
    │
    └─ 流式: Generator 逐 chunk yield → 逐个回传
    │
    ▼
Engine 结果 → Proto 转换
    │
    ▼
回传响应 + 记录统计到 StatisticsDB
```

### 7.3 并发控制

| 引擎 | 策略 | 原因 |
|------|------|------|
| MLX | `_infer_lock` 互斥锁串行化 | Metal API 线程安全限制 |
| vLLM | vLLM 内部并发管理 | 内置 request scheduler |
| llama.cpp | 内部线程锁 | 单实例串行推理 |

---

## 8. 配置系统

### 8.1 三级配置结构

```python
AppConfig                       # 应用根配置
├── ServerConfig                #   HTTP 服务: host, port
│   ├── host: str = "127.0.0.1"
│   └── port: int = 8765
├── PlatformConfig              #   平台 gRPC 端点
│   ├── manager_addr: str       #     Manager gRPC 地址
│   ├── scheduler_addr: str     #     Scheduler gRPC 地址
│   └── nodemanager_addr: str   #     NodeManager gRPC 地址
├── LogConfig                   #   日志配置
│   ├── level: str = "INFO"
│   ├── log_dir: str
│   └── backup_count: int = 7
└── EngineConfig                #   推理引擎性能参数 (10+ 可调项)
    ├── num_workers: int
    ├── tokenizer_workers: int
    ├── prefill_step_size: int
    ├── max_kv_size: int
    └── ... (更多引擎级参数)
```

### 8.2 加载优先级

```
代码参数 > 环境变量 LOCALSERVER_CONFIG > 默认 config.yaml
```

### 8.3 全局单例

```python
init_config()  # 启动时加载一次
get_config()   # 全局访问
```

---

## 9. 存储与持久化

| 存储位置 | 内容 | 格式 | 访问方式 |
|---------|------|------|---------|
| `~/.deeppool/device_credential.json` | 设备凭证 (simei + token) | JSON | credential.py |
| `~/.deeppool/statistics/stats.db` | 推理统计数据 | SQLite (WAL) | statistics.py |
| `~/.deeppool/models/<model_name>/` | 模型文件 | safetensors/bin/gguf | downloader.py |
| `~/.deeppool/logs/localserver.log` | Python 服务日志 | 文本 (按天滚动, 保留 7 天) | log_setup.py |
| `~/.deeppool/logs/deepnode.log` | Tauri 壳日志 | 文本 | main.rs |
| `localStorage` (WebView) | 用户 token + 用户信息 | 字符串/JSON | App.vue |

---

## 10. 设备指纹生成 (SIMEI)

通过 Tauri Command 暴露给前端调用，跨平台采集硬件特征后生成确定性唯一标识：

### 10.1 硬件特征采集

| 平台 | 采集项 |
|------|--------|
| **macOS** | IOPlatformUUID、序列号、机型、CPU 品牌、NVMe/SATA 磁盘序列号、GPU 芯片型号、物理网卡 MAC |
| **Windows** | UUID、BIOS/主板序列号、CPU ID、磁盘序列号、GPU PNP ID、物理网卡 MAC (过滤虚拟适配器) |

### 10.2 生成算法

```
采集硬件特征值 → 去重 → 排序 → 小写化 → 拼接 → SHA-256 哈希 → 64 位十六进制 SIMEI
```

特点：
- **确定性**：相同硬件始终生成相同 SIMEI
- **唯一性**：不同硬件组合几乎不可能碰撞
- **不可逆**：SHA-256 哈希，无法反推硬件信息

---

## 11. 前端 HTTP 通信 (http.ts)

为解决 macOS WKWebView 对 `http://127.0.0.1` 的跨域限制，采用双模式 HTTP 封装：

| 模式 | 实现 | 适用场景 |
|------|------|---------|
| **Production** | `@tauri-apps/plugin-http` fetch | Tauri 打包后的桌面应用 |
| **Development** | 原生 `fetch` + Vite proxy | 本地开发调试 |

---

## 12. 日志与错误处理

### 12.1 日志系统

**Python LocalServer**：
- 双输出：`stderr` 控制台 + `~/.deeppool/logs/localserver.log` 文件
- 按天滚动：`TimedRotatingFileHandler`，保留 7 天历史
- 统一格式：`%(asctime)s [%(levelname)s] [%(name)s] %(message)s`
- 三方库降噪：uvicorn 日志级别设为 WARNING

**Tauri Shell**：
- 独立简易文件日志 `deepnode.log`
- Unix 时间戳格式

### 12.2 错误处理策略

#### 不阻塞原则

`_try_restore_and_connect()` 中的任何失败仅记录日志，不阻塞 HTTP 服务启动。确保前端 UI 始终可访问。

#### 优雅降级

| 异常场景 | 处理策略 |
|---------|---------|
| 设备凭证缺失 | 静默跳过，等待前端触发初始化 |
| Platform 返回空模型 | 跳过自动恢复，等待手动初始化 |
| gRPC 连接断开 | 指数退避自动重连 (2s → 60s) |
| 推理日志上报失败 | 仅打日志，不影响推理服务 |
| 设备重复注册 | 处理 "duplicate resource" / "already exists" 错误（幂等） |

#### 资源清理链

```
on_shutdown() 触发:
  1. gRPC → Manager.UpdateDevice(status=stopped)  # 上报停止状态
  2. LogReporter.stop()                            # 停止日志上报
  3. NodeManagerClient.disconnect()                 # 断开隧道连接
  4. ServiceManager.shutdown()                      # 关停推理引擎 + gRPC Server
  5. StatisticsDB.close()                           # 关闭统计数据库
```

#### 进程清理 (Tauri 层)

Tauri 壳通过递归进程树遍历 + **SIGTERM → SIGKILL 两轮清理**确保 sidecar 彻底退出，防止端口占用。

---

## 13. 设计模式总结

| 设计模式 | 应用位置 | 说明 |
|---------|---------|------|
| **策略模式** | `engine/` | 三种推理引擎通过统一 `LLMEngine` 接口切换 |
| **工厂模式** | `ServiceManager._create_engine()` | 按 engine_type 创建对应引擎实例 |
| **模板方法** | `reasoning.py` | `ThinkTagParser` 基类 → `DeepSeekR1Parser` / `Qwen3Parser` |
| **单例模式** | `ServiceManager`, `StatisticsDB`, `AppConfig` | 全局唯一实例 |
| **观察者/事件** | Tauri emit/listen | `localserver-ready` / `localserver-failed` / `open-settings` |
| **适配器模式** | `rpc/infer_server.py` | Proto ↔ Engine 数据结构双向转换 |
| **Sidecar 模式** | `main.rs` | Tauri 壳通过子进程管理 Python LocalServer 生命周期 |
| **消息队列** | `NodeManagerClient._MessageQueue` | 线程安全队列适配 gRPC 双向流 iterator |

---

## 14. 构建与发布

### 14.1 macOS 构建流程 (build_mac.sh)

```
1. Python 环境准备
   └─ venv 创建 + 依赖安装 (requirements.txt)

2. PyInstaller 打包
   └─ localserver Python 代码 → 单文件可执行二进制

3. Tauri 构建
   └─ Vue 前端编译 + Rust 编译 + 打包为 .dmg 安装包

4. 产物
   └─ target/release/bundle/dmg/DeepNode_*.dmg
```

### 14.2 依赖清单 (requirements.txt)

| 类别 | 核心依赖 |
|------|---------|
| HTTP 框架 | fastapi, uvicorn |
| gRPC | grpcio, grpcio-tools, protobuf |
| 推理引擎 | mlx, mlx-lm, mlx-vlm, vllm, llama-cpp-python |
| 模型管理 | huggingface-hub, transformers, tokenizers |
| 系统监控 | psutil |
| 配置 | pyyaml |

---

## 15. 技术栈总结

| 层面 | 技术选型 |
|------|---------|
| **桌面外壳** | Tauri 2.0 (Rust)，原生窗口 + Sidecar 进程管理 |
| **前端 UI** | Vue 3 (Composition API) + TypeScript + Vite 6 + vue-i18n |
| **后端服务** | Python 3.13，FastAPI + Uvicorn，grpcio |
| **推理引擎** | MLX (Apple Metal) / vLLM (NVIDIA CUDA) / llama.cpp (CPU) |
| **序列化/RPC** | Protocol Buffers 3，gRPC (含双向流) |
| **数据存储** | SQLite (WAL 模式)，JSON 文件 |
| **模型管理** | HuggingFace Hub（国内镜像 hf-mirror.com） |
| **密码学** | SHA-256 (设备指纹) |
| **打包发布** | PyInstaller (Python → 单文件) + cargo tauri build (.dmg) |
| **国际化** | vue-i18n (中/英双语) |
