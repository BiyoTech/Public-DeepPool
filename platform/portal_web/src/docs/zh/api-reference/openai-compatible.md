# OpenAI 兼容 API

DeepPool Gateway 对外提供**标准 OpenAI 规范**的推理接口。无论底层模型来自 DeepNode（边缘推理）、Provider（云端代理）还是 Hybrid（智能混合调度），调用方只需使用统一的 OpenAI SDK 即可接入，**无需关心底层模型差异**。

> **💡 多模型适配**：DeepPool Gateway 在底层对各模型的参数格式做了全面适配（包括 Qwen、DeepSeek、GLM、Kimi、Gemma、Anthropic 等），将标准 OpenAI 参数自动转换为各模型的原生格式。调用方只需使用标准 OpenAI 接口，即可驱动不同厂商的模型。

## 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/chat/completions` | Chat Completions（流式/非流式） |
| `GET` | `/v1/models` | 列出所有可用模型 |

## 认证

所有请求需在 Header 中携带 API Key：

```
Authorization: Bearer dp-xxxxxxxxxxxxxxxx
Content-Type: application/json
```

## Chat Completions

### 请求体

```json
{
  "model": "Qwen3-0.6B-8bit",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 2048,
  "reasoning_effort": "medium"
}
```

#### 视觉理解请求（Vision）

对于支持视觉理解的模型，`messages` 中的 `content` 字段支持**多部分数组**格式，可以同时发送图片和文本。该格式遵循 [OpenAI Vision API](https://platform.openai.com/docs/guides/vision) 规范。

```json
{
  "model": "deeppool-hybrid-v1",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "这张图片里有什么？"},
        {
          "type": "image_url",
          "image_url": {
            "url": "data:image/png;base64,iVBORw0KGgo...",
            "detail": "auto"
          }
        }
      ]
    }
  ],
  "stream": true,
  "max_tokens": 2048
}
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型名称（通过 `/v1/models` 获取可用列表） |
| `messages` | array | 是 | 对话消息列表，支持 `system` / `user` / `assistant` / `tool` 角色。`content` 字段可以是字符串或多部分数组（用于视觉理解请求，详见下方说明） |
| `stream` | boolean | 否 | 是否流式输出（SSE），默认 `false` |
| `temperature` | number | 否 | 采样温度 0~2，默认 1.0 |
| `top_p` | number | 否 | 核采样概率，默认 1.0 |
| `n` | integer | 否 | 生成候选数量，默认 1 |
| `max_tokens` | integer | 否 | 最大生成 token 数，默认 4096 |
| `stop` | string 或 array | 否 | 停止序列，详见下方说明 |
| `presence_penalty` | number | 否 | 存在惩罚 -2.0~2.0 |
| `frequency_penalty` | number | 否 | 频率惩罚 -2.0~2.0 |
| `tools` | array | 否 | Function Calling 工具定义列表 |
| `tool_choice` | string/object | 否 | 工具选择策略：`"none"` / `"auto"` / `"required"` / 具体函数名 |
| `reasoning_effort` | string | 否 | 推理强度控制，详见下方说明 |
| `enable_thinking` | boolean | 否 | 启用推理模式（旧版兼容），推荐使用 `reasoning_effort` 代替 |
| `seed` | integer | 否 | 随机种子（用于可复现输出） |

#### 视觉理解消息 Content 格式

发送图片时，`user` 消息的 `content` 字段应为内容部分的数组：

| 部分类型 | 字段 | 说明 |
|---------|------|------|
| `text` | `type: "text"`, `text: string` | 文本内容 |
| `image_url` | `type: "image_url"`, `image_url: { url, detail? }` | 图片内容 |

`image_url.url` 字段支持：
- **Base64 data URL**：`data:image/<格式>;base64,<数据>`（推荐，适用于直接上传）
- **HTTP(S) URL**：`https://example.com/image.png`（需模型支持 URL 拉取）

`image_url.detail` 字段控制图片处理精度：
- `"auto"`（默认）— 由模型自动决定最优分辨率
- `"low"` — 更快处理，较低分辨率
- `"high"` — 更高分辨率，消耗更多 Token

> **💡 路由提示**：使用 Hybrid 模型时，Gateway 会自动检测视觉理解请求（通过检查最后一条 `user` 消息是否包含 `image_url` 类型内容），并将其路由到支持视觉理解的子模型。详见[模型路由](/zh/architecture/model-routing)。

> **⚠️ 注意**：并非所有模型都支持视觉理解。可通过 `/v1/models` 查看模型能力。向不支持视觉的模型发送图片将返回错误。

---

### 推理模式（Thinking / Reasoning）

DeepPool 支持通过 **`reasoning_effort`** 参数控制模型的思考/推理行为。这是 OpenAI 标准参数，Gateway 会自动将其转换为各模型的原生格式。

#### `reasoning_effort` 参数

| 值 | 含义 |
|----|------|
| `"none"` | 关闭推理模式，模型不进行深度思考 |
| `"low"` | 轻度推理，适合简单推理任务 |
| `"medium"` | 中等推理深度（推荐默认值） |
| `"high"` | 深度推理，适合复杂问题 |

**不传该参数**时，模型使用其自身默认行为。

#### 底层多模型适配

调用方只需传递标准的 `reasoning_effort`，Gateway 会自动转换为各模型的原生格式：

| 模型族 | 原生格式 | Gateway 自动处理 |
|-------|---------|----------------|
| OpenAI / Gemini | `reasoning_effort` 直接透传 | ✅ |
| DeepSeek / Kimi / GLM | `thinking: {"type": "enabled"}` | ✅ 自动转换 |
| Qwen / ERNIE / MiniMax | `enable_thinking: true` | ✅ 自动转换 |
| Anthropic (Claude) | `thinking: {"type": "enabled", "budget_tokens": N}` | ✅ 自动转换并映射 budget |

> **兼容性说明**：旧版 `enable_thinking: true/false` 参数仍然有效。当两者同时存在时，`reasoning_effort` 优先。

#### 启用推理模式的响应

启用推理模式后，模型会在响应中返回思考过程：

- **非流式**：`message.reasoning_content` 字段
- **流式**：`delta.reasoning_content` 增量字段

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "The answer is 42.",
      "reasoning_content": "Let me think step by step..."
    },
    "finish_reason": "stop"
  }]
}
```

---

### 停止序列（Stop Sequences）

`stop` 参数用于指定模型在生成过程中遇到特定字符串时立即停止输出。

```json
{
  "stop": ["\n\n", "END"]
}
```

- 支持传入**字符串**（单个停止序列）或**数组**（最多 8 个）
- Gateway 会将请求级 stop 与模型默认停止序列**自动合并去重**，无需手动添加模型内置的停止符
- 对于 DeepNode 模型，引擎会在非流式和流式两种模式下均生效

---

### 非流式响应

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "Qwen3-0.6B-8bit",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you?",
      "reasoning_content": "...(if reasoning enabled)"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 33,
    "completion_tokens": 196,
    "total_tokens": 229,
    "prompt_tokens_details": {
      "cached_tokens": 0,
      "audio_tokens": 0
    },
    "completion_tokens_details": {
      "reasoning_tokens": 7,
      "audio_tokens": 0,
      "accepted_prediction_tokens": 0,
      "rejected_prediction_tokens": 0
    }
  }
}
```

> **Usage 格式说明**：响应中的 `usage` 字段完整兼容 OpenAI 标准格式，包含 `prompt_tokens_details` 和 `completion_tokens_details` 嵌套结构。当上游模型未返回某些字段时，对应值默认为 0。

### 流式响应（SSE）

```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"reasoning_content":"Let me think..."},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{...}}

data: [DONE]
```

> 流式模式下，思考内容通过 `delta.reasoning_content` 先行输出，然后是正式回复 `delta.content`。

### Function Calling 响应

当模型返回工具调用时，`finish_reason` 为 `"tool_calls"`：

```json
{
  "choices": [{
    "message": {
      "role": "assistant",
      "content": null,
      "tool_calls": [{
        "id": "call_xxx",
        "type": "function",
        "function": {
          "name": "get_weather",
          "arguments": "{\"city\":\"Beijing\"}"
        }
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

## 计费说明

### Token 用量与 Cached Tokens

DeepPool 的计费基于实际 token 消耗，完整兼容 OpenAI 的 Usage 格式。响应中的 `usage.prompt_tokens_details.cached_tokens` 字段标识了被缓存命中的 prompt token 数量。

#### Cached Tokens 计费规则

| Token 类型 | 计费倍率 | 说明 |
|-----------|---------|------|
| 普通 Prompt Tokens | 100% | 未命中缓存的输入 token，按模型标准输入价格计费 |
| Cached Tokens | **20%** | 命中上下文缓存的输入 token，按标准输入价格的 **20%** 计费 |
| Completion Tokens | 100% | 输出 token，按模型标准输出价格计费 |

#### 计费公式

```
输入费用 = (prompt_tokens - cached_tokens) × input_price / 1,000,000
         + cached_tokens × input_price × 0.2 / 1,000,000
输出费用 = completion_tokens × output_price / 1,000,000
总费用   = 输入费用 + 输出费用
```

> **💡 提示**：当模型支持上下文缓存（如长对话中重复的 system prompt），`cached_tokens` 会自动生效，用户无需额外配置。未命中缓存时 `cached_tokens` 为 0，计费退化为标准公式。

---

## 列出可用模型

```
GET /v1/models
Authorization: Bearer dp-xxxxxxxxxxxxxxxx
```

响应：

```json
{
  "object": "list",
  "data": [
    {
      "id": "Qwen3-0.6B-8bit",
      "object": "model",
      "owned_by": "deeppool",
      "vendor_type": "deepnode"
    },
    {
      "id": "gpt-4o",
      "object": "model",
      "owned_by": "openai",
      "vendor_type": "provider",
      "provider_type": "openai"
    },
    {
      "id": "deeppool-hybrid-v1",
      "object": "model",
      "owned_by": "deeppool",
      "vendor_type": "hybrid"
    }
  ]
}
```

## 响应头

每个推理请求的响应中包含以下自定义头，标识实际路由路径：

| Header | 说明 |
|--------|------|
| `X-DeepPool-Backend` | 后端类型：`deepnode` / `provider` / `hybrid` |
| `X-DeepPool-Model-Name` | 请求的模型名称 |
| `X-DeepPool-Provider-Type` | 提供商类型（仅 provider 模型） |
| `X-DeepPool-Route-Target` | 实际路由目标地址 |

## 错误响应

```json
{
  "error": {
    "message": "model not found",
    "type": "invalid_request_error"
  }
}
```

| HTTP 状态码 | 含义 |
|------------|------|
| 401 | API Key 无效或缺失 |
| 404 | 模型不存在 |
| 429 | 超过 RPM/TPM 限流或 Token 配额用尽 |
| 502 | 上游节点/Provider 不可用 |
| 503 | 无可用后端（Hybrid 全部候选失败） |

## 多模型统一适配

DeepPool Gateway 的核心设计理念是**对上层提供标准 OpenAI 规范接口，对下层适配各模型厂商的原生参数格式**。

以下参数会被 Gateway 自动适配，调用方无需了解底层差异：

| 标准参数 | 适配范围 | 说明 |
|---------|---------|------|
| `reasoning_effort` | Qwen, DeepSeek, GLM, Kimi, Gemini, Anthropic, MiniMax 等 | 自动转换为 `thinking`、`enable_thinking` 等原生格式 |
| `stop` | 所有 DeepNode 模型 | 自动与模型内置停止序列合并 |
| `tools` / `tool_choice` | 所有支持 FC 的模型 | 统一 OpenAI Function Calling 格式 |
| `model` | 所有 Provider 模型 | 自动替换为上游模型名，响应中还原回 DeepPool 名称 |
| Vision `content` 数组 | 所有支持视觉的模型 | Hybrid 模式下自动检测并路由到支持视觉理解的后端 |

这意味着你可以用完全相同的代码调用 Qwen、DeepSeek、GPT-4o、Claude 等不同厂商的模型，无需针对每个模型做参数适配。
