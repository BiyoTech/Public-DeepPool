const e=`# Model Routing & Hybrid Dispatch

## Model Classification

Every model in DeepPool has a \`vendor_type\` that determines the request routing path:

| VendorType | Routing | Description |
|-----------|---------|-------------|
| **deepnode** | Gateway → gRPC → NodeManager → Device Tunnel | Edge device local inference, low latency |
| **provider** | Gateway → HTTP Proxy → Cloud API | OpenAI, Qianfan and other cloud LLMs |
| **hybrid** | Gateway → Smart Dispatch → DeepNode or Provider | Multi-model combo, condition routing + auto failover |

## Provider Proxy

Provider-type models act as transparent proxies to cloud APIs:

- **Request Rewrite**: \`model\` field replaced with the configured \`upstream_model\`
- **Auth Passthrough**: Uses the model's configured \`api_key\` for upstream authentication
- **Response Rewrite**: Response \`model\` field replaced back to the DeepPool-facing name
- **Streaming Support**: SSE line-by-line relay with real-time flushing

Callers are completely unaware whether the backend is a cloud API or an edge device.

## Hybrid Smart Dispatch

Hybrid is the recommended model type for production environments. Core capabilities:

### Workflow

\`\`\`
Request arrives → Extract features → Match routing policy → Generate candidate list → Try each
                                                                          ↓
                                                               Success → Return result
                                                               Failure → Try next
                                                               All failed → 503
\`\`\`

### Request Feature Extraction

The system extracts the following features from the request body for routing decisions:

| Feature | Calculation |
|---------|------------|
| InputTokens | Total chars of all message contents ÷ 4 |
| ToolCount | Length of tools array |
| HasTools | Whether function calling is included |
| HasReasoning | Whether enable_thinking is true |

### Routing Policy (YAML)

Administrators can configure routing policies for each Hybrid model:

\`\`\`yaml
load_balance: "round-robin"

rules:
  # Route long context requests to cloud LLM
  - name: "long_context"
    condition:
      min_input_tokens: 2000
    targets: ["gpt-4o-provider"]

  # Prefer local for Function Calling
  - name: "tool_call"
    condition:
      has_tools: true
    targets: ["qwen3-deepnode", "gpt-4o-provider"]

  # Route reasoning requests to dedicated model
  - name: "reasoning"
    condition:
      has_reasoning: true
    targets: ["deepseek-r1-provider"]

# Default targets when no rule matches
default_targets: ["qwen3-deepnode"]
\`\`\`

### Matching Logic

1. **Iterate rules in order** — conditions within each rule are AND-combined
2. **First matching rule** takes effect — its targets are round-robin rotated to select the primary
3. **Append Fallback** — child_models not in the targets list are appended to the end
4. **Failover** — if the primary fails, automatically switch to next; 503 only if all fail
5. **Anti-Recursion** — child models cannot also be Hybrid type

### Example

Given a Hybrid model with \`child_models: ["local-qwen", "cloud-gpt4", "cloud-deepseek"]\`:

| Request Features | Matched Rule | Candidate List |
|-----------------|-------------|----------------|
| 100 tokens, no tools | No match → default | \`["local-qwen", "cloud-gpt4", "cloud-deepseek"]\` |
| 3000 tokens | long_context | \`["cloud-gpt4", "local-qwen", "cloud-deepseek"]\` |
| Has tools | tool_call | \`["local-qwen", "cloud-gpt4", "cloud-deepseek"]\` |

## PolicyCache

- Polls database every 10 seconds to sync all Hybrid model routing policies
- Only re-parses YAML when \`updated_at\` changes
- Admin policy changes take effect within ~10 seconds, no restart needed
- Multi-Manager nodes stay consistent via DB polling
`;export{e as default};
