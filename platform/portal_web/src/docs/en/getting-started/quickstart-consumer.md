# Consumer Quickstart

This guide will help you quickly integrate with the DeepPool inference API.

## Prerequisites

- DeepPool platform account
- Any programming language or tool that supports HTTP requests

## Steps

### 1. Create an API Key

Log in to the portal website, go to the "Service" page, and click "Create API Key" in the right panel. Copy and save the full key immediately — it's only shown once at creation.

### 2. List Available Models

```bash
curl https://your-deeppool-host/v1/models \
  -H "Authorization: Bearer your-api-key"
```

Each model in the response includes a `vendor_type` field (`deepnode` / `provider` / `hybrid`) indicating the model source type.

### 3. Call the Inference API

DeepPool is fully compatible with the OpenAI Chat Completions API — use the OpenAI SDK directly:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://your-deeppool-host/v1",
    api_key="your-api-key",
)

# Non-streaming
response = client.chat.completions.create(
    model="Qwen3-0.6B-8bit",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

# Streaming
stream = client.chat.completions.create(
    model="Qwen3-0.6B-8bit",
    messages=[{"role": "user", "content": "Write a poem about distributed computing"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

### 4. Using Hybrid Models

Hybrid models auto-route between multiple child models with intelligent scheduling and failover — recommended for production:

```python
response = client.chat.completions.create(
    model="deeppool_hybrid_model_v1",   # Hybrid model name
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    stream=True,
)
```

The response header `X-DeepPool-Backend` indicates the actual backend type used (`deepnode` / `provider` / `hybrid`).

### 5. Function Calling

```python
response = client.chat.completions.create(
    model="Qwen3-0.6B-8bit",
    messages=[{"role": "user", "content": "What's the weather in Beijing?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }],
    tool_choice="auto",
)
```

## Billing

The platform is currently in free trial. In the future, billing will be token-based. Each API Key supports independent RPM (requests per minute) and TPM (tokens per minute) rate limits.
