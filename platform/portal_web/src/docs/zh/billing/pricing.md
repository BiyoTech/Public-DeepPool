# 计费说明

DeepPool 采用**按量计费**模式，根据每次 API 调用实际消耗的 Token 数量计费。本文详细说明计费策略、Token 类型、Cached Tokens 优惠机制以及如何查看模型单价和消费明细。

## 计费概览

每次 API 调用产生的费用由两部分组成：

| 费用组成 | 说明 |
|---------|------|
| **输入费用** | 基于发送给模型的 prompt token 数量（含 system、user、assistant 上下文消息） |
| **输出费用** | 基于模型生成的 completion token 数量（含 reasoning/thinking 思考 token） |

> **单位**：所有价格以 **元 / 百万 Token** 为单位。

---

## Token 类型说明

API 响应中的 `usage` 字段包含详细的 Token 用量统计，完整兼容 OpenAI 标准格式：

```json
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
```

### 各字段含义

| 字段 | 说明 |
|------|------|
| `prompt_tokens` | 本次请求的总输入 Token 数 |
| `completion_tokens` | 模型生成的总输出 Token 数（包含 reasoning tokens） |
| `total_tokens` | 输入 + 输出总和 |
| `prompt_tokens_details.cached_tokens` | 命中上下文缓存的输入 Token 数（享受优惠费率） |
| `prompt_tokens_details.audio_tokens` | 音频输入 Token 数（保留字段，当前为 0） |
| `completion_tokens_details.reasoning_tokens` | 模型思考/推理阶段消耗的 Token 数 |
| `completion_tokens_details.audio_tokens` | 音频输出 Token 数（保留字段，当前为 0） |

---

## Cached Tokens 优惠计费

### 什么是 Cached Tokens？

当你的请求中包含与之前请求相同的上下文前缀（如重复的 system prompt、多轮对话中不变的历史消息），部分模型可以命中上下文缓存。命中缓存的 Token 以 **Cached Tokens** 标识，享受大幅优惠费率。

### 计费费率

| Token 类型 | 计费费率 | 说明 |
|-----------|---------|------|
| 普通输入 Token（Prompt Tokens） | **100%** | 未命中缓存的输入 Token，按模型标准输入单价计费 |
| 缓存命中 Token（Cached Tokens） | **20%** | 命中缓存的输入 Token，按标准输入单价的 **20%** 计费 |
| 输出 Token（Completion Tokens） | **100%** | 模型生成的输出 Token，按模型标准输出单价计费 |

### 计费公式

```
输入费用 = (prompt_tokens - cached_tokens) × 输入单价 / 1,000,000
         + cached_tokens × 输入单价 × 0.2 / 1,000,000

输出费用 = completion_tokens × 输出单价 / 1,000,000

总费用   = 输入费用 + 输出费用
```

### 计费示例

假设模型输入单价为 **6 元/百万Token**，输出单价为 **12 元/百万Token**：

| 场景 | prompt_tokens | cached_tokens | completion_tokens | 费用计算 | 总费用 |
|------|:---:|:---:|:---:|------|:---:|
| 无缓存 | 10,000 | 0 | 5,000 | (10000×6 + 5000×12) / 1M | 0.12 元 |
| 50% 缓存 | 10,000 | 5,000 | 5,000 | (5000×6 + 5000×6×0.2 + 5000×12) / 1M | 0.096 元 |
| 全部缓存 | 10,000 | 10,000 | 5,000 | (10000×6×0.2 + 5000×12) / 1M | 0.072 元 |

> **💡 提示**：缓存命中是自动生效的，用户无需额外配置。当模型不支持缓存或未命中时，`cached_tokens` 为 0，计费退化为标准公式。

---

## 阶梯定价

DeepPool 支持**阶梯定价**机制——同一模型根据单次请求的输入 Token 数量可能适用不同的单价区间：

| 模型示例 | 输入 Token 范围 | 输入单价（元/百万Token） | 输出单价（元/百万Token） |
|---------|:---:|:---:|:---:|
| glm5.1 | 0 < Token ≤ 32K | 6 | 12 |
| glm5.1 | 32K < Token ≤ 80K | 7 | 18 |
| glm5.1 | 80K < Token ≤ 200K | 8 | 20 |

系统会根据单次请求的 `prompt_tokens` 数量自动匹配适用的价格区间。

---

## 如何查看模型计费单价

你可以在 DeepPool 平台的 **「数据」** 菜单下查看每个模型的计费单价：

1. 登录 DeepPool 平台
2. 点击顶部导航栏的 **「数据」** 菜单
3. 切换到 **「计费说明」** 标签页
4. 页面中会展示所有模型的定价信息，包括：
   - 模型名称、参数规模、上下文长度
   - 各阶梯的输入 Token 范围
   - 对应的输入单价和输出单价（元/百万 Token）

---

## 如何查看消费明细

在 **「数据」** 菜单下你还可以查看详细的 API 消费记录：

1. 点击顶部导航栏的 **「数据」** 菜单
2. 切换到 **「API 消耗」** 标签页
3. 页面展示按日汇总的消费数据，包括：
   - 总消耗 Token 数 / 总请求数
   - 按日期、模型的消耗明细
   - 每条记录的费用金额

你也可以按时间范围、模型名称进行筛选，方便追踪特定时段或模型的消费情况。

---

## 免费额度与折扣

- **免费 Token 额度**：新注册用户和特定活动可能获得免费 Token 额度，使用时优先消耗免费额度
- **折扣策略**：部分用户可能享受折扣优惠，折扣在免费额度用完后、从钱包扣费前生效

> 免费额度和折扣信息可在「数据」页面或个人中心查看。

---

## 常见问题

### Cached Tokens 是怎么产生的？

当你的连续请求中包含相同的前缀内容（如固定的 system prompt 或多轮对话中未变的历史消息），模型会自动命中上下文缓存。这是由模型底层自动识别的，无需手动配置。

### 为什么我的请求没有 Cached Tokens？

可能原因：
- 当前请求是该会话的第一次请求（无前序缓存可命中）
- 请求的上下文前缀与之前的请求不同
- 使用的模型不支持上下文缓存功能

### reasoning_tokens 如何计费？

`reasoning_tokens` 是 `completion_tokens` 的一部分（不是额外计费），已包含在 `completion_tokens` 总数中，按输出单价计费。

### Hybrid 模型如何计费？

Hybrid 模型会智能路由到最合适的子模型，计费按实际命中的子模型单价计算。你可以在消费明细中看到每次调用实际使用的模型和对应费用。
