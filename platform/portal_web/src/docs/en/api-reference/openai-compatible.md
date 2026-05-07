# OpenAI-Compatible API

DeepPool Gateway exposes a **standard OpenAI-compatible** inference API. Regardless of whether the underlying model runs on DeepNode (edge inference), Provider (cloud proxy), or Hybrid (smart dispatch), callers only need to use the standard OpenAI SDK — **no need to worry about model-specific differences**.

> **💡 Multi-Model Adaptation**: DeepPool Gateway automatically adapts parameters across all supported model families (including Qwen, DeepSeek, GLM, Kimi, Gemma, Anthropic, etc.), converting standard OpenAI parameters into each model's native format. Callers use a single standard interface to drive models from different vendors.

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
  "max_tokens": 2048,
  "reasoning_effort": "medium"
}
```

#### Vision Request (Image Understanding)

For vision-capable models, the `content` field in `messages` supports a **multipart array** format, allowing you to send images alongside text. This follows the [OpenAI Vision API](https://platform.openai.com/docs/guides/vision) specification.

```json
{
  "model": "deeppool-hybrid-v1",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "text", "text": "What's in this image?"},
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

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | Yes | Model name (use `/v1/models` to get available list) |
| `messages` | array | Yes | Conversation message list, supports `system` / `user` / `assistant` / `tool` roles. The `content` field can be a string or a multipart array (for vision requests, see below) |
| `stream` | boolean | No | Enable streaming output (SSE), default `false` |
| `temperature` | number | No | Sampling temperature 0~2, default 1.0 |
| `top_p` | number | No | Nucleus sampling probability, default 1.0 |
| `n` | integer | No | Number of completions to generate, default 1 |
| `max_tokens` | integer | No | Maximum tokens to generate, default 4096 |
| `stop` | string or array | No | Stop sequences, see details below |
| `presence_penalty` | number | No | Presence penalty -2.0~2.0 |
| `frequency_penalty` | number | No | Frequency penalty -2.0~2.0 |
| `tools` | array | No | Function Calling tool definition list |
| `tool_choice` | string/object | No | Tool selection strategy: `"none"` / `"auto"` / `"required"` / specific function name |
| `reasoning_effort` | string | No | Reasoning intensity control, see details below |
| `enable_thinking` | boolean | No | Enable reasoning mode (legacy compat), recommend using `reasoning_effort` instead |
| `seed` | integer | No | Random seed (for reproducible output) |

#### Vision Message Content Format

When sending images, the `content` field of a `user` message should be an array of content parts:

| Part Type | Fields | Description |
|-----------|--------|-------------|
| `text` | `type: "text"`, `text: string` | Text content |
| `image_url` | `type: "image_url"`, `image_url: { url, detail? }` | Image content |

The `image_url.url` field supports:
- **Base64 data URL**: `data:image/<format>;base64,<data>` (recommended for direct uploads)
- **HTTP(S) URL**: `https://example.com/image.png` (if the model supports URL fetching)

The `image_url.detail` field controls image processing fidelity:
- `"auto"` (default) — model decides the optimal resolution
- `"low"` — faster processing, lower resolution
- `"high"` — higher resolution, more tokens consumed

> **💡 Routing Tip**: When using Hybrid models, the Gateway automatically detects vision requests (by checking if the last `user` message contains `image_url` type content) and routes them to vision-capable child models. See [Model Routing](/en/architecture/model-routing) for details.

> **⚠️ Note**: Not all models support vision. Use `/v1/models` to check model capabilities. Sending images to a non-vision model will result in an error.

---

### Reasoning Mode (Thinking)

DeepPool supports controlling model thinking/reasoning behavior via the **`reasoning_effort`** parameter. This is a standard OpenAI parameter — the Gateway automatically converts it into each model's native format.

#### `reasoning_effort` Parameter

| Value | Meaning |
|-------|---------|
| `"none"` | Disable reasoning mode, model does not perform deep thinking |
| `"low"` | Light reasoning, suitable for simple reasoning tasks |
| `"medium"` | Moderate reasoning depth (recommended default) |
| `"high"` | Deep reasoning, suitable for complex problems |

**When not provided**, the model uses its own default behavior.

#### Multi-Model Adaptation Under the Hood

Callers only need to pass the standard `reasoning_effort` — the Gateway automatically converts it to each model's native format:

| Model Family | Native Format | Gateway Auto-Handles |
|-------------|--------------|---------------------|
| OpenAI / Gemini | `reasoning_effort` passthrough | ✅ |
| DeepSeek / Kimi / GLM | `thinking: {"type": "enabled"}` | ✅ Auto-converted |
| Qwen / ERNIE / MiniMax | `enable_thinking: true` | ✅ Auto-converted |
| Anthropic (Claude) | `thinking: {"type": "enabled", "budget_tokens": N}` | ✅ Auto-converted with budget mapping |

> **Backward Compatibility**: The legacy `enable_thinking: true/false` parameter still works. When both are present, `reasoning_effort` takes priority.

#### Reasoning Mode Response

When reasoning is enabled, the model returns its thinking process:

- **Non-streaming**: `message.reasoning_content` field
- **Streaming**: `delta.reasoning_content` incremental field

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

### Stop Sequences

The `stop` parameter specifies strings that cause the model to immediately stop generating when encountered.

```json
{
  "stop": ["\n\n", "END"]
}
```

- Accepts a **string** (single stop sequence) or **array** (up to 8)
- The Gateway automatically **merges and deduplicates** request-level stop sequences with model default stop sequences — no need to manually add model built-in stop tokens
- For DeepNode models, stop sequences are enforced in both streaming and non-streaming modes

---

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

> **Usage Format**: The `usage` field in responses is fully OpenAI-compatible, including nested `prompt_tokens_details` and `completion_tokens_details` structures. When the upstream model does not return certain fields, their values default to 0.

### Streaming Response (SSE)

```
data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"reasoning_content":"Let me think..."},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-xxx","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{...}}

data: [DONE]
```

> In streaming mode, thinking content is emitted via `delta.reasoning_content` before the actual response `delta.content`.

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

## Unified Multi-Model Adaptation

The core design principle of DeepPool Gateway is to **expose a standard OpenAI-compatible interface to callers, while adapting to each model vendor's native parameter format under the hood**.

The following parameters are automatically adapted by the Gateway — callers need not be aware of underlying differences:

| Standard Parameter | Adaptation Scope | Description |
|-------------------|-----------------|-------------|
| `reasoning_effort` | Qwen, DeepSeek, GLM, Kimi, Gemini, Anthropic, MiniMax, etc. | Auto-converted to `thinking`, `enable_thinking`, etc. |
| `stop` | All DeepNode models | Auto-merged with model built-in stop sequences |
| `tools` / `tool_choice` | All FC-capable models | Unified OpenAI Function Calling format |
| `model` | All Provider models | Auto-replaced with upstream model name; restored in response |
| Vision `content` array | All vision-capable models | Auto-detected and routed to vision-capable backends in Hybrid mode |

This means you can use the exact same code to call Qwen, DeepSeek, GPT-4o, Claude, and other vendor models — no per-model parameter adaptation required.
