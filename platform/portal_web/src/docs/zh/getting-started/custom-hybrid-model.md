# 自定义 Hybrid 模型

## 概述

DeepPool 允许 API 使用者创建个人自定义的 Hybrid 模型。你可以通过编写 YAML 路由策略，将多个平台公开模型组合成一个智能调度入口，实现**条件路由 + 自动故障转移 + 负载均衡**。

**核心特性：**

- 自定义 Hybrid 模型仅创建者本人可见、可调用
- 子模型从平台已公开的模型中选择（不能包含其他 Hybrid 模型）
- 通过 YAML 配置文件定义路由策略，用户可随时修改
- 每位用户最多创建 10 个自定义 Hybrid 模型
- 计费按实际路由到的子模型定价计算

## 使用入口

登录后进入「服务」页面 → 右侧面板切换到「我的模型」Tab。

## 创建模型

1. 点击「+ 创建」按钮
2. 填写**模型名称**（2-32 位，支持英文/数字/下划线/短横线）
3. 选择**子模型**（至少 2 个，不能选择 Hybrid 类型模型）
4. 编写**路由策略 YAML**（可选，留空使用默认 least-inflight 策略）
5. 点击「保存」

创建后，模型标识格式为 `u{用户ID}-{模型名称}`，可直接在 API 调用中使用。

## 路由策略 YAML 完整格式

```yaml
# ============================================================================
# 负载均衡策略（必选其一）
#   - least-inflight: 优先选择当前并发最少的模型（推荐）
#   - round-robin:    轮询分配
# ============================================================================
load_balance: "least-inflight"

# 每个 deepnode 类型子模型的 Gateway 级最大并发数
# 超过此数则跳过该模型，选择下一个。0 = 使用系统默认值。
max_inflight_per_deepnode_child: 2

# ============================================================================
# 条件路由规则（按顺序从上到下匹配，首个 condition 全部满足的 rule 生效）
# ============================================================================
rules:
  - name: "rule_name"        # 规则名称（仅用于日志标识，任意字符串）
    condition:               # 匹配条件（同一 rule 内多个条件取 AND）
      min_input_tokens: 0    # 输入 Token 数 ≥ 此值
      max_input_tokens: 0    # 输入 Token 数 ≤ 此值
      has_tools: false       # 请求是否包含 Function Calling
      has_reasoning: false   # 请求是否开启推理模式 (enable_thinking=true)
      has_vision: false      # 请求是否包含图片/视觉内容
      min_tool_count: 0      # Tools 数量 ≥ 此值
      max_tool_count: 0      # Tools 数量 ≤ 此值
      tags: ["tag1"]         # 请求的 tag 在列表中即命中（OR 语义，大小写不敏感）
    targets:                 # 命中此规则时的候选模型列表（按偏好顺序排列）
      - "model-a"
      - "model-b"

# ============================================================================
# 无规则命中时的默认目标
# 留空 [] = 使用所有 child_models + 负载均衡策略分配
# ============================================================================
default_targets:
  - "model-a"
  - "model-b"
```

## 条件字段详解

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `min_input_tokens` | int | 输入 Token 数 ≥ 此值时匹配 | `min_input_tokens: 128001` → 超长上下文 |
| `max_input_tokens` | int | 输入 Token 数 ≤ 此值时匹配 | `max_input_tokens: 2000` → 短文本 |
| `has_tools` | bool | 请求是否包含 Function Calling | `has_tools: true` |
| `has_reasoning` | bool | 请求是否开启推理模式（enable_thinking=true） | `has_reasoning: true` |
| `has_vision` | bool | 请求最后一条 user 消息是否包含图片/视频 | `has_vision: true` |
| `min_tool_count` | int | 请求中 tools 数量 ≥ 此值 | `min_tool_count: 3` → 复杂 Agent 场景 |
| `max_tool_count` | int | 请求中 tools 数量 ≤ 此值 | `max_tool_count: 2` → 简单工具调用 |
| `tags` | []string | 请求携带的 tag 匹配列表中任一值即命中 | `tags: ["data-analysis"]` |

**注意：**
- 同一 rule 内多个 condition 字段取 **AND** 关系
- 只需写需要的条件字段，未写的字段不参与匹配
- Token 数由系统自动从请求体中估算（所有 message content 字符总长 ÷ 4 + 图片 Token）
- `tags` 匹配大小写不敏感，列表中多个值之间为 **OR** 关系

## 匹配与故障转移逻辑

```
请求到达 → 提取请求特征 → 按顺序匹配 rules → 首个命中的 rule 生效
                                                    ↓
                                         rule.targets 按负载均衡排序
                                                    ↓
                                         追加 Fallback（子模型中未在 targets 出现的）
                                                    ↓
                                         逐个尝试调用
                                                    ↓
                                         成功 → 返回结果
                                         失败 → 自动切下一个
                                         全部失败 → 503
```

**详细流程：**

1. **特征提取**：系统自动从请求中提取 InputTokens、HasTools、ToolCount、HasReasoning、HasVision、Tag 等特征
2. **规则匹配**：从 `rules` 列表中按顺序遍历，首个 condition 全部满足的 rule 生效
3. **候选排序**：生效 rule 的 `targets` 按负载均衡策略排序（如 least-inflight 选并发最少的）
4. **Fallback 追加**：子模型中未出现在 targets 列表的模型追加到候选末尾
5. **故障转移**：首选模型调用失败时自动切换到下一个候选模型
6. **无匹配**：如果所有 rules 都不匹配，使用 `default_targets`

## 负载均衡策略

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| `least-inflight` | 优先选择当前并发请求数最少的模型 | **推荐默认使用**，自动均衡负载 |
| `round-robin` | 按顺序依次轮询分配 | 模型能力相近时适用 |

## 完整示例

### 示例 1：最简配置（默认策略）

留空 YAML 或使用以下最简配置，表示所有子模型使用 least-inflight 均匀分配：

```yaml
load_balance: "least-inflight"
rules: []
default_targets: []
```

### 示例 2：成本优先的 5 模型混合

以下策略适用于选择了多个不同价位模型的场景，核心思想是**低成本优先、按需升级**：

```yaml
# ============================================================================
# 成本优先的 5 模型混合策略
# ============================================================================
# 子模型价格参考（从便宜到贵）:
#   1. qwen3.6-plus    — 最便宜, 1M上下文, 支持工具调用
#   2. ernie-5.0       — 中低价, 128K上下文, 支持视觉/音频/视频
#   3. kimi-k2.6       — 中价, 256K上下文, 支持视觉+视频, 擅长Agent
#   4. gpt-5.4         — 较贵, 1M上下文, 支持视觉, 均衡
#   5. gpt-5.5         — 最贵, 1M上下文, 综合最强
#
# 路由思路：
#   - 默认路由到最便宜的模型
#   - 视觉请求 → 有视觉能力的模型（按价格排序）
#   - 超长上下文 → 支持1M的模型
#   - 深度推理 → 最强模型
#   - 复杂Agent → 擅长Agent的模型
# ============================================================================

load_balance: least-inflight
max_inflight_per_deepnode_child: 2

rules:
  # ── 视觉/多模态请求 ──
  # 路由到支持视觉的模型（价格从低到高）
  - name: "vision_requests"
    condition:
      has_vision: true
    targets:
      - "ernie-5.0"
      - "kimi-k2.6"
      - "gpt-5.4"
      - "gpt-5.5"

  # ── 超长上下文 >256K ──
  # 只有 qwen3.6-plus、gpt-5.4、gpt-5.5 支持 1M
  - name: "ultra_long_context_gt_256k"
    condition:
      min_input_tokens: 256001
    targets:
      - "qwen3.6-plus"
      - "gpt-5.4"
      - "gpt-5.5"

  # ── 长上下文 128K-256K ──
  # ernie-5.0 仅支持128K，排除
  - name: "long_context_128k_to_256k"
    condition:
      min_input_tokens: 128001
      max_input_tokens: 256000
    targets:
      - "qwen3.6-plus"
      - "kimi-k2.6"
      - "gpt-5.4"

  # ── 深度推理任务 ──
  # 需要 enable_thinking 时，优先最强模型
  - name: "reasoning_tasks"
    condition:
      has_reasoning: true
    targets:
      - "gpt-5.5"
      - "ernie-5.0"
      - "gpt-5.4"
      - "qwen3.6-plus"

  # ── 复杂 Agent/工具调用 (≥3 tools) ──
  # kimi-k2.6 擅长多步骤 Agent 工作流
  - name: "heavy_tool_calling"
    condition:
      has_tools: true
      min_tool_count: 3
    targets:
      - "kimi-k2.6"
      - "gpt-5.5"
      - "qwen3.6-plus"

  # ── 简单工具调用 (1-2 tools) ──
  # 优先最便宜的支持 function-call 的模型
  - name: "simple_tool_calling"
    condition:
      has_tools: true
      max_tool_count: 2
    targets:
      - "qwen3.6-plus"
      - "ernie-5.0"
      - "kimi-k2.6"

  # ── 短文本简单请求 (≤2000 tokens, 无工具) ──
  # 直接路由到最便宜模型
  - name: "short_simple_requests"
    condition:
      max_input_tokens: 2000
      has_tools: false
    targets:
      - "qwen3.6-plus"
      - "ernie-5.0"

  # ── 中等上下文通用请求 (2K-128K, 无工具无推理) ──
  # 按成本排序
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

# ── 默认 fallback ──
# 无规则命中时，按价格从低到高排列
default_targets:
  - "qwen3.6-plus"
  - "ernie-5.0"
  - "kimi-k2.6"
  - "gpt-5.4"
  - "gpt-5.5"
```

### 示例 3：推理优先的 4 模型组合

```yaml
# ============================================================================
# 推理优先策略 — 适合编程/Agent场景
# ============================================================================

load_balance: least-inflight
max_inflight_per_deepnode_child: 2

rules:
  # 超长上下文 (>128K) — 只有部分模型支持
  - name: "ultra_long_context_gt_128k"
    condition:
      min_input_tokens: 128001
    targets:
      - "deepseek-v4-pro"
      - "qwen3.6-max-preview"
      - "glm-5.1"

  # 深度推理 — 优先推理专精模型
  - name: "reasoning_tasks"
    condition:
      has_reasoning: true
    targets:
      - "deepseek-v4-pro"
      - "glm-5.1"
      - "qwen3.6-max-preview"

  # 复杂 Agent (≥3 tools) — Agent 专精模型优先
  - name: "heavy_tool_calling"
    condition:
      has_tools: true
      min_tool_count: 3
    targets:
      - "qwen3.6-max-preview"
      - "deepseek-v4-pro"
      - "deepseek-v3.2"

  # 简单工具调用 — 便宜的优先
  - name: "simple_tool_calling"
    condition:
      has_tools: true
      max_tool_count: 2
    targets:
      - "deepseek-v3.2"
      - "qwen3.6-max-preview"

  # 短文本无工具 — 直接用最便宜的
  - name: "short_simple_requests"
    condition:
      max_input_tokens: 2000
      has_tools: false
    targets:
      - "deepseek-v3.2"

  # 中等上下文通用
  - name: "medium_context_general"
    condition:
      min_input_tokens: 2001
      max_input_tokens: 128000
      has_tools: false
      has_reasoning: false
    targets:
      - "deepseek-v3.2"
      - "deepseek-v4-pro"

# 默认按成本排序
default_targets:
  - "deepseek-v3.2"
  - "deepseek-v4-pro"
  - "qwen3.6-max-preview"
  - "glm-5.1"
```

### 示例 4：双模型极简配置

只有两个子模型时的简单策略：

```yaml
load_balance: least-inflight

rules:
  # 长上下文走云端
  - name: "long_to_cloud"
    condition:
      min_input_tokens: 4000
    targets: ["cloud-model"]

  # 视觉走云端
  - name: "vision_to_cloud"
    condition:
      has_vision: true
    targets: ["cloud-model"]

# 默认本地优先（便宜）
default_targets:
  - "local-model"
  - "cloud-model"
```

### 示例 5：基于 Tag 的业务路由

通过请求中的自定义 tag 将不同业务类型路由到不同模型：

```yaml
load_balance: least-inflight

rules:
  # 数据分析任务 → 推理能力强的模型
  - name: "data_analysis"
    condition:
      tags: ["data-analysis", "data-science"]
    targets:
      - "deepseek-v4-pro"
      - "qwen3.6-max-preview"

  # 聊天和图片生成 → 多模态模型
  - name: "chat_and_photo"
    condition:
      tags: ["chat", "photo-gen"]
    targets:
      - "glm-5.1"

  # 编码任务 + 工具调用 → 代码能力强的模型
  - name: "coding_with_tools"
    condition:
      tags: ["coding"]
      has_tools: true
    targets:
      - "qwen3.6-max-preview"
      - "deepseek-v4-pro"

  # 翻译任务 → 成本优先
  - name: "translation"
    condition:
      tags: ["translation", "i18n"]
    targets:
      - "deepseek-v3.2"

default_targets:
  - "deepseek-v3.2"
  - "deepseek-v4-pro"
```

**调用时传递 tags：**

```bash
curl https://your-deeppool-host/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "u42-my-hybrid",
    "messages": [{"role": "user", "content": "分析这组销售数据的趋势"}],
    "metadata": {"tags": ["data-analysis"]}
  }'
```

也可使用 `x_tags` 顶层字段（`metadata.tags` 优先级更高）：

```json
{
  "model": "u42-my-hybrid",
  "messages": [{"role": "user", "content": "Hello"}],
  "x_tags": ["chat"]
}
```

## 策略设计建议

### 规则排列顺序

规则从上到下匹配，**建议按如下优先级排列**：

1. **特殊能力需求**（视觉、多模态）— 只有部分模型支持
2. **上下文长度限制**（超长 → 长 → 中） — 排除不支持的模型
3. **推理模式** — 推理能力差异大
4. **工具调用复杂度**（复杂 → 简单）
5. **通用文本请求**（按长度细分）

### 成本优化技巧

- `default_targets` 按价格从低到高排列
- 短文本请求（≤2000 tokens）直接路由到最便宜模型
- 只在需要特殊能力时才路由到高价模型
- 利用 `max_input_tokens` 和 `has_tools: false` 组合识别"简单请求"

### targets 注意事项

- `targets` 中的模型名称**必须是你所选子模型之一**
- targets 列表的顺序会影响负载均衡策略的选择偏好
- 未出现在 targets 中的其他子模型会被自动追加为 Fallback

## API 调用

创建成功后，使用模型标识（如 `u42-my-hybrid`）直接调用：

```bash
curl https://your-deeppool-host/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "u42-my-hybrid",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

在 `/v1/models` 接口返回的模型列表中，你的自定义模型也会出现（仅限你自己的 API Key 可见）。

## 注意事项

| 项目 | 说明 |
|------|------|
| 模型名称 | 创建后不可修改；标识格式 `u{uid}-{name}` |
| 子模型约束 | 不能包含 Hybrid 类型（防止递归） |
| targets 校验 | 必须引用已选子模型，否则保存报错 |
| 生效延迟 | 修改策略后约 10 秒自动生效，无需重启 |
| 计费方式 | 按实际路由到的子模型定价计费 |
| 数量限制 | 每用户最多 10 个自定义 Hybrid 模型 |
| 可见性 | 仅创建者可见、可调用 |
