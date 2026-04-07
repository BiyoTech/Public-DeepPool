# OpenAI-Compatible API

DeepPool Gateway provides a fully OpenAI-compatible inference interface, supporting three model types: DeepNode (edge inference), Provider (cloud proxy), and Hybrid (smart hybrid dispatch).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/chat/completions` | Chat Completions (streaming/non-streaming) |
| `GET` | `/v1/models` | List all available models |

## Authentication

All requests require an API Key in the header:

```
Authorization: Bearer dp-xxxxxxxxxxxxxxxx
Content-Type: application/json
```

## Chat Completions

### Request Body

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

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name (use `/v1/models` to get available list) |
| `messages` | array | Yes | Conversation message list, supports `system` / `user` / `assistant` / `tool` roles |
| `stream` | boolean | No | Enable streaming output (SSE), default `false` |
| `temperature` | number | No | Sampling temperature 0~2, default 1.0 |
| `top_p` | number | No | Nucleus sampling probability, default 1.0 |
| `n` | integer | No | Number of completions to generate, default 1 |
| `max_tokens` | integer | No | Maximum tokens to generate, default 4096 |
| `stop` | array | No | Stop sequence list |
| `presence_penalty` | number | No | Presence penalty -2.0~2.0 |
| `frequency_penalty` | number | No | Frequency penalty -2.0~2.0 |
| `tools` | array | No | Function Calling tool definition list |
| `tool_choice` | string/object | No | Tool selection strategy: `"none"` / `"auto"` / `"required"` / specific function name |
| `enable_thinking` | boolean | No | Enable reasoning mode (returns `reasoning_content`), only supported by select models |
| `seed` | integer | No | Random seed (for reproducible output) |

### Non-Streaming Response

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

### Streaming Response (SSE)

```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{...}}

data: [DONE]
```

### Function Calling Response

When the model returns tool calls, `finish_reason` is `"tool_calls"`:

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

## List Available Models

```
GET /v1/models
Authorization: Bearer dp-xxxxxxxxxxxxxxxx
```

Response:

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

## Response Headers

Each inference request includes the following custom headers indicating the actual routing path:

| Header | Description |
|--------|-------------|
| `X-DeepPool-Backend` | Backend type: `deepnode` / `provider` / `hybrid` |
| `X-DeepPool-Model-Name` | Requested model name |
| `X-DeepPool-Provider-Type` | Provider type (provider models only) |
| `X-DeepPool-Route-Target` | Actual route target address |

## Error Responses

```json
{
  "error": {
    "message": "model not found",
    "type": "invalid_request_error"
  }
}
```

| HTTP Status | Meaning |
|-------------|---------|
| 401 | Invalid or missing API Key |
| 404 | Model not found |
| 429 | RPM/TPM rate limit exceeded or token quota exhausted |
| 502 | Upstream node/Provider unavailable |
| 503 | No available backend (all Hybrid candidates failed) |
