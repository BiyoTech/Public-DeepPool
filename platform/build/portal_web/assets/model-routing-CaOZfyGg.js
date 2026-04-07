const n=`# 模型路由与 Hybrid 调度

## 模型三分类

DeepPool 中每个模型都有一个 \`vendor_type\`，决定了请求的路由路径：

| VendorType | 路由方式 | 说明 |
|-----------|---------|------|
| **deepnode** | Gateway → gRPC → NodeManager → 设备隧道 | 边缘设备本地推理，低延迟 |
| **provider** | Gateway → HTTP 代理 → 云端 API | OpenAI、百度千帆等云端大模型 |
| **hybrid** | Gateway → 智能分发 → DeepNode 或 Provider | 多模型组合，条件路由 + 自动故障转移 |

## Provider 代理

Provider 类型的模型作为云端 API 的透明代理：

- **请求改写**：\`model\` 字段替换为配置的 \`upstream_model\`
- **认证透传**：使用模型配置中的 \`api_key\` 向上游认证
- **响应改写**：响应中的 \`model\` 字段替换回 DeepPool 对外暴露的名称
- **流式支持**：SSE 逐行转发，实时 flush

调用方完全感知不到底层是云端 API 还是边缘设备。

## Hybrid 智能调度

Hybrid 是生产环境的推荐模型类型，核心能力：

### 工作流程

\`\`\`
请求到达 → 提取请求特征 → 匹配路由策略 → 生成候选列表 → 逐个尝试
                                                        ↓
                                             成功 → 返回结果
                                             失败 → 尝试下一个
                                             全部失败 → 503
\`\`\`

### 请求特征提取

系统从请求体中提取以下特征用于路由决策：

| 特征 | 计算方式 |
|------|---------|
| InputTokens | 所有 message content 字符总长 ÷ 4 |
| ToolCount | tools 数组长度 |
| HasTools | 是否包含 function calling |
| HasReasoning | enable_thinking 是否为 true |

### 路由策略（YAML）

管理员可为每个 Hybrid 模型配置路由策略：

\`\`\`yaml
load_balance: "round-robin"

rules:
  # 长上下文请求路由到云端大模型
  - name: "long_context"
    condition:
      min_input_tokens: 2000
    targets: ["gpt-4o-provider"]

  # Function Calling 请求优先本地
  - name: "tool_call"
    condition:
      has_tools: true
    targets: ["qwen3-deepnode", "gpt-4o-provider"]

  # 推理模式请求路由到专用模型
  - name: "reasoning"
    condition:
      has_reasoning: true
    targets: ["deepseek-r1-provider"]

# 无规则命中时的默认目标
default_targets: ["qwen3-deepnode"]
\`\`\`

### 匹配逻辑

1. **按顺序遍历 rules**，每条 rule 的 condition 内部取 AND
2. **首个命中的 rule** 生效，其 targets 通过 Round-Robin 轮询选出首选
3. **追加 Fallback**：child_models 中未出现在 targets 的模型追加到末尾
4. **故障转移**：首选模型失败时自动切到下一个，全部失败返回 503
5. **防递归**：子模型不允许也是 Hybrid 类型

### 示例

假设 Hybrid 模型配置了 \`child_models: ["local-qwen", "cloud-gpt4", "cloud-deepseek"]\`：

| 请求特征 | 匹配规则 | 候选列表 |
|---------|---------|---------|
| 100 tokens, 无 tools | 无匹配 → default | \`["local-qwen", "cloud-gpt4", "cloud-deepseek"]\` |
| 3000 tokens | long_context | \`["cloud-gpt4", "local-qwen", "cloud-deepseek"]\` |
| 有 tools | tool_call | \`["local-qwen", "cloud-gpt4", "cloud-deepseek"]\` |

## PolicyCache 缓存机制

- 从数据库每 10 秒轮询同步所有 Hybrid 模型的路由策略
- 仅在 \`updated_at\` 变化时重新解析 YAML
- 管理员修改策略后 ~10 秒自动生效，无需重启
- 多 Manager 节点通过 DB polling 保持一致
`;export{n as default};
