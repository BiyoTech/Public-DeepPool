# OpenAI 兼容 API

DeepPool Gateway 提供完全兼容 OpenAI 的推理接口，支持 DeepNode（边缘推理）、Provider（云端代理）和 Hybrid（智能混合调度）三种模型类型。

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
  "max_tokens": 2048
}
```

### 参数说明

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | string | 是 | 模型名称（通过 `/v1/models` 获取可用列表） |
| `messages` | array | 是 | 对话消息列表，支持 `system` / `user` / `assistant` / `tool` 角色 |
| `stream` | boolean | 否 | 是否流式输出（SSE），默认 `false` |
| `temperature` | number | 否 | 采样温度 0~2，默认 1.0 |
| `top_p` | number | 否 | 核采样概率，默认 1.0 |
| `n` | integer | 否 | 生成候选数量，默认 1 |
| `max_tokens` | integer | 否 | 最大生成 token 数，默认 4096 |
| `stop` | array | 否 | 停止序列列表 |
| `presence_penalty` | number | 否 | 存在惩罚 -2.0~2.0 |
| `frequency_penalty` | number | 否 | 频率惩罚 -2.0~2.0 |
| `tools` | array | 否 | Function Calling 工具定义列表 |
| `tool_choice` | string/object | 否 | 工具选择策略：`"none"` / `"auto"` / `"required"` / 具体函数名 |
| `enable_thinking` | boolean | 否 | 启用推理模式（返回 `reasoning_content`），仅部分模型支持 |
| `seed` | integer | 否 | 随机种子（用于可复现输出） |

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
      "reasoning_content": "...(if enable_thinking=true)"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 8,
    "total_tokens": 20
  }
}
```

### 流式响应（SSE）

```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{...}}

data: [DONE]
```

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
