# API 使用者快速开始

本指南将帮助你快速接入 DeepPool 推理 API。

## 前置条件

- DeepPool 平台账号
- 任意支持 HTTP 请求的编程语言或工具

## 步骤

### 1. 创建 API Key

登录门户网站，进入「服务」页面，在右侧面板点击「创建 API Key」。创建成功后请立即复制保存完整密钥，密钥仅在创建时展示一次。

### 2. 查看可用模型

```bash
curl https://your-deeppool-host/v1/models \
  -H "Authorization: Bearer your-api-key"
```

响应中每个模型包含 `vendor_type` 字段（`deepnode` / `provider` / `hybrid`），表示模型来源类型。

### 3. 调用推理 API

DeepPool 完全兼容 OpenAI Chat Completions API，可直接使用 OpenAI SDK：

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

### 4. 使用 Hybrid 模型

Hybrid 模型自动在多个子模型间智能路由和故障转移，推荐用于生产环境：

```python
response = client.chat.completions.create(
    model="deeppool_hybrid_model_v1",   # Hybrid model name
    messages=[{"role": "user", "content": "Explain quantum computing"}],
    stream=True,
)
```

响应头 `X-DeepPool-Backend` 会标识实际使用的后端类型（`deepnode` / `provider` / `hybrid`）。

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
