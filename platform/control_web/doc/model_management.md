# Model Management Guide

## Overview

DeepPool supports three model vendor types:

| Type | Description | Use Case |
|------|-------------|----------|
| **DeepNode** | Runs on contributor devices via gRPC tunnel | Private/edge deployment, contributor earns revenue |
| **Provider** | Proxied to third-party API (OpenAI, etc.) | Quick access to cloud models |
| **Hybrid** | Virtual model that routes to DeepNode/Provider children | Intelligent routing, fallback, cost optimization |

---

## 1. Hybrid Model — Routing Policy

### 1.1 How It Works

A Hybrid model is a **virtual entry point** — it does not serve inference itself. When a user request arrives:

1. **Feature extraction**: Parse the request to compute routing features (input token count, tool count, reasoning flag).
2. **Rule matching**: Evaluate routing rules top-down (first match wins).
3. **Target selection**: Pick a candidate from the matched rule's targets via round-robin.
4. **Fallback**: If the selected child fails (before any response bytes), try the next candidate in the list.
5. **Final fallback**: Child models not listed in the matched rule are appended as last-resort fallbacks.

### 1.2 Routing Policy YAML Schema

```yaml
# Load balancing strategy for multi-target rules (currently only round-robin)
load_balance: round-robin

# Rules are evaluated top-down; first matching rule wins
rules:
  - name: "rule_name"           # Human-readable rule name
    condition:                   # All specified fields must match (AND logic)
      max_input_tokens: 2000    # Input token count <= this value
      min_input_tokens: 100     # Input token count >= this value
      has_tools: true           # Request contains tool definitions
      has_reasoning: false      # Request has enable_thinking=true
      max_tool_count: 5         # Number of tools <= this value
      min_tool_count: 1         # Number of tools >= this value
    targets:                    # Candidate models for this rule (must be child models)
      - "model-a"
      - "model-b"

# Fallback targets when no rule matches (if omitted, all child models are used)
default_targets:
  - "model-a"
  - "model-b"
```

### 1.3 Condition Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `max_input_tokens` | int | Match if estimated input tokens ≤ value |
| `min_input_tokens` | int | Match if estimated input tokens ≥ value |
| `has_tools` | bool | Match if request contains tool definitions |
| `has_reasoning` | bool | Match if `enable_thinking` is true |
| `max_tool_count` | int | Match if tool count ≤ value |
| `min_tool_count` | int | Match if tool count ≥ value |

> **Note**: Token estimation uses a `len(content) / 4` heuristic (~4 chars per token). All specified conditions must be satisfied simultaneously (AND logic). Omitted fields are not checked.

### 1.4 Configuration Examples

#### Example 1: Route by request complexity

Short requests go to a lightweight local model; long/complex requests go to a powerful provider.

```yaml
load_balance: round-robin

rules:
  - name: "short_simple_requests"
    condition:
      max_input_tokens: 2000
      has_tools: false
    targets:
      - "qwen3-0.6b-local"

  - name: "tool_calling"
    condition:
      has_tools: true
    targets:
      - "gpt-4o-proxy"

  - name: "long_context"
    condition:
      min_input_tokens: 2001
    targets:
      - "gpt-4o-proxy"

default_targets:
  - "qwen3-0.6b-local"
  - "gpt-4o-proxy"
```

#### Example 2: Reasoning vs non-reasoning split

```yaml
load_balance: round-robin

rules:
  - name: "reasoning_tasks"
    condition:
      has_reasoning: true
    targets:
      - "deepseek-r1-local"
      - "qwq-32b-proxy"

default_targets:
  - "qwen3-0.6b-local"
  - "gpt-4o-mini-proxy"
```

#### Example 3: Leave empty for simple round-robin

If no routing policy YAML is configured, all child models are load-balanced via round-robin with automatic fallback.

### 1.5 Fallback Mechanism

When a candidate fails **before writing any response bytes** to the client, the system automatically tries the next candidate. The full candidate order is:

1. Models from the matched rule's `targets` (round-robin rotated)
2. All remaining child models not in the matched targets

> **Important**: Once response streaming has started (bytes written), fallback is not possible. The error is returned to the client.

---

## 2. Billing Strategy

### 2.1 Billing Roles

| Role | Description | Applies To |
|------|-------------|------------|
| **Consumer (pricing_tiers)** | The user who sends the request pays | All model types |
| **Contributor (contributor_tiers)** | The device owner who provides compute earns | DeepNode models only |

### 2.2 Configuration Rules by Model Type

| Model Type | Consumer Billing (pricing_tiers) | Contributor Billing (contributor_tiers) |
|------------|----------------------------------|----------------------------------------|
| **DeepNode** | ✅ Configure here | ✅ Configure here |
| **Provider** | ✅ Configure here | ❌ Not applicable (no contributor) |
| **Hybrid** | ✅ Configure here (charges the user) | ❌ Derived from the resolved child model |

### 2.3 How Hybrid Billing Works

When a Hybrid model processes a request:

1. **Consumer cost**: Calculated using the **Hybrid model's own `pricing_tiers`**
2. **Contributor earning**: Calculated using the **resolved child model's `contributor_tiers`**
   - If the child is a DeepNode → uses that DeepNode's contributor tiers
   - If the child is a Provider → contributor earning is 0 (no device contributor)

```
User Request → hybrid-model (pricing_tiers: charges user ¥X)
                  │
                  ├─ routes to deepnode-child → contributor_tiers: pays device owner ¥Y
                  │
                  └─ routes to provider-child → contributor earning: ¥0
```

> **Why this design**: The Hybrid model is a virtual routing layer — it doesn't know which child will be selected until runtime. Consumer pricing is fixed at the Hybrid level for predictable user billing. Contributor earning varies based on the actual execution backend.

### 2.4 Tiered Pricing Configuration

Pricing uses tiered matching based on input token count:

```
pricing_tiers:
  ┌──────────────────┬─────────────┬──────────────┐
  │ max_input_tokens │ input_price │ output_price  │
  │ (0 = unlimited)  │ (¥/M tokens)│ (¥/M tokens) │
  ├──────────────────┼─────────────┼──────────────┤
  │ 4096             │ 1.00        │ 2.00         │
  │ 32768            │ 2.00        │ 4.00         │
  │ 0 (catch-all)    │ 4.00        │ 8.00         │
  └──────────────────┴─────────────┴──────────────┘
```

**Matching logic**:
1. Iterate tiers in order
2. Pick the **first** tier where `prompt_tokens <= max_input_tokens`
3. `max_input_tokens = 0` means unlimited (catch-all tier, should be last)
4. If no tier matches, fall back to the last tier

**Cost formula**:
```
cost_yuan = prompt_tokens × input_price / 1,000,000
          + completion_tokens × output_price / 1,000,000
```

> **Precision**: All amounts are stored as `DECIMAL(20,10)` in the database (yuan), preserving up to 10 decimal places. No rounding is applied — even very small requests are accurately billed.

### 2.5 Configuration Examples

#### Example: DeepNode model with contributor tiers

```
pricing_tiers (consumer):
  ≤4K tokens:  input ¥1.00/M, output ¥2.00/M
  unlimited:   input ¥2.00/M, output ¥4.00/M

contributor_tiers (device owner):
  ≤4K tokens:  input ¥0.50/M, output ¥1.00/M
  unlimited:   input ¥1.00/M, output ¥2.00/M
```

#### Example: Hybrid model billing

```
hybrid-model pricing_tiers (consumer):
  unlimited:  input ¥2.00/M, output ¥4.00/M

→ If routed to deepnode-child:
    contributor_tiers from deepnode-child:
      unlimited: input ¥0.80/M, output ¥1.60/M

→ If routed to provider-child:
    contributor earning = ¥0
```

#### Example: Free model

Leave `pricing_tiers` empty → model is free for consumers.

---

## 3. Quick Reference

### Model Creation Checklist

| Step | DeepNode | Provider | Hybrid |
|------|----------|----------|--------|
| model_name | ✅ Required | ✅ Required | ✅ Required |
| repo_id | ✅ Required | — | — |
| endpoint + api_key | — | ✅ Required | — |
| child_models (≥2) | — | — | ✅ Required |
| routing_policy | — | — | Optional (YAML) |
| pricing_tiers | Optional | Optional | Optional |
| contributor_tiers | Optional | — | — (derived from child) |

### Common Mistakes

1. **Setting contributor_tiers on Hybrid** → Will be ignored; contributor billing comes from the resolved child model.
2. **Routing policy targets not in child_models** → Validation error; all targets must reference existing child models.
3. **Only 1 child model** → Validation error; Hybrid requires at least 2 children.
4. **Recursive Hybrid** → Not allowed; a Hybrid's child cannot be another Hybrid.
