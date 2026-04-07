# DeepPool LLM 服务联调测试手册

## 一、环境准备

### 1.1 模型说明

模型配置（名称、HuggingFace 仓库 ID、存储目录等）全部由后端 `GetModelDeployConfig` 接口下发，客户端无需手动配置。

当前 MVP 默认模型：`Qwen/Qwen3-0.6B-8bit`

模型会在设备初始化时自动通过 `huggingface_hub` 下载到 `~/.deeppool/models/` 目录。
如需提前下载：

```bash
pip install huggingface_hub
huggingface-cli download Qwen/Qwen3-0.6B-8bit --local-dir ~/.deeppool/models/Qwen3-0.6B-8bit
```

### 1.2 安装本地 Python 依赖

```bash
cd /Users/loganhu/Documents/eclipse_workspace/DeepPool
source env/bin/activate
pip install -r clients/deepnode/localserver/requirements.txt
```

### 1.3 启动服务

```bash
# 终端 1：启动 platform manager（HTTP :8080 / gRPC :9090）
./run_platformserver.sh

# 终端 2：启动 platform nodemanager（HTTP :8082 / gRPC :9092）
# nodemanager 承载设备长连接 + OpenAI 兼容推理网关
cd platform && go run cmd/nodemanager/main.go

# 终端 3：启动 localserver（HTTP :8765，自动连接 nodemanager 隧道）
./run_client.sh

# 终端 4：启动前端（可选）
./run_platformweb.sh
```

---

## 二、推理引擎说明

项目支持多种推理后端，运行时自动选择（后端 `engine` 字段留空则由客户端检测）：

| 引擎 | 配置值 | 适用环境 | 模型格式 | GPU 加速 |
|------|--------|---------|---------|---------|
| **vLLM-MLX** | `vllm_mlx` | macOS (Apple Silicon) | HF 原始权重 | Metal ✅ |
| **llama.cpp** | `llamacpp` | macOS (Metal) / CPU | GGUF (量化) | Metal ✅ |
| **vLLM** | `vllm` | Linux + NVIDIA GPU | HF 原始权重 | CUDA ✅ |

- macOS Apple Silicon 优先使用 `vllm_mlx`，回退到 `llamacpp`
- Linux 自动使用 `vllm`
- 可通过 platform deploy-config 返回的 `engine` 字段强制指定

---

## 三、接口测试

### 3.1 用户注册

```bash
curl -s http://127.0.0.1:8080/api/v1/users/register \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "testuser",
    "password": "test12345678",
    "phone": "13800138000",
    "email": "test@deeppool.io"
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 1,
    "username": "testuser",
    "phone": "13800138000",
    "email": "test@deeppool.io",
    "created_at": "...",
    "updated_at": "..."
  }
}
```

### 3.2 用户登录（获取 token）

```bash
curl -s http://127.0.0.1:8080/api/v1/users/login \
  -H 'Content-Type: application/json' \
  -d '{
    "account": "testuser",
    "password": "test12345678"
  }' | python3 -m json.tool
```

**预期返回（记录 token 供后续使用）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "token": "<YOUR_TOKEN>",
    "user": { "id": 1, "username": "testuser" }
  }
}
```

### 3.3 获取模型部署配置（manager 新接口）

```bash
curl -s http://127.0.0.1:8080/api/v1/models/deploy-config \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <YOUR_TOKEN>' \
  -d '{
    "simei": "TEST-SIMEI-001",
    "supported_models": ["qwen", "deepseek", "gemini"]
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "model_name": "Qwen3-0.6B-8bit",
    "repo_id": "Qwen/Qwen3-0.6B-8bit",
    "rpc_host": "127.0.0.1",
    "rpc_port": 19090,
    "engine": "",
    "options": {
      "model_base_dir": "~/.deeppool/models"
    }
  }
}
```

### 3.4 设备初始化（本地 localserver，完整链路）

```bash
curl -s http://127.0.0.1:8765/api/init/device \
  -H 'Content-Type: application/json' \
  -d '{
    "simei": "TEST-SIMEI-001",
    "token": "<YOUR_TOKEN>",
    "platform_base_url": "http://127.0.0.1:8080",
    "supported_models": ["qwen"]
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "device_ip": "127.0.0.1",
    "device_config": {
      "init_stage": "ready",
      "simei": "TEST-SIMEI-001",
      "llm_model": "Qwen3-0.6B-8bit",
      "llm_rpc_host": "127.0.0.1",
      "llm_rpc_port": 19090,
      "llm_engine": "vllm_mlx"
    }
  }
}
```

### 3.5 查询设备信息（验证注册成功）

```bash
curl -s http://127.0.0.1:8080/api/v1/devices/TEST-SIMEI-001 \
  -H 'Authorization: Bearer <YOUR_TOKEN>' | python3 -m json.tool
```

---

## 四、gRPC 推理服务测试

> 前提：设备初始化成功后 gRPC 服务已启动（默认端口 19090）
>
> 因服务端未开启 gRPC reflection，所有命令需通过 `-proto` 指定 proto 文件，
> `-import-path` 指定搜索路径。以下命令均在项目根目录执行。
>
> 协议支持 DeepSeek R1 / Qwen3 等推理模型的 `reasoning_content` 字段，
> 以及 `enable_thinking`、`completion_tokens_details` 等 OpenAI 扩展字段。

### 4.1 Health 检查

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{}' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/Health
```

**预期返回：**

```json
{
  "ready": true,
  "modelName": "Qwen3-0.6B-8bit",
  "message": "ok"
}
```

### 4.2 Chat Completions（非流式，基础）

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{
    "request_id": "test-001",
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "system", "content": "你是一个有趣的故事讲述者。"},
      {"role": "user", "content": "你好，讲一个简短的故事"}
    ],
    "max_tokens": 128,
    "temperature": 0.7
  }' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/ChatCompletion
```

**预期返回：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": "1742486400",
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "从前有一只小猫..."
      },
      "finishReason": "stop"
    }
  ],
  "usage": {
    "promptTokens": 18,
    "completionTokens": 50,
    "totalTokens": 68
  }
}
```

### 4.3 Chat Completions（非流式，推理模型 — reasoning_content）

> 适用于 DeepSeek R1 / Qwen3 等推理模型。
> 模型输出的 `<think>...</think>` 会自动拆分为 `reasoning_content` + `content`。
> Qwen3 等模型可通过 `enable_thinking` 控制是否进入思考模式。

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{
    "request_id": "test-reasoning-001",
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？请解释你的推理过程"}
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "enable_thinking": true
  }' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/ChatCompletion
```

**预期返回（推理模型会同时返回 reasoning_content 和 content）：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": "1742486400",
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "1+1等于2。",
        "reasoningContent": "用户问的是基础加法，1+1=2，这是最基本的数学运算..."
      },
      "finishReason": "stop"
    }
  ],
  "usage": {
    "promptTokens": 15,
    "completionTokens": 80,
    "totalTokens": 95,
    "completionTokensDetails": {
      "reasoningTokens": 50
    }
  }
}
```

### 4.4 Chat Completions（非流式，多轮对话携带 reasoning_content 历史）

> 多轮对话时，将上一轮 assistant 的 `reasoning_content` 回传，
> 引擎会自动将其转为 `<think>...</think>` 拼入 prompt，保持推理连贯性。

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{
    "request_id": "test-multiturn-001",
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？"},
      {
        "role": "assistant",
        "content": "1+1等于2。",
        "reasoning_content": "这是基础加法运算，1+1=2。"
      },
      {"role": "user", "content": "那再加3呢？"}
    ],
    "max_tokens": 128,
    "temperature": 0.7,
    "enable_thinking": true
  }' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/ChatCompletion
```

**预期返回：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": "1742486400",
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "2+3等于5。",
        "reasoningContent": "上一步得到1+1=2，现在加3，即2+3=5。"
      },
      "finishReason": "stop"
    }
  ],
  "usage": {
    "promptTokens": 40,
    "completionTokens": 60,
    "totalTokens": 100,
    "completionTokensDetails": {
      "reasoningTokens": 30
    }
  }
}
```

### 4.5 Chat Completions（流式，基础）

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{
    "request_id": "test-stream-001",
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "用一句话介绍自己"}
    ],
    "max_tokens": 64,
    "temperature": 0.7
  }' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/ChatCompletionStream
```

**预期返回（逐个 chunk 输出）：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"content": "我"}}]
}
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"content": "是"}}]
}
...
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {}, "finishReason": "stop"}],
  "usage": {"promptTokens": 10, "completionTokens": 20, "totalTokens": 30}
}
```

### 4.6 Chat Completions（流式，推理模型 — reasoning_content 增量）

> 推理模型流式输出时，先输出 `reasoningContent` 增量（思考过程），
> 思考结束后输出 `content` 增量（最终回答），最后一个 chunk 携带 `finishReason` 和 `usage`。

```bash
grpcurl -plaintext \
  -import-path libs/proto \
  -proto llm_infer.proto \
  -d '{
    "request_id": "test-stream-reasoning-001",
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？"}
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "enable_thinking": true
  }' \
  127.0.0.1:19090 deeppool.llm.v1.LLMInferService/ChatCompletionStream
```

**预期返回（先输出 reasoning，再输出 content）：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"reasoningContent": "用户问的是"}}]
}
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"reasoningContent": "基础加法..."}}]
}
...
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"content": "1+1"}}]
}
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {"content": "等于2。"}}]
}
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion.chunk",
  "choices": [{"index": 0, "delta": {}, "finishReason": "stop"}],
  "usage": {
    "promptTokens": 10,
    "completionTokens": 40,
    "totalTokens": 50,
    "completionTokensDetails": {"reasoningTokens": 25}
  }
}
```

### 4.7 列出服务和方法（需 proto 文件）

```bash
grpcurl -import-path libs/proto -proto llm_infer.proto list
grpcurl -import-path libs/proto -proto llm_infer.proto describe deeppool.llm.v1.LLMInferService
```

---

## 五、模型下载说明

模型通过 `huggingface_hub` 自动下载到 `~/.deeppool/models/<model_name>/` 目录。

### 手动提前下载

```bash
pip install huggingface_hub

# 下载当前默认模型
huggingface-cli download Qwen/Qwen3-0.6B-8bit \
  --local-dir ~/.deeppool/models/Qwen3-0.6B-8bit
```

> 如模型已存在于本地目录，初始化时会跳过下载步骤。

---

## 六、NodeManager OpenAI 兼容推理接口测试

> **前提条件：**
> 1. Platform manager 已启动（`:8080`）
> 2. NodeManager 已启动（HTTP `:8082`，gRPC `:9092`）
> 3. Localserver 已启动并完成设备初始化，推理服务就绪
> 4. Localserver 已自动与 NodeManager 建立双向流长连接（启动日志中可见 `tunnel registered`）
>
> **架构说明：**
> NodeManager 对外提供 OpenAI 兼容 HTTP 接口 `/v1/chat/completions`，
> 请求到达后通过内部事件总线路由到在线设备（按 model 匹配），
> 设备通过 gRPC 双向流隧道回传推理结果，NodeManager 再以 OpenAI JSON 格式返回给调用方。
>
> 这套机制使得外部用户无需知道具体设备地址，仅通过 NodeManager 统一入口即可调用算力提供方的推理服务。

### 6.1 NodeManager 健康检查

```bash
curl -s http://127.0.0.1:8082/health | python3 -m json.tool
```

**预期返回：**

```json
{
  "status": "ok",
  "service": "nodemanager",
  "region": "default",
  "online_devices": 1
}
```

> `online_devices` 表示当前通过隧道在线的设备数量，至少为 1 才能处理推理请求。

### 6.2 Chat Completions（非流式，基础）

```bash
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "system", "content": "你是一个有趣的故事讲述者。"},
      {"role": "user", "content": "你好，讲一个简短的故事"}
    ],
    "max_tokens": 128,
    "temperature": 0.7,
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1742486400,
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "从前有一只小猫..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 18,
    "completion_tokens": 50,
    "total_tokens": 68
  }
}
```

### 6.3 Chat Completions（非流式，推理模型 — reasoning_content）

> 适用于 Qwen3 等推理模型，通过 `enable_thinking` 控制是否输出思考过程。

```bash
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？请解释你的推理过程"}
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "enable_thinking": true,
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1742486400,
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "1+1等于2。",
        "reasoning_content": "用户问的是基础加法，1+1=2..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 15,
    "completion_tokens": 80,
    "total_tokens": 95
  }
}
```

### 6.4 Chat Completions（非流式，多轮对话携带 reasoning_content 历史）

```bash
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？"},
      {
        "role": "assistant",
        "content": "1+1等于2。",
        "reasoning_content": "这是基础加法运算，1+1=2。"
      },
      {"role": "user", "content": "那再加3呢？"}
    ],
    "max_tokens": 128,
    "temperature": 0.7,
    "enable_thinking": true,
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1742486400,
  "model": "Qwen3-0.6B-8bit",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "2+3等于5。",
        "reasoning_content": "上一步得到1+1=2，现在加3，即2+3=5。"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 40,
    "completion_tokens": 60,
    "total_tokens": 100
  }
}
```

### 6.5 Chat Completions（流式 SSE，基础）

```bash
curl -N http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "用一句话介绍自己"}
    ],
    "max_tokens": 64,
    "temperature": 0.7,
    "stream": true
  }'
```

> `-N` 禁用 curl 缓冲，实时显示 SSE 事件。

**预期返回（逐行 SSE 事件）：**

```
data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"我"}}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"是"}}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"一个"}}]}

...

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}

data: [DONE]
```

### 6.6 Chat Completions（流式 SSE，推理模型 — reasoning_content 增量）

> 流式模式下，先输出 `reasoning_content` 增量（思考过程），
> 思考结束后输出 `content` 增量（最终回答），最后一个 chunk 携带 `finish_reason` 和 `usage`。

```bash
curl -N http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [
      {"role": "user", "content": "1+1等于几？"}
    ],
    "max_tokens": 256,
    "temperature": 0.7,
    "enable_thinking": true,
    "stream": true
  }'
```

**预期返回（先输出 reasoning，再输出 content）：**

```
data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"reasoning_content":"用户问的是"}}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"reasoning_content":"基础加法..."}}]}

...

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"1+1"}}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"等于2。"}}]}

data: {"id":"chatcmpl-xxxx","object":"chat.completion.chunk","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":40,"total_tokens":50}}

data: [DONE]
```

### 6.7 错误场景测试

#### 无在线设备时请求

```bash
# 不启动 localserver，直接请求 nodemanager
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "messages": [{"role": "user", "content": "hello"}],
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "error": {
    "message": "no online device available for model Qwen3-0.6B-8bit",
    "type": "server_error"
  }
}
```

#### 缺少必要参数

```bash
# 缺少 model 字段
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "messages": [{"role": "user", "content": "hello"}],
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "error": {
    "message": "model is required",
    "type": "invalid_request_error"
  }
}
```

```bash
# 缺少 messages 字段
curl -s http://127.0.0.1:8082/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen3-0.6B-8bit",
    "stream": false
  }' | python3 -m json.tool
```

**预期返回：**

```json
{
  "error": {
    "message": "messages is required",
    "type": "invalid_request_error"
  }
}
```

---

## 七、涉及文件清单

### Platform Manager（Go）

| 文件 | 说明 |
|------|------|
| `platform/internal/manager/handler/user_handler.go` | HTTP 路由，`POST /api/v1/models/deploy-config` |
| `platform/internal/manager/service/user_service.go` | 业务层，`GetModelDeployConfig` 返回 repo_id 等 |
| `platform/internal/manager/types/types.go` | DTO，`ModelDeployConfigDTO` 含 RepoID/ModelBaseDir |

### Platform NodeManager（Go）

| 文件 | 说明 |
|------|------|
| `platform/cmd/nodemanager/main.go` | NodeManager 启动入口 |
| `platform/internal/nodemanager/server.go` | HTTP + gRPC 双端口服务器 |
| `platform/internal/nodemanager/connection_hub.go` | 256 分片连接表，心跳巡检，按 model 路由 |
| `platform/internal/nodemanager/tunnel_handler.go` | gRPC 双向流处理：注册鉴权→事件循环 |
| `platform/internal/nodemanager/dispatch_service.go` | 推理任务分发：选设备→下发→等结果 |
| `platform/internal/nodemanager/openai_handler.go` | `/v1/chat/completions` OpenAI 兼容接口 |
| `platform/internal/nodemanager/auth.go` | 隧道连接鉴权（复用 session 表） |
| `platform/config/nodemanager.yaml` | NodeManager 配置（HTTP/gRPC 端口、数据库） |

### Proto

| 文件 | 说明 |
|------|------|
| `libs/proto/llm_infer.proto` | gRPC 推理协议定义 |
| `libs/proto/manager_service.proto` | Platform manager gRPC 协议（含 ModelDeployConfig） |
| `libs/proto/node_tunnel.proto` | 设备隧道双向流协议（注册/心跳/任务/结果） |

### LLM Service（Python）

| 文件 | 说明 |
|------|------|
| `llm_service/engine_base.py` | 推理引擎抽象基类 |
| `llm_service/engine_llamacpp.py` | llama.cpp 引擎（macOS Metal） |
| `llm_service/engine_vllm.py` | vLLM 引擎（Linux CUDA） |
| `llm_service/engine_vllm_mlx.py` | vLLM-MLX 引擎（macOS Apple Silicon） |
| `llm_service/model_registry.py` | 模型路径解析工具（无硬编码模型列表） |
| `llm_service/model_downloader.py` | 模型下载（huggingface_hub） |
| `llm_service/rpc_server.py` | gRPC 推理服务 |
| `llm_service/platform_client.py` | Platform gRPC 调用封装 |
| `llm_service/service_manager.py` | 服务管理（引擎选择+下载+加载+gRPC） |

### LocalServer 路由

| 文件 | 说明 |
|------|------|
| `clients/deepnode/localserver/main.py` | 入口，启动推理服务后自动连接 nodemanager 隧道 |
| `clients/deepnode/localserver/api/init.py` | `POST /api/init/device` 设备初始化编排 |
| `clients/deepnode/localserver/rpc/node_manager_client.py` | NodeManager 双向流长连接客户端（心跳/重连/任务执行） |
| `clients/deepnode/localserver/rpc/platform_client.py` | Platform manager gRPC 调用封装 |
| `clients/deepnode/localserver/requirements.txt` | Python 依赖清单 |

### 前端

| 文件 | 说明 |
|------|------|
| `clients/deepnode/app/src/views/DeviceInitView.vue` | 设备初始化页面 |

---

## 八、常见问题排查

| 问题 | 排查方向 |
|------|---------|
| init 返回 `Failed to fetch model deploy config` | manager 未启动 / token 无效 / 网络不通 |
| HuggingFace 下载失败 | 网络受限，配置 `HF_ENDPOINT` 镜像或手动下载 |
| `vllm_mlx` 导入失败 | 确认 `pip install vllm-mlx` 已在 env 中安装 |
| `llama-cpp-python` 编译失败 | 确保 Xcode CLI tools 已安装：`xcode-select --install` |
| 模型加载 OOM | 换更小的模型或量化版本 |
| gRPC 端口冲突 | 检查 19090 是否被占用：`lsof -i :19090` |
| `grpcurl` 报 reflection 错误 | 使用 `-proto` 参数指定 proto 文件（见第四节示例） |
| NodeManager 返回 `no online device available` | localserver 未启动或未成功注册隧道，检查 localserver 日志 |
| 隧道连接建立失败 | 检查 nodemanager gRPC 端口 9092 是否可达：`nc -z 127.0.0.1 9092` |
| 隧道连接频繁断开重连 | 检查网络质量；nodemanager 日志中 `heartbeat evict` 表示心跳超时 |
| NodeManager OpenAI 接口超时 | 检查在线设备是否繁忙；可通过 `/health` 查看 `online_devices` 数量 |
