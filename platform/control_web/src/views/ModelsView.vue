<template>
  <div class="models-view space-y-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <t-input
          v-model="keyword"
          placeholder="搜索模型名称 / Upstream Model / Endpoint / Provider"
          clearable
          class="w-96"
          @enter="fetchModels"
          @clear="fetchModels"
        >
          <template #prefix-icon><SearchIcon /></template>
        </t-input>
        <t-button theme="primary" @click="fetchModels">搜索</t-button>
      </div>
      <t-button theme="primary" @click="openCreateDialog">
        <template #icon><AddIcon /></template>
        新增模型
      </t-button>
      <t-button variant="outline" @click="helpVisible = true">
        <template #icon><HelpCircleIcon /></template>
        配置帮助
      </t-button>
    </div>

    <div class="bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <t-table
        :data="models"
        :columns="columns"
        :loading="loading"
        row-key="id"
        :hover="true"
        :stripe="true"
        size="medium"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #vendor_type="{ row }">
          <t-tag :theme="vendorTheme(row.vendor_type)" variant="light" size="small">
            {{ vendorLabelMap[row.vendor_type] || row.vendor_type || '-' }}
          </t-tag>
        </template>

        <template #provider_type="{ row }">
          <span class="text-dp-text-2 text-sm">{{ row.provider_type || '-' }}</span>
        </template>

        <template #route_target="{ row }">
          <div class="text-xs text-dp-text-2 leading-5 max-w-[260px] break-all">
            <template v-if="row.vendor_type === 'hybrid' && row.child_models?.length">
              <div>Children: {{ row.child_models.join(', ') }}</div>
              <div v-if="row.routing_policy" class="text-dp-text-3">Has routing policy</div>
            </template>
            <template v-else>
              <div v-if="row.repo_id">Repo: {{ row.repo_id }}</div>
              <div v-if="row.upstream_model">Upstream: {{ row.upstream_model }}</div>
              <div v-if="row.endpoint">Endpoint: {{ row.endpoint }}</div>
              <span v-if="!row.repo_id && !row.upstream_model && !row.endpoint">-</span>
            </template>
          </div>
        </template>

        <template #api_key_masked="{ row }">
          <span class="text-dp-text-2 text-xs font-mono">{{ row.api_key_masked || '-' }}</span>
        </template>

        <template #supported_engines="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatEngines(row.supported_engines) }}</span>
        </template>

        <template #param_scale="{ row }">
          <span class="text-dp-text-2 text-sm">{{ row.param_scale ? row.param_scale + 'B' : '-' }}</span>
        </template>

        <template #supports_reasoning="{ row }">
          <t-tag v-if="row.supports_reasoning" theme="success" variant="light" size="small">Yes</t-tag>
          <t-tag v-else theme="default" variant="light" size="small">No</t-tag>
        </template>

        <template #supports_function_call="{ row }">
          <t-tag v-if="row.supports_function_call" theme="success" variant="light" size="small">Yes</t-tag>
          <t-tag v-else theme="default" variant="light" size="small">No</t-tag>
        </template>

        <template #max_context_length="{ row }">
          <span class="text-dp-text-2 text-sm">{{ row.max_context_length ? formatContextLength(row.max_context_length) : '-' }}</span>
        </template>

        <template #pricing="{ row }">
          <div class="text-xs text-dp-text-2 leading-5">
            <template v-if="row.pricing_tiers?.length">
              <div v-for="(tier, idx) in row.pricing_tiers" :key="'p'+idx">
                {{ tier.max_input_tokens ? `≤${formatContextLength(tier.max_input_tokens)}` : '∞' }}:
                入{{ tier.input_price }}/出{{ tier.output_price }}
              </div>
            </template>
            <template v-if="row.contributor_tiers?.length">
              <div class="text-dp-text-3 mt-0.5">贡献者:</div>
              <div v-for="(tier, idx) in row.contributor_tiers" :key="'c'+idx" class="text-dp-text-3">
                {{ tier.max_input_tokens ? `≤${formatContextLength(tier.max_input_tokens)}` : '∞' }}:
                入{{ tier.input_price }}/出{{ tier.output_price }}
              </div>
            </template>
            <span v-if="!row.pricing_tiers?.length && !row.contributor_tiers?.length" class="text-dp-text-3">免费</span>
          </div>
        </template>

        <template #enabled="{ row }">
          <t-tag v-if="row.enabled" theme="success" variant="light" size="small">启用</t-tag>
          <t-tag v-else theme="default" variant="light" size="small">禁用</t-tag>
        </template>

        <template #allow_external_call="{ row }">
          <t-tag v-if="row.allow_external_call" theme="success" variant="light" size="small">允许</t-tag>
          <t-tag v-else theme="warning" variant="light" size="small">禁止</t-tag>
        </template>

        <template #created_at="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatTime(row.created_at) }}</span>
        </template>

        <template #op="{ row }">
          <div class="flex items-center gap-2">
            <t-button variant="text" theme="primary" size="small" @click="openEditDialog(row)">编辑</t-button>
            <t-button
              variant="text"
              :theme="row.enabled ? 'warning' : 'success'"
              size="small"
              @click="toggleEnabled(row)"
            >
              {{ row.enabled ? '禁用' : '启用' }}
            </t-button>
            <t-button
              variant="text"
              :theme="row.allow_external_call ? 'warning' : 'success'"
              size="small"
              @click="toggleExternalCall(row)"
            >
              {{ row.allow_external_call ? '禁止外调' : '允许外调' }}
            </t-button>
            <t-popconfirm content="确认删除该模型？删除后不可恢复。" @confirm="handleDelete(row.id)">
              <t-button variant="text" theme="danger" size="small">删除</t-button>
            </t-popconfirm>
          </div>
        </template>
      </t-table>
    </div>

    <t-dialog
      v-model:visible="dialogVisible"
      :header="isEdit ? '编辑模型' : '新增模型'"
      :confirm-btn="{ loading: saving }"
      width="760px"
      @confirm="handleSave"
    >
      <t-form :data="formData" label-width="150px" class="mt-4">
        <t-form-item label="模型名称" required>
          <div class="w-full space-y-2">
            <t-input v-model="formData.model_name" placeholder="管理员自定义唯一模型名称，如 gpt-4o-proxy" />
            <div class="text-xs text-dp-text-3">该字段是门户与统一网关暴露给用户的唯一模型标识。</div>
          </div>
        </t-form-item>

        <t-form-item label="模型来源" required>
          <t-select v-model="formData.vendor_type" :options="vendorOptions" />
        </t-form-item>

        <t-form-item v-if="requiresProvider" label="Provider 类型">
          <t-select v-model="formData.provider_type" :options="providerOptions" clearable />
        </t-form-item>

        <!-- Hybrid: child model selector with rich rendering -->
        <t-form-item v-if="isHybrid" label="子模型列表" required>
          <div class="w-full space-y-2">
            <t-select
              v-model="formData.child_models"
              :loading="loadingChildModels"
              multiple
              filterable
              placeholder="选择至少 2 个 DeepNode / Provider 子模型"
            >
              <t-option
                v-for="opt in childModelOptions"
                :key="opt.value"
                :value="opt.value"
                :label="opt.label"
                style="height: auto; line-height: normal;"
              >
                <div class="flex items-center justify-between w-full gap-2" style="padding: 6px 0;">
                  <div class="flex-1 min-w-0">
                    <div class="font-medium text-sm truncate leading-5">{{ opt.label }}</div>
                    <div
                      v-if="opt.param_scale || opt.max_context_length || opt.tags?.length"
                      class="flex flex-wrap items-center gap-1 mt-0.5 leading-4"
                    >
                      <span v-if="opt.param_scale" class="text-[10px] text-gray-500">{{ opt.param_scale }}B</span>
                      <span v-if="opt.param_scale && opt.max_context_length" class="text-[10px] text-gray-300">|</span>
                      <span v-if="opt.max_context_length" class="text-[10px] text-gray-500">{{ formatContextLength(opt.max_context_length) }}</span>
                      <span
                        v-for="tag in opt.tags"
                        :key="tag"
                        class="inline-flex items-center rounded-full bg-slate-100 px-1.5 text-[10px] text-gray-500 leading-4"
                      >{{ tag }}</span>
                    </div>
                  </div>
                  <span
                    :class="vendorTagClass(opt.vendor_type)"
                    class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  >{{ vendorLabelMap[opt.vendor_type] || opt.vendor_type }}</span>
                </div>
              </t-option>
            </t-select>
            <div class="text-xs text-dp-text-3">选择已有的 DeepNode 或 Provider 模型进行组合路由。</div>
          </div>
        </t-form-item>

        <!-- Hybrid: routing policy YAML editor -->
        <t-form-item v-if="isHybrid" label="调度策略 (YAML)">
          <div class="w-full space-y-2">
            <t-textarea
              v-model="formData.routing_policy"
              placeholder="留空使用默认 round-robin 策略"
              :autosize="{ minRows: 6, maxRows: 20 }"
              class="font-mono text-sm"
            />
            <div class="text-xs text-dp-text-3">
              YAML 格式路由策略，按规则顺序匹配。留空时所有子模型按 round-robin 轮询。
              <a class="text-blue-400 hover:text-blue-300 cursor-pointer ml-1" @click.prevent="helpVisible = true; helpScrollTo = 'routing'">查看配置文档 →</a>
            </div>
          </div>
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="HuggingFace Repo ID" :required="requiresDeepNode">
          <t-input v-model="formData.repo_id" placeholder="如 Qwen/Qwen3-0.6B-MLX-8bit" />
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="模型存储目录">
          <t-input v-model="formData.model_base_dir" placeholder="如 ~/.deeppool/models" />
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="推理引擎">
          <t-input v-model="formData.engine" placeholder="如 vllm_mlx（留空则自动检测）" />
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="支持的引擎列表">
          <t-input v-model="formData.supported_engines" placeholder="逗号分隔，如 vllm_mlx,llamacpp" />
        </t-form-item>

        <t-form-item v-if="requiresProvider" label="Provider Endpoint" :required="requiresProvider">
          <t-input v-model="formData.endpoint" placeholder="如 https://api.openai.com/v1" />
        </t-form-item>

        <t-form-item v-if="requiresProvider" label="上游模型名" :required="requiresProvider">
          <t-input v-model="formData.upstream_model" placeholder="如 gpt-4o-mini" />
        </t-form-item>

        <t-form-item v-if="requiresProvider" label="Provider API Key" :required="!isEdit && requiresProvider">
          <div class="w-full space-y-2">
            <t-input
              v-model="formData.api_key"
              type="password"
              :placeholder="providerAPIKeyPlaceholder"
            />
            <div class="text-xs text-dp-text-3">
              {{ isEdit ? '留空表示保留当前密钥；页面只会展示脱敏后的 key。' : '创建 provider / hybrid 模型时必须填写。' }}
            </div>
          </div>
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="最低内存 (GB)">
          <t-input-number v-model="formData.min_memory_gb" :min="0" :step="0.5" :decimal-places="1" />
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="最低 GPU 显存 (GB)">
          <t-input-number v-model="formData.min_gpu_memory_gb" :min="0" :step="0.5" :decimal-places="1" />
        </t-form-item>

        <t-form-item v-if="requiresDeepNode" label="优先级">
          <t-input-number v-model="formData.priority" :min="0" :max="999" />
        </t-form-item>

        <t-form-item v-if="!isHybrid" label="支持 Reasoning">
          <t-switch v-model="formData.supports_reasoning" />
        </t-form-item>

        <t-form-item v-if="!isHybrid" label="支持 Function Call">
          <t-switch v-model="formData.supports_function_call" />
        </t-form-item>

        <t-form-item v-if="!isHybrid" label="最大上下文长度">
          <t-input-number v-model="formData.max_context_length" :min="0" :step="1024" />
        </t-form-item>

        <t-form-item v-if="!isHybrid" label="模型参数量级 (B)">
          <t-input-number v-model="formData.param_scale" :min="0" :step="0.5" :decimal-places="1" placeholder="如 0.6, 7, 72" />
        </t-form-item>

        <t-form-item label="模型标签">
          <div class="w-full space-y-2">
            <t-tag-input
              v-model="formData.tags"
              placeholder="输入标签后按回车添加，如 多模态、推理增强"
              :max="10"
              clearable
            />
            <div class="text-xs text-dp-text-3">用于描述模型特点，如"多模态"、"推理增强"、"低延迟"。</div>
          </div>
        </t-form-item>

        <t-form-item label="允许外部调用">
          <div class="w-full space-y-2">
            <t-switch v-model="formData.allow_external_call" />
            <div class="text-xs text-dp-text-3">
              关闭后，Portal 用户无法直接调用该模型，但仍可作为 Hybrid 子模型被调度，Admin 也可在 Chat 调试页调用。
            </div>
          </div>
        </t-form-item>

        <!-- Pricing configuration (hidden for hybrid — hybrid uses dynamic billing from child models) -->
        <t-form-item v-if="isHybrid" label="计费策略">
          <div class="text-xs text-dp-text-3">
            Hybrid 模型采用动态计费：按实际路由到的子模型单价计费，无需单独配置。
          </div>
        </t-form-item>
        <t-form-item v-if="!isHybrid" label="计费策略（阶梯）">
          <div class="w-full space-y-3">
            <div
              v-for="(tier, idx) in formData.pricing_tiers"
              :key="idx"
              class="flex items-center gap-2 bg-dp-bg-2 rounded-lg p-2"
            >
              <t-input-number
                v-model="tier.max_input_tokens"
                :min="0"
                :step="1024"
                placeholder="输入Token上限"
                class="w-40"
              />
              <span class="text-xs text-dp-text-3 shrink-0">输入:</span>
              <t-input-number
                v-model="tier.input_price"
                :min="0"
                :step="0.5"
                :decimal-places="2"
                placeholder="元/百万"
                class="w-32"
              />
              <span class="text-xs text-dp-text-3 shrink-0">输出:</span>
              <t-input-number
                v-model="tier.output_price"
                :min="0"
                :step="0.5"
                :decimal-places="2"
                placeholder="元/百万"
                class="w-32"
              />
              <t-button theme="danger" variant="text" size="small" @click="removePricingTier(idx)">删除</t-button>
            </div>
            <t-button theme="default" variant="dashed" size="small" @click="addPricingTier">+ 添加价格区间</t-button>
            <div class="text-xs text-dp-text-3">
              按输入Token长度分段定价（元/百万Token）。输入Token上限填 0 表示无上限（兜底区间）。留空表示免费。
              <a class="text-blue-400 hover:text-blue-300 cursor-pointer ml-1" @click.prevent="helpVisible = true; helpScrollTo = 'billing'">查看计费文档 →</a>
            </div>
          </div>
        </t-form-item>

        <t-form-item v-if="formData.vendor_type === 'deepnode'" label="贡献者收益（阶梯）">
          <div class="w-full space-y-3">
            <div
              v-for="(tier, idx) in formData.contributor_tiers"
              :key="idx"
              class="flex items-center gap-2 bg-dp-bg-2 rounded-lg p-2"
            >
              <t-input-number
                v-model="tier.max_input_tokens"
                :min="0"
                :step="1024"
                placeholder="输入Token上限"
                class="w-40"
              />
              <span class="text-xs text-dp-text-3 shrink-0">输入:</span>
              <t-input-number
                v-model="tier.input_price"
                :min="0"
                :step="0.5"
                :decimal-places="2"
                placeholder="元/百万"
                class="w-32"
              />
              <span class="text-xs text-dp-text-3 shrink-0">输出:</span>
              <t-input-number
                v-model="tier.output_price"
                :min="0"
                :step="0.5"
                :decimal-places="2"
                placeholder="元/百万"
                class="w-32"
              />
              <t-button theme="danger" variant="text" size="small" @click="removeContributorTier(idx)">删除</t-button>
            </div>
            <t-button theme="default" variant="dashed" size="small" @click="addContributorTier">+ 添加收益区间</t-button>
            <div class="text-xs text-dp-text-3">
              按输入Token长度分段设置贡献者收益（元/百万Token）。交互与消费者计费一致。留空表示无收益。
            </div>
          </div>
        </t-form-item>

        <t-form-item label="额外参数 (JSON)">
          <t-textarea v-model="formData.options" placeholder='如 {"n_gpu_layers": -1}' :autosize="{ minRows: 3 }" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Help doc dialog -->
    <t-dialog
      v-model:visible="helpVisible"
      header="模型管理配置帮助"
      :footer="false"
      width="900px"
      placement="center"
    >
      <div class="help-doc-content prose prose-sm max-h-[70vh] overflow-y-auto px-2" v-html="helpHtml" />
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { SearchIcon, AddIcon, HelpCircleIcon } from 'tdesign-icons-vue-next'
import { MessagePlugin } from 'tdesign-vue-next'
import { getModels, getEnabledModels, createModel, updateModel, deleteModel } from '@/api/admin'

interface ModelRow {
  id: number
  model_name: string
  vendor_type: string
  provider_type?: string
  repo_id?: string
  model_base_dir?: string
  engine?: string
  supported_engines?: string[]
  min_memory_gb?: number
  min_gpu_memory_gb?: number
  priority?: number
  supports_reasoning?: boolean
  supports_function_call?: boolean
  max_context_length?: number
  param_scale?: number
  enabled?: boolean
  allow_external_call?: boolean
  endpoint?: string
  upstream_model?: string
  api_key_masked?: string
  child_models?: string[]
  routing_policy?: string
  pricing_tiers?: Array<{ max_input_tokens: number; input_price: number; output_price: number }>
  contributor_tiers?: Array<{ max_input_tokens: number; input_price: number; output_price: number }>
  tags?: string[]
  options?: Record<string, any>
  created_at?: string
}

const vendorLabelMap: Record<string, string> = {
  deepnode: 'DeepNode',
  provider: 'Provider',
  hybrid: 'Hybrid',
}

const vendorOptions = [
  { label: 'DeepNode', value: 'deepnode' },
  { label: 'Provider', value: 'provider' },
  { label: 'Hybrid', value: 'hybrid' },
]

const providerOptions = [
  { label: 'OpenAI Compatible', value: 'openai' },
  { label: 'Anthropic Proxy', value: 'anthropic' },
  { label: 'Gemini Proxy', value: 'gemini' },
  { label: 'Qianfan Proxy', value: 'qianfan' },
  { label: 'Qwen Proxy', value: 'qwen' },
  { label: 'Custom', value: 'custom' },
]

const loading = ref(true)
const keyword = ref('')
const models = ref<ModelRow[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
})

const columns = [
  { colKey: 'id', title: 'ID', width: 70 },
  { colKey: 'model_name', title: '模型名称', width: 220 },
  { colKey: 'vendor_type', title: '来源', width: 110, cell: 'vendor_type' },
  { colKey: 'provider_type', title: 'Provider', width: 120, cell: 'provider_type' },
  { colKey: 'route_target', title: '路由配置', minWidth: 260, cell: 'route_target' },
  { colKey: 'api_key_masked', title: 'API Key', width: 160, cell: 'api_key_masked' },
  { colKey: 'param_scale', title: '参数量级', width: 100, cell: 'param_scale' },
  { colKey: 'supports_reasoning', title: 'Reasoning', width: 100, cell: 'supports_reasoning' },
  { colKey: 'supports_function_call', title: 'FnCall', width: 90, cell: 'supports_function_call' },
  { colKey: 'max_context_length', title: '最大上下文', width: 110, cell: 'max_context_length' },
  { colKey: 'supported_engines', title: '支持引擎', width: 160, cell: 'supported_engines' },
  { colKey: 'priority', title: '优先级', width: 90 },
  { colKey: 'pricing', title: '计费', width: 160, cell: 'pricing' },
  { colKey: 'enabled', title: '状态', width: 80, cell: 'enabled' },
  { colKey: 'allow_external_call', title: '外部调用', width: 100, cell: 'allow_external_call' },
  { colKey: 'created_at', title: '创建时间', width: 170, cell: 'created_at' },
  { colKey: 'op', title: '操作', width: 240, cell: 'op', fixed: 'right' },
]

async function fetchModels() {
  loading.value = true
  try {
    const res = await getModels({
      keyword: keyword.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    const data = res?.data?.data || {}
    models.value = data.items || []
    pagination.total = data.total || 0
  } catch {
    models.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

function onPageChange(pageInfo: { current: number; pageSize: number }) {
  pagination.current = pageInfo.current
  pagination.pageSize = pageInfo.pageSize
  fetchModels()
}

const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref(0)

const defaultForm = {
  model_name: '',
  vendor_type: 'deepnode',
  provider_type: 'openai',
  repo_id: '',
  model_base_dir: '',
  engine: '',
  supported_engines: '',
  min_memory_gb: 0,
  min_gpu_memory_gb: 0,
  priority: 0,
  supports_reasoning: false,
  supports_function_call: false,
  max_context_length: 0,
  param_scale: 0,
  allow_external_call: true,
  endpoint: '',
  upstream_model: '',
  api_key: '',
  api_key_masked: '',
  child_models: [] as string[],
  routing_policy: '',
  pricing_tiers: [] as Array<{ max_input_tokens: number; input_price: number; output_price: number }>,
  contributor_tiers: [] as Array<{ max_input_tokens: number; input_price: number; output_price: number }>,
  tags: [] as string[],
  options: '',
}

const formData = reactive({ ...defaultForm })

const isHybrid = computed(() => formData.vendor_type === 'hybrid')
const requiresDeepNode = computed(() => formData.vendor_type === 'deepnode')
const requiresProvider = computed(() => formData.vendor_type === 'provider')
const providerAPIKeyPlaceholder = computed(() => formData.api_key_masked || '输入新的 provider api key')

// ── Help doc dialog ──
const helpVisible = ref(false)
const helpScrollTo = ref('')

// Pre-rendered help doc HTML (inline to avoid build-time markdown dependency)
const helpHtml = computed(() => `
<h2 id="routing">1. Hybrid Routing Policy</h2>

<h3>How It Works</h3>
<p>A Hybrid model is a <b>virtual entry point</b> — it does not serve inference itself. When a request arrives:</p>
<ol>
  <li><b>Feature extraction</b>: Parse request to compute routing features (input tokens, tool count, reasoning flag)</li>
  <li><b>Rule matching</b>: Evaluate rules top-down, first match wins</li>
  <li><b>Target selection</b>: Pick candidate via round-robin from matched rule's targets</li>
  <li><b>Fallback</b>: If selected child fails before response starts, try next candidate</li>
</ol>

<h3>YAML Schema</h3>
<pre><code>load_balance: round-robin

rules:
  - name: "short_requests"
    condition:
      max_input_tokens: 2000    # input tokens ≤ 2000
      has_tools: false          # no tool calls
    targets:
      - "local-small-model"

  - name: "tool_calling"
    condition:
      has_tools: true
    targets:
      - "gpt-4o-proxy"

default_targets:
  - "local-small-model"
  - "gpt-4o-proxy"</code></pre>

<h3>Condition Fields</h3>
<table>
  <tr><th>Field</th><th>Type</th><th>Description</th></tr>
  <tr><td><code>max_input_tokens</code></td><td>int</td><td>Match if estimated input tokens ≤ value</td></tr>
  <tr><td><code>min_input_tokens</code></td><td>int</td><td>Match if estimated input tokens ≥ value</td></tr>
  <tr><td><code>has_tools</code></td><td>bool</td><td>Match if request contains tool definitions</td></tr>
  <tr><td><code>has_reasoning</code></td><td>bool</td><td>Match if enable_thinking is true</td></tr>
  <tr><td><code>max_tool_count</code></td><td>int</td><td>Match if tool count ≤ value</td></tr>
  <tr><td><code>min_tool_count</code></td><td>int</td><td>Match if tool count ≥ value</td></tr>
</table>
<p><b>Note</b>: All specified conditions must match (AND logic). Omitted fields are not checked. Token estimation uses ~4 chars per token heuristic.</p>

<h3>Fallback Order</h3>
<ol>
  <li>Models from matched rule's <code>targets</code> (round-robin rotated)</li>
  <li>All remaining child models not in matched targets</li>
</ol>
<p>Leave routing policy empty → all child models are load-balanced via round-robin with automatic fallback.</p>

<hr/>

<h2 id="billing">2. Billing Strategy</h2>

<h3>Billing Roles by Model Type</h3>
<table>
  <tr><th>Model Type</th><th>Consumer (pricing_tiers)</th><th>Contributor (contributor_tiers)</th></tr>
  <tr><td><b>DeepNode</b></td><td>✅ Configure here</td><td>✅ Configure here</td></tr>
  <tr><td><b>Provider</b></td><td>✅ Configure here</td><td>❌ Not applicable</td></tr>
  <tr><td><b>Hybrid</b></td><td>Dynamic (from child model)</td><td>❌ Derived from resolved child</td></tr>
</table>

<h3>How Hybrid Billing Works</h3>
<ul>
  <li><b>Consumer cost</b>: Dynamically calculated from the resolved child model's <code>pricing_tiers</code> at request time</li>
  <li><b>Contributor earning</b>: Uses the resolved child model's <code>contributor_tiers</code></li>
  <li>If child is DeepNode → uses that DeepNode's contributor tiers</li>
  <li>If child is Provider → contributor earning = ¥0</li>
  <li>No need to configure pricing_tiers on Hybrid — it is derived from children</li>
</ul>

<h3>Tiered Pricing</h3>
<p>Tiers are matched by input token count (first match wins):</p>
<pre><code>Tier 1: ≤4K tokens  → input ¥1.00/M, output ¥2.00/M
Tier 2: ≤32K tokens → input ¥2.00/M, output ¥4.00/M
Tier 3: unlimited   → input ¥4.00/M, output ¥8.00/M</code></pre>
<p><code>max_input_tokens = 0</code> means unlimited (catch-all tier, should be last). Leave empty = free model.</p>

<h3>Cost Formula</h3>
<pre><code>cost = prompt_tokens × input_price / 1,000,000
     + completion_tokens × output_price / 1,000,000</code></pre>
<p>All amounts stored as <code>DECIMAL(20,10)</code> — precise to 10 decimal places, no rounding.</p>

<hr/>

<h3>Common Mistakes</h3>
<ul>
  <li>❌ Setting contributor_tiers on Hybrid → ignored; contributor billing comes from child model</li>
  <li>❌ Routing targets not in child_models → validation error</li>
  <li>❌ Only 1 child model → Hybrid requires at least 2</li>
  <li>❌ Recursive Hybrid (child is Hybrid) → not allowed</li>
</ul>
`)

// Child model options for hybrid model selector.
interface ChildModelOption {
  label: string
  value: string
  vendor_type: string
  param_scale: number
  max_context_length: number
  tags: string[]
}
const loadingChildModels = ref(false)
const childModelOptions = ref<ChildModelOption[]>([])

async function fetchChildModelOptions() {
  loadingChildModels.value = true
  try {
    const res = await getEnabledModels()
    const items: ModelRow[] = res?.data?.data || []
    // Only show deepnode/provider models as candidates (exclude hybrid).
    childModelOptions.value = items
      .filter((m) => m.vendor_type !== 'hybrid')
      .map((m) => ({
        label: m.model_name,
        value: m.model_name,
        vendor_type: m.vendor_type || 'deepnode',
        param_scale: m.param_scale || 0,
        max_context_length: m.max_context_length || 0,
        tags: m.tags || [],
      }))
  } catch {
    childModelOptions.value = []
  } finally {
    loadingChildModels.value = false
  }
}

function resetForm() {
  Object.assign(formData, {
    ...defaultForm,
    child_models: [] as string[],
    pricing_tiers: [] as Array<{ max_input_tokens: number; input_price: number; output_price: number }>,
    contributor_tiers: [] as Array<{ max_input_tokens: number; input_price: number; output_price: number }>,
    tags: [] as string[],
  })
}

function openCreateDialog() {
  isEdit.value = false
  editingId.value = 0
  resetForm()
  fetchChildModelOptions()
  dialogVisible.value = true
}

function openEditDialog(row: ModelRow) {
  isEdit.value = true
  editingId.value = row.id
  formData.model_name = row.model_name || ''
  formData.vendor_type = row.vendor_type || 'deepnode'
  formData.provider_type = row.provider_type || 'openai'
  formData.repo_id = row.repo_id || ''
  formData.model_base_dir = row.model_base_dir || ''
  formData.engine = row.engine || ''
  formData.supported_engines = (row.supported_engines || []).join(',')
  formData.min_memory_gb = row.min_memory_gb || 0
  formData.min_gpu_memory_gb = row.min_gpu_memory_gb || 0
  formData.priority = row.priority || 0
  formData.supports_reasoning = row.supports_reasoning || false
  formData.supports_function_call = row.supports_function_call || false
  formData.max_context_length = row.max_context_length || 0
  formData.param_scale = row.param_scale || 0
  formData.allow_external_call = row.allow_external_call !== false
  formData.endpoint = row.endpoint || ''
  formData.upstream_model = row.upstream_model || ''
  formData.api_key = ''
  formData.api_key_masked = row.api_key_masked || ''
  formData.child_models = row.child_models || []
  formData.routing_policy = row.routing_policy || ''
  formData.pricing_tiers = (row.pricing_tiers || []).map((t) => ({ ...t }))
  formData.contributor_tiers = (row.contributor_tiers || []).map((t) => ({ ...t }))
  formData.options = row.options ? JSON.stringify(row.options, null, 2) : ''
  formData.tags = row.tags || []
  fetchChildModelOptions()
  dialogVisible.value = true
}

function parseOptions(): Record<string, any> | undefined {
  if (!formData.options.trim()) return undefined
  return JSON.parse(formData.options)
}

function buildPayload() {
  const supportedEngines = formData.supported_engines
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const payload: Record<string, any> = {
    model_name: formData.model_name.trim(),
    vendor_type: formData.vendor_type,
    supports_reasoning: formData.supports_reasoning,
    supports_function_call: formData.supports_function_call,
    max_context_length: formData.max_context_length,
    param_scale: formData.param_scale,
    pricing_tiers: formData.pricing_tiers.length ? formData.pricing_tiers : [],
    tags: formData.tags.length ? formData.tags : [],
    allow_external_call: formData.allow_external_call,
    options: parseOptions(),
  }

  if (isHybrid.value) {
    payload.child_models = formData.child_models
    if (formData.routing_policy.trim()) {
      payload.routing_policy = formData.routing_policy.trim()
    }
  } else if (requiresDeepNode.value) {
    payload.repo_id = formData.repo_id.trim()
    payload.model_base_dir = formData.model_base_dir.trim()
    payload.engine = formData.engine.trim()
    payload.supported_engines = supportedEngines.length ? supportedEngines : undefined
    payload.min_memory_gb = formData.min_memory_gb
    payload.min_gpu_memory_gb = formData.min_gpu_memory_gb
    payload.priority = formData.priority
    payload.contributor_tiers = formData.contributor_tiers.length ? formData.contributor_tiers : []
  } else if (requiresProvider.value) {
    payload.provider_type = formData.provider_type.trim() || 'custom'
    payload.endpoint = formData.endpoint.trim()
    payload.upstream_model = formData.upstream_model.trim()
    if (formData.api_key.trim()) {
      payload.api_key = formData.api_key.trim()
    }
  }

  return payload
}

function validateForm() {
  if (!formData.model_name.trim()) {
    return '模型名称不能为空'
  }
  if (isHybrid.value) {
    if (!formData.child_models || formData.child_models.length < 2) {
      return 'Hybrid 模型至少需要选择 2 个子模型'
    }
    return ''
  }
  if (requiresDeepNode.value && !formData.repo_id.trim()) {
    return 'DeepNode 模型必须填写 Repo ID'
  }
  if (requiresProvider.value && !formData.endpoint.trim()) {
    return 'Provider 模型必须填写 Endpoint'
  }
  if (requiresProvider.value && !formData.upstream_model.trim()) {
    return 'Provider 模型必须填写上游模型名'
  }
  if (requiresProvider.value && !isEdit.value && !formData.api_key.trim()) {
    return '创建 Provider 模型时必须填写 API Key'
  }
  return ''
}

function extractErrorMessage(error: any, fallback: string) {
  return error?.response?.data?.message || fallback
}

async function handleSave() {
  const validationMessage = validateForm()
  if (validationMessage) {
    MessagePlugin.warning(validationMessage)
    return
  }

  let payload: Record<string, any>
  try {
    payload = buildPayload()
  } catch {
    MessagePlugin.warning('额外参数 JSON 格式不正确')
    return
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateModel(editingId.value, payload)
      MessagePlugin.success('更新成功')
    } else {
      await createModel(payload)
      MessagePlugin.success('创建成功')
    }
    dialogVisible.value = false
    fetchModels()
  } catch (error) {
    MessagePlugin.error(extractErrorMessage(error, '操作失败'))
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: ModelRow) {
  try {
    await updateModel(row.id, { enabled: !row.enabled })
    MessagePlugin.success(row.enabled ? '已禁用' : '已启用')
    fetchModels()
  } catch (error) {
    MessagePlugin.error(extractErrorMessage(error, '操作失败'))
  }
}

async function toggleExternalCall(row: ModelRow) {
  try {
    await updateModel(row.id, { allow_external_call: !row.allow_external_call })
    MessagePlugin.success(row.allow_external_call ? '已禁止外部调用' : '已允许外部调用')
    fetchModels()
  } catch (error) {
    MessagePlugin.error(extractErrorMessage(error, '操作失败'))
  }
}

async function handleDelete(id: number) {
  try {
    await deleteModel(id)
    MessagePlugin.success('已删除')
    fetchModels()
  } catch (error) {
    MessagePlugin.error(extractErrorMessage(error, '删除失败'))
  }
}

// ── Pricing tier manipulation ──

function addPricingTier() {
  formData.pricing_tiers.push({ max_input_tokens: 0, input_price: 0, output_price: 0 })
}

function removePricingTier(idx: number) {
  formData.pricing_tiers.splice(idx, 1)
}

function addContributorTier() {
  formData.contributor_tiers.push({ max_input_tokens: 0, input_price: 0, output_price: 0 })
}

function removeContributorTier(idx: number) {
  formData.contributor_tiers.splice(idx, 1)
}

function formatEngines(engines?: string[]) {
  if (!engines || engines.length === 0) return '-'
  return engines.join(', ')
}

function formatContextLength(value: number) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `${(value / 1000).toFixed(0)}K`
  return String(value)
}

function formatTime(value?: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

function vendorTheme(vendorType: string) {
  if (vendorType === 'provider') return 'warning'
  if (vendorType === 'hybrid') return 'primary'
  return 'success'
}

function vendorTagClass(vendorType: string): string {
  if (vendorType === 'provider') return 'bg-orange-50 text-orange-600'
  if (vendorType === 'hybrid') return 'bg-red-50 text-red-500'
  return 'bg-green-50 text-green-600'
}

onMounted(() => fetchModels())
</script>

<style scoped>
.help-doc-content :deep(h2) {
  font-size: 1.25rem;
  font-weight: 700;
  margin: 1.5rem 0 0.75rem;
  padding-bottom: 0.375rem;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.help-doc-content :deep(h3) {
  font-size: 1rem;
  font-weight: 600;
  margin: 1rem 0 0.5rem;
}
.help-doc-content :deep(p) {
  margin: 0.5rem 0;
  line-height: 1.6;
}
.help-doc-content :deep(pre) {
  background: rgba(0,0,0,0.15);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  overflow-x: auto;
  font-size: 0.8rem;
  line-height: 1.5;
  margin: 0.5rem 0;
}
.help-doc-content :deep(code) {
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 0.85em;
  background: rgba(0,0,0,0.1);
  padding: 0.1em 0.3em;
  border-radius: 3px;
}
.help-doc-content :deep(pre code) {
  background: none;
  padding: 0;
}
.help-doc-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
  font-size: 0.85rem;
}
.help-doc-content :deep(th),
.help-doc-content :deep(td) {
  padding: 0.4rem 0.6rem;
  border: 1px solid rgba(255,255,255,0.08);
  text-align: left;
}
.help-doc-content :deep(th) {
  font-weight: 600;
  background: rgba(0,0,0,0.1);
}
.help-doc-content :deep(ol),
.help-doc-content :deep(ul) {
  padding-left: 1.5rem;
  margin: 0.4rem 0;
}
.help-doc-content :deep(li) {
  margin: 0.25rem 0;
  line-height: 1.5;
}
.help-doc-content :deep(hr) {
  border: none;
  border-top: 1px solid rgba(255,255,255,0.08);
  margin: 1.5rem 0;
}
</style>
