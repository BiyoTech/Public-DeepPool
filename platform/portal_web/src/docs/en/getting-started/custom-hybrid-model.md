# Custom Hybrid Models

## Overview

DeepPool allows API consumers to create personal custom Hybrid models. By writing a YAML routing policy, you can combine multiple platform-available models into a single smart-routing endpoint with **conditional routing + automatic failover + load balancing**.

**Key Features:**

- Custom Hybrid models are only visible and callable by their creator
- Child models are selected from publicly available platform models (no other Hybrid models allowed)
- Routing policy is defined via a user-editable YAML configuration file
- Up to 10 custom Hybrid models per user
- Billing is based on the actual child model that handles the request

## Access

After logging in, go to the "Service" page → switch to the "My Models" tab on the right panel.

## Creating a Model

1. Click the "+ Create" button
2. Enter a **model name** (2-32 chars, letters/digits/underscores/hyphens)
3. Select **child models** (at least 2; Hybrid-type models cannot be selected)
4. Write a **routing policy YAML** (optional; leave empty for default least-inflight strategy)
5. Click "Save"

Once created, the model identifier is `u{userID}-{name}`, which can be used directly in API calls.

## Routing Policy YAML — Full Format

```yaml
# ============================================================================
# Load balance strategy (choose one)
#   - least-inflight: prefer the model with fewest in-flight requests (recommended)
#   - round-robin:    evenly distribute in sequence
# ============================================================================
load_balance: "least-inflight"

# Gateway-level max concurrent requests per deepnode-type child model.
# When exceeded, the model is skipped in favor of the next candidate. 0 = system default.
max_inflight_per_deepnode_child: 2

# ============================================================================
# Conditional routing rules (evaluated top-to-bottom; first full match wins)
# ============================================================================
rules:
  - name: "rule_name"        # Rule name (for logging only, any string)
    condition:               # Match conditions (AND logic within a single rule)
      min_input_tokens: 0    # Input tokens ≥ this value
      max_input_tokens: 0    # Input tokens ≤ this value
      has_tools: false       # Whether request includes Function Calling
      has_reasoning: false   # Whether reasoning mode is enabled (enable_thinking=true)
      has_vision: false      # Whether request contains image/visual content
      min_tool_count: 0      # Tools count ≥ this value
      max_tool_count: 0      # Tools count ≤ this value
    targets:                 # Candidate models when this rule matches (preference order)
      - "model-a"
      - "model-b"

# ============================================================================
# Default targets when no rule matches
# Empty [] = use all child_models with load balance strategy
# ============================================================================
default_targets:
  - "model-a"
  - "model-b"
```

## Condition Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `min_input_tokens` | int | Matches when input tokens ≥ value | `min_input_tokens: 128001` → ultra-long context |
| `max_input_tokens` | int | Matches when input tokens ≤ value | `max_input_tokens: 2000` → short text |
| `has_tools` | bool | Whether request includes Function Calling | `has_tools: true` |
| `has_reasoning` | bool | Whether reasoning mode is enabled | `has_reasoning: true` |
| `has_vision` | bool | Whether last user message contains images/video | `has_vision: true` |
| `min_tool_count` | int | Matches when tools count ≥ value | `min_tool_count: 3` → complex agent |
| `max_tool_count` | int | Matches when tools count ≤ value | `max_tool_count: 2` → simple tool use |

**Notes:**
- Multiple condition fields within the same rule use **AND** logic
- Only include the fields you need; omitted fields are not evaluated
- Token count is automatically estimated from the request body (total message chars ÷ 4 + image tokens)

## Matching & Failover Logic

```
Request arrives → Extract features → Match rules top-to-bottom → First full match wins
                                                                       ↓
                                                          rule.targets ordered by load balance
                                                                       ↓
                                                          Append fallback (child models not in targets)
                                                                       ↓
                                                          Try each candidate in order
                                                                       ↓
                                                          Success → return result
                                                          Failure → try next
                                                          All fail → 503
```

**Detailed Flow:**

1. **Feature Extraction**: System extracts InputTokens, HasTools, ToolCount, HasReasoning, HasVision from the request
2. **Rule Matching**: Iterate through `rules` in order; first rule where ALL conditions are satisfied wins
3. **Candidate Ordering**: Winning rule's `targets` are ordered by load balance strategy
4. **Fallback Append**: Child models not listed in targets are appended to the candidate list
5. **Failover**: If preferred model fails, automatically switches to next candidate
6. **No Match**: If no rules match, `default_targets` is used

## Load Balance Strategies

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `least-inflight` | Prefers model with fewest in-flight requests | **Recommended default**, auto-balances load |
| `round-robin` | Distributes requests evenly in sequence | When models have similar capabilities |

## Full Examples

### Example 1: Minimal Config (Default Strategy)

Leave YAML empty or use the following — all child models balanced with least-inflight:

```yaml
load_balance: "least-inflight"
rules: []
default_targets: []
```

### Example 2: Cost-First 5-Model Mix

For scenarios with multiple models at different price points — core principle: **cheapest first, upgrade only when needed**:

```yaml
# ============================================================================
# Cost-first 5-model routing strategy
# ============================================================================
# Model price reference (cheapest to most expensive):
#   1. qwen3.6-plus    — cheapest, 1M ctx, tool-call
#   2. ernie-5.0       — low-mid price, 128K ctx, omni-modal (vision+audio+video)
#   3. kimi-k2.6       — mid price, 256K ctx, vision+video, agent-strong
#   4. gpt-5.4         — expensive, 1M ctx, vision, balanced
#   5. gpt-5.5         — most expensive, 1M ctx, strongest overall
#
# Routing philosophy:
#   - Default to cheapest model
#   - Vision → models with vision capability (sorted by price)
#   - Ultra-long context → 1M-capable models only
#   - Deep reasoning → strongest models
#   - Complex agent → agent-specialized models
# ============================================================================

load_balance: least-inflight
max_inflight_per_deepnode_child: 2

rules:
  # ── Vision/multi-modal requests ──
  - name: "vision_requests"
    condition:
      has_vision: true
    targets:
      - "ernie-5.0"
      - "kimi-k2.6"
      - "gpt-5.4"
      - "gpt-5.5"

  # ── Ultra-long context >256K ──
  - name: "ultra_long_context_gt_256k"
    condition:
      min_input_tokens: 256001
    targets:
      - "qwen3.6-plus"
      - "gpt-5.4"
      - "gpt-5.5"

  # ── Long context 128K-256K ──
  - name: "long_context_128k_to_256k"
    condition:
      min_input_tokens: 128001
      max_input_tokens: 256000
    targets:
      - "qwen3.6-plus"
      - "kimi-k2.6"
      - "gpt-5.4"

  # ── Deep reasoning ──
  - name: "reasoning_tasks"
    condition:
      has_reasoning: true
    targets:
      - "gpt-5.5"
      - "ernie-5.0"
      - "gpt-5.4"
      - "qwen3.6-plus"

  # ── Heavy agent/tool-calling (≥3 tools) ──
  - name: "heavy_tool_calling"
    condition:
      has_tools: true
      min_tool_count: 3
    targets:
      - "kimi-k2.6"
      - "gpt-5.5"
      - "qwen3.6-plus"

  # ── Simple tool-calling (1-2 tools) ──
  - name: "simple_tool_calling"
    condition:
      has_tools: true
      max_tool_count: 2
    targets:
      - "qwen3.6-plus"
      - "ernie-5.0"
      - "kimi-k2.6"

  # ── Short simple (≤2000 tokens, no tools) ──
  - name: "short_simple_requests"
    condition:
      max_input_tokens: 2000
      has_tools: false
    targets:
      - "qwen3.6-plus"
      - "ernie-5.0"

  # ── Medium context general (2K-128K, no tools, no reasoning) ──
  - name: "medium_context_general"
    condition:
      min_input_tokens: 2001
      max_input_tokens: 128000
      has_tools: false
      has_reasoning: false
    targets:
      - "qwen3.6-plus"
      - "ernie-5.0"
      - "kimi-k2.6"

# Default fallback: cost-ascending
default_targets:
  - "qwen3.6-plus"
  - "ernie-5.0"
  - "kimi-k2.6"
  - "gpt-5.4"
  - "gpt-5.5"
```

### Example 3: Reasoning-First 4-Model Setup

```yaml
# ============================================================================
# Reasoning-first strategy — for coding/agent scenarios
# ============================================================================

load_balance: least-inflight
max_inflight_per_deepnode_child: 2

rules:
  # Ultra-long context (>128K)
  - name: "ultra_long_context_gt_128k"
    condition:
      min_input_tokens: 128001
    targets:
      - "deepseek-v4-pro"
      - "qwen3.6-max-preview"
      - "glm-5.1"

  # Deep reasoning
  - name: "reasoning_tasks"
    condition:
      has_reasoning: true
    targets:
      - "deepseek-v4-pro"
      - "glm-5.1"
      - "qwen3.6-max-preview"

  # Heavy agent (≥3 tools)
  - name: "heavy_tool_calling"
    condition:
      has_tools: true
      min_tool_count: 3
    targets:
      - "qwen3.6-max-preview"
      - "deepseek-v4-pro"
      - "deepseek-v3.2"

  # Simple tools
  - name: "simple_tool_calling"
    condition:
      has_tools: true
      max_tool_count: 2
    targets:
      - "deepseek-v3.2"
      - "qwen3.6-max-preview"

  # Short simple
  - name: "short_simple_requests"
    condition:
      max_input_tokens: 2000
      has_tools: false
    targets:
      - "deepseek-v3.2"

  # Medium context general
  - name: "medium_context_general"
    condition:
      min_input_tokens: 2001
      max_input_tokens: 128000
      has_tools: false
      has_reasoning: false
    targets:
      - "deepseek-v3.2"
      - "deepseek-v4-pro"

default_targets:
  - "deepseek-v3.2"
  - "deepseek-v4-pro"
  - "qwen3.6-max-preview"
  - "glm-5.1"
```

### Example 4: Simple 2-Model Config

A minimal strategy with just two child models:

```yaml
load_balance: least-inflight

rules:
  # Long context → cloud
  - name: "long_to_cloud"
    condition:
      min_input_tokens: 4000
    targets: ["cloud-model"]

  # Vision → cloud
  - name: "vision_to_cloud"
    condition:
      has_vision: true
    targets: ["cloud-model"]

# Default: local-first (cheaper)
default_targets:
  - "local-model"
  - "cloud-model"
```

## Strategy Design Tips

### Rule Ordering

Rules are matched top-to-bottom. **Recommended priority order:**

1. **Special capability requirements** (vision, multi-modal) — only some models support these
2. **Context length constraints** (ultra-long → long → medium) — exclude unsupported models
3. **Reasoning mode** — large capability differences between models
4. **Tool-calling complexity** (heavy → simple)
5. **General text requests** (subdivided by length)

### Cost Optimization Tips

- List models in `default_targets` from cheapest to most expensive
- Route short requests (≤2000 tokens) directly to cheapest model
- Only route to expensive models when special capabilities are needed
- Use `max_input_tokens` + `has_tools: false` combination to identify "simple requests"

### targets Notes

- Model names in `targets` **must be one of your selected child models**
- The order in targets affects load balance preference
- Child models not in targets are auto-appended as fallback

## API Usage

After creation, use the model identifier (e.g., `u42-my-hybrid`) in your API calls:

```bash
curl https://your-deeppool-host/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "u42-my-hybrid",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

Your custom models will also appear in the `/v1/models` endpoint response (only visible with your own API Key).

## Important Notes

| Item | Description |
|------|-------------|
| Model name | Cannot be changed after creation; format: `u{uid}-{name}` |
| Child model constraint | Cannot include Hybrid-type models (prevents recursion) |
| targets validation | Must reference selected child models, otherwise save fails |
| Propagation delay | Policy changes take effect within ~10 seconds, no restart needed |
| Billing | Based on the actual child model that handles the request |
| Limit | Up to 10 custom Hybrid models per user |
| Visibility | Only visible and callable by the creator |
