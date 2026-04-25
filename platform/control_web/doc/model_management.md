# 模型管理指南

## 概述

DeepPool 支持三种模型供应商类型：

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| **DeepNode** | 通过 gRPC 隧道运行在贡献者设备上 | 私有/边缘部署，贡献者赚取收益 |
| **Provider** | 代理转发到第三方 API（OpenAI 等） | 快速接入云端模型 |
| **Hybrid** | 虚拟模型，路由到 DeepNode/Provider 子模型 | 智能路由、降级、成本优化 |

---

## 1. Hybrid 模型 — 路由策略

### 1.1 工作原理

Hybrid 模型是一个**虚拟入口** — 自身不执行推理。当用户请求到达时：

1. **特征提取**：解析请求，计算路由特征（输入 token 数、工具数量、推理标志）。
2. **规则匹配**：自上而下评估路由规则（首个匹配的规则生效）。
3. **目标选择**：从匹配规则的 targets 中按负载均衡策略排序候选列表。
4. **降级**：如果选中的子模型失败（在任何响应字节写入客户端之前），自动尝试列表中的下一个候选。
5. **兜底降级**：未出现在匹配规则中的子模型会被追加到候选列表末尾作为最终兜底。

### 1.2 路由策略 YAML 格式

```yaml
# 候选排序的负载均衡策略
# 可选值：round-robin（默认）、least-inflight
load_balance: round-robin

# Gateway 单个 DeepNode 子模型的最大 inflight 上限（超过则跳过，给其它候选让路）
# 0 表示使用代码默认值（2）
max_inflight_per_deepnode_child: 2

# 规则自上而下评估，首个匹配的规则生效
rules:
  - name: "rule_name"           # 规则名称（便于阅读）
    condition:                   # 所有指定字段必须同时满足（AND 逻辑）
      max_input_tokens: 2000    # 输入 token 数 <= 该值
      min_input_tokens: 100     # 输入 token 数 >= 该值
      has_tools: true           # 请求包含工具定义
      has_reasoning: false      # 请求启用了 enable_thinking=true
      has_vision: true          # 最后一条 user 消息包含图片（image_url）
      max_tool_count: 5         # 工具数量 <= 该值
      min_tool_count: 1         # 工具数量 >= 该值
    targets:                    # 该规则的候选模型（必须是子模型）
      - "model-a"
      - "model-b"

# 无规则匹配时的默认目标（如省略则使用全部子模型）
default_targets:
  - "model-a"
  - "model-b"
```

> **说明**：路由策略文件只负责"**怎么选子模型**"。"**每个子模型执行时的流式健康度兜底**"（首 token 超时 / chunk 间 idle 超时）不在这里配置，详见下文 [3. 流式超时配置](#3-流式超时配置)。

### 1.3 条件字段参考

| 字段 | 类型 | 说明 |
|------|------|------|
| `max_input_tokens` | int | 预估输入 token 数 ≤ 该值时匹配 |
| `min_input_tokens` | int | 预估输入 token 数 ≥ 该值时匹配 |
| `has_tools` | bool | 请求包含工具定义时匹配 |
| `has_reasoning` | bool | `enable_thinking` 为 true 时匹配 |
| `has_vision` | bool | 最后一条 user 消息包含 `image_url` 类型内容时匹配 |
| `max_tool_count` | int | 工具数量 ≤ 该值时匹配 |
| `min_tool_count` | int | 工具数量 ≥ 该值时匹配 |

> **注意**：Token 预估使用 `len(content) / 4` 启发式方法（约每 4 个字符 1 个 token），图片按 detail 模式估算（low=85 tokens/张，high/auto=765 tokens/张）。所有指定条件必须同时满足（AND 逻辑）。未指定的字段不参与检查。
>
> **视觉检测范围**：`has_vision` 仅检测**最后一条 `role: "user"` 的消息**是否包含图片，而非扫描全部 messages。多轮对话中，如果用户早期发送了图片但后续追问是纯文本，`has_vision` 为 false，避免将纯文本追问路由到昂贵的视觉模型。

### 1.4 负载均衡策略

| 策略 | `load_balance` 值 | 行为 | 适用场景 |
|------|-------------------|------|----------|
| **轮询** | `round-robin`（默认） | 通过原子计数器轮转候选列表 | 子模型能力相近，均匀分流 |
| **最少并发优先** | `least-inflight` | 按进行中请求数升序排列候选列表；并列时轮询打散 | DeepNode + Provider 混合部署，容量差异较大 |

**最少并发优先（least-inflight）详细说明**：
- Gateway 实时追踪每个子模型的进行中请求数（`ChildModelTracker`）。
- 候选列表按 inflight 数排序，待处理请求最少的模型排在最前。
- 当多个模型 inflight 数相同时，通过轮询旋转打散，避免惊群效应。
- 降级池中的模型（不在匹配规则中的）同样按 inflight 数排序。

> **何时使用 `least-inflight`**：如果你的 Hybrid 模型混合了本地 DeepNode（GPU 有限，可能排队）和云端 Provider（高吞吐，按量付费），`least-inflight` 会在 DeepNode 繁忙时自动将请求路由到 Provider，而不是排队等待。

### 1.5 配置示例

#### 示例 1：按请求复杂度路由

短请求发送到轻量本地模型；长/复杂请求发送到强力 Provider。

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

#### 示例 2：推理与非推理分流

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

#### 示例 3：视觉理解请求路由

将包含图片的请求路由到支持视觉理解的模型；纯文本请求路由到轻量本地模型。

```yaml
load_balance: least-inflight

rules:
  - name: "vision_requests"
    condition:
      has_vision: true
    targets:
      - "qwen-vl-proxy"
      - "gpt-4o-proxy"

  - name: "text_only"
    condition:
      has_vision: false
    targets:
      - "qwen3-0.6b-local"

default_targets:
  - "qwen3-0.6b-local"
  - "gpt-4o-proxy"
```

#### 示例 4：留空使用简单轮询

如果未配置路由策略 YAML，所有子模型将使用轮询负载均衡并自动降级。

#### 示例 5：基于并发感知的 least-inflight 路由

适用于 DeepNode + Provider 混合部署，本地设备在高负载下可能饱和的场景。

```yaml
load_balance: least-inflight

rules:
  - name: "tool_calling"
    condition:
      has_tools: true
    targets:
      - "gpt-4o-proxy"

default_targets:
  - "gemma-4-e4b-it-8bit"
  - "gpt-4o-mini-proxy"
```

在此配置中：
- 工具调用请求始终路由到有能力的 Provider。
- 其他请求路由到进行中请求最少的子模型 — 如果本地 DeepNode 繁忙，流量会自动转移到 Provider。

### 1.6 降级机制

当候选模型在**向客户端写入任何响应字节之前**失败时，系统自动尝试下一个候选。完整的候选顺序为：

1. 匹配规则的 `targets` 中的模型（按负载均衡策略排序）
2. 不在匹配 targets 中的所有剩余子模型（使用 `least-inflight` 时同样按 inflight 数排序）

> **重要**：一旦响应流式传输已开始（字节已写入），则无法降级，错误将直接返回给客户端。

---

## 2. 计费策略

### 2.1 计费角色

| 角色 | 说明 | 适用范围 |
|------|------|----------|
| **消费者（pricing_tiers）** | 发送请求的用户付费 | 所有模型类型 |
| **贡献者（contributor_tiers）** | 提供算力的设备所有者获得收益 | 仅 DeepNode 模型 |

### 2.2 按模型类型的配置规则

| 模型类型 | 消费者计费（pricing_tiers） | 贡献者计费（contributor_tiers） |
|----------|---------------------------|-------------------------------|
| **DeepNode** | ✅ 在此配置 | ✅ 在此配置 |
| **Provider** | ✅ 在此配置 | ❌ 不适用（无贡献者） |
| **Hybrid** | 动态（来自实际子模型） | ❌ 继承自实际子模型 |

### 2.3 Hybrid 计费机制

Hybrid 模型使用**动态计费** — 不在 Hybrid 模型本身配置 `pricing_tiers`。当请求被处理时：

1. **消费者费用**：使用**实际处理请求的子模型的 `pricing_tiers`** 计算
2. **贡献者收益**：使用**实际处理请求的子模型的 `contributor_tiers`** 计算
   - 如果子模型是 DeepNode → 使用该 DeepNode 的 contributor_tiers
   - 如果子模型是 Provider → 贡献者收益为 0（无设备贡献者）

```
用户请求 → hybrid-model（无自有定价）
              │
              ├─ 路由到 deepnode-child → pricing_tiers：向用户收费 ¥X
              │                       → contributor_tiers：支付设备所有者 ¥Y
              │
              └─ 路由到 provider-child → pricing_tiers：向用户收费 ¥Z
                                      → 贡献者收益：¥0
```

> **为何使用动态计费**：不同子模型的成本可能差异巨大（如本地 0.6B 模型 vs. GPT-4o）。动态计费确保用户支付的价格准确反映实际使用的计算后端。公开 API 展示由所有子模型计算得出的价格区间，让用户了解可能的费用范围。

### 2.4 阶梯定价配置

定价使用基于输入 token 数的阶梯匹配：

```
pricing_tiers:
  ┌──────────────────┬─────────────┬──────────────┐
  │ max_input_tokens │ input_price │ output_price  │
  │ (0 = 不限)       │ (¥/百万token)│ (¥/百万token) │
  ├──────────────────┼─────────────┼──────────────┤
  │ 4096             │ 1.00        │ 2.00         │
  │ 32768            │ 2.00        │ 4.00         │
  │ 0 (兜底)         │ 4.00        │ 8.00         │
  └──────────────────┴─────────────┴──────────────┘
```

**匹配逻辑**：
1. 按顺序遍历阶梯
2. 选择**第一个** `prompt_tokens <= max_input_tokens` 的阶梯
3. `max_input_tokens = 0` 表示不限（兜底阶梯，应放在最后）
4. 如无阶梯匹配，回退到最后一个阶梯

**费用公式**：
```
cost_yuan = prompt_tokens × input_price / 1,000,000
          + completion_tokens × output_price / 1,000,000
```

> **精度**：所有金额在数据库中以 `DECIMAL(20,10)` 存储（单位：元），保留最多 10 位小数。不进行四舍五入 — 即使极小的请求也能被精确计费。

### 2.5 配置示例

#### 示例：带贡献者阶梯的 DeepNode 模型

```
pricing_tiers（消费者）：
  ≤4K tokens：input ¥1.00/M，output ¥2.00/M
  不限：      input ¥2.00/M，output ¥4.00/M

contributor_tiers（设备所有者）：
  ≤4K tokens：input ¥0.50/M，output ¥1.00/M
  不限：      input ¥1.00/M，output ¥2.00/M
```

#### 示例：Hybrid 模型计费（动态）

```
hybrid-model 无自有 pricing_tiers。
子模型：deepnode-child（input ¥1.00/M，output ¥2.00/M）+ provider-child（input ¥10.00/M，output ¥30.00/M）

→ 公开 API 展示价格区间：input ¥1.00 ~ ¥10.00/M，output ¥2.00 ~ ¥30.00/M

→ 如果路由到 deepnode-child：
    消费者费用：input ¥1.00/M，output ¥2.00/M（来自 deepnode-child 的 pricing_tiers）
    贡献者收益：来自 deepnode-child 的 contributor_tiers

→ 如果路由到 provider-child：
    消费者费用：input ¥10.00/M，output ¥30.00/M（来自 provider-child 的 pricing_tiers）
    贡献者收益 = ¥0
```

#### 示例：免费模型

`pricing_tiers` 留空 → 模型对消费者免费。

---

## 3. 流式超时配置

### 3.1 背景

流式（SSE）推理请求与传统的"整体超时"语义天然冲突 —— 长推理、长生成（尤其是 reasoning 模型）可能连续数分钟输出 token，但每两个 chunk 之间应当保持较短的间隔；如果某个上游"连上了但不吐 token"或"中途卡住"，整条链路会一直阻塞，客户端超时后连接挂起、资源占用、降级机会也被白白浪费。

为此 DeepPool 为**所有流式链路**（包括 Hybrid 的 Provider / DeepNode 子模型，以及非 Hybrid 的直连模型）统一应用两段式健康度守护：

| 参数 | 作用 | 默认值 |
|------|------|--------|
| `first_token_timeout_seconds` | **首 token 超时（TTFT）**：从任务下发到收到首个 chunk 的最大等待时间 | `10` 秒 |
| `inter_chunk_idle_timeout_seconds` | **chunk 间 idle 超时**：两个连续 chunk 之间允许的最大间隔 | `20` 秒 |

**语义要点**：
- 一旦收到首个 chunk，`first_token_timeout` 解除，切换为 `inter_chunk_idle`。
- `inter_chunk_idle` 在每次收到新 chunk 时重置；只要 chunk 持续流入，整体时长不设上限。
- 超时触发时主动断开上游连接；如果此时尚未向客户端写入过字节，Hybrid 会自动降级到下一个候选；否则以 OpenAI 风格的 SSE `error` 事件结束流。

### 3.2 生效链路

同一份配置同时作用于以下三处（对称语义、同步调整）：

| 位置 | 说明 |
|------|------|
| Gateway → Provider（HTTP SSE） | OpenAI / 百度千帆 / 任何第三方 provider 的 SSE 行读循环 |
| Gateway → NodeManager（gRPC stream） | Gateway 侧 gRPC `Recv` 兜底，避免 NodeManager 假死时 Gateway 无限等待 |
| NodeManager → DeepNode（隧道 chunk 通道） | 设备未按时吐出 chunk 时，任务被中止并记录推理失败日志 |

### 3.3 配置位置

流式超时是**顶层配置**，不再位于 hybrid 路由策略文件中。分别在 Manager 与 NodeManager 各自的 YAML 中声明：

**`manager.yaml`**（Gateway 使用）：
```yaml
# Stream-level liveness timeouts shared with NodeManager.
# 0 means "use code default" (10s / 20s).
stream_timeouts:
  first_token_timeout_seconds: 10
  inter_chunk_idle_timeout_seconds: 20
```

**`nodemanager.yaml`**（DispatchService 使用）：
```yaml
stream_timeouts:
  first_token_timeout_seconds: 10
  inter_chunk_idle_timeout_seconds: 20
```

> **为什么不放在 hybrid policy 里**：policy 语义上只描述"**怎么选 child**"，不是"每个 child 执行时的健康度兜底"。放在顶层 `stream_timeouts` 后，非 Hybrid 的直连 Provider / 直连 DeepNode 模型也能自动享受同一套保护，避免"只有 Hybrid 的 child 才有兜底"的语义错位。

### 3.4 调参建议

| 场景 | 建议 |
|------|------|
| 通用（默认） | 保持 10s / 20s |
| DeepNode 冷启动 / 大模型 load 较慢 | 适当放宽 `first_token_timeout_seconds` 到 20~30s |
| reasoning 模型（深度推理、chunk 间隔可能较长） | 适当放宽 `inter_chunk_idle_timeout_seconds` 到 30~60s |
| 追求更激进的 Hybrid 降级 | 收紧 `first_token_timeout_seconds` 到 5~8s，让卡住的候选更快失败以切换 |

> **提示**：任一字段设为 `0` 或缺省时，组件将自动回退到代码默认值。改动需重启 Manager / NodeManager 才生效。

---

## 4. 快速参考

### 模型创建清单

| 步骤 | DeepNode | Provider | Hybrid |
|------|----------|----------|--------|
| model_name | ✅ 必填 | ✅ 必填 | ✅ 必填 |
| repo_id | ✅ 必填 | — | — |
| endpoint + api_key | — | ✅ 必填 | — |
| child_models（≥2） | — | — | ✅ 必填 |
| routing_policy | — | — | 可选（YAML） |
| pricing_tiers | 可选 | 可选 | —（动态来自子模型） |
| contributor_tiers | 可选 | — | —（继承自子模型） |

### 常见错误

1. **在 Hybrid 上设置 pricing_tiers** → 会被忽略并清除；消费者计费动态来自实际子模型。
2. **在 Hybrid 上设置 contributor_tiers** → 会被忽略；贡献者计费来自实际子模型。
3. **路由策略 targets 不在 child_models 中** → 校验错误；所有 targets 必须引用已有的子模型。
4. **仅 1 个子模型** → 校验错误；Hybrid 至少需要 2 个子模型。
5. **递归 Hybrid** → 不允许；Hybrid 的子模型不能是另一个 Hybrid。
