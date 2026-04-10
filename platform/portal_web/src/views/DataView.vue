<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-6xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">{{ $t('data.title') }}</h1>

      <!-- 未登录提示 -->
      <div v-if="!authStore.isLoggedIn" class="text-center py-20 text-dp-muted">
        {{ $t('data.login_required') }}
      </div>

      <template v-else>
        <!-- 汇总卡片 -->
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div class="bg-white rounded-xl p-5 border border-slate-100 shadow-sm">
            <div class="text-xs text-dp-muted mb-1">{{ $t('data.summary_contributed') }}</div>
            <div class="text-2xl font-bold text-dp-title">{{ formatTokens(summary.contributed_tokens) }}</div>
          </div>
          <div class="bg-white rounded-xl p-5 border border-slate-100 shadow-sm">
            <div class="text-xs text-dp-muted mb-1">{{ $t('data.summary_consumed') }}</div>
            <div class="text-2xl font-bold text-dp-title">{{ formatTokens(summary.consumed_tokens) }}</div>
          </div>
          <div class="bg-white rounded-xl p-5 border border-slate-100 shadow-sm">
            <div class="text-xs text-dp-muted mb-1">{{ $t('data.summary_requests') }}</div>
            <div class="text-2xl font-bold text-dp-title">{{ formatNum(summary.contributed_requests + summary.consumed_requests) }}</div>
          </div>
        </div>

        <!-- Tab 切换 -->
        <div class="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
          <div class="flex border-b border-slate-100">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="flex-1 py-3 text-sm font-medium text-center transition-colors relative"
              :class="activeTab === tab.key
                ? 'text-dp-blue'
                : 'text-dp-muted hover:text-dp-title'"
              @click="switchTab(tab.key as 'contribution' | 'consumption' | 'billing')"
            >
              {{ tab.label }}
              <span
                v-if="activeTab === tab.key"
                class="absolute bottom-0 left-1/4 right-1/4 h-0.5 bg-dp-blue rounded-full"
              />
            </button>
          </div>

          <!-- ═══ Billing Tab: Tiered Pricing Table + Hybrid Price Range ═══ -->
          <div v-if="activeTab === 'billing'" class="px-6 py-6">
            <div v-if="billingModels.length === 0" class="py-12 text-center text-dp-muted">
              {{ $t('data.billing_empty') }}
            </div>
            <div v-else class="overflow-x-auto">
              <table class="w-full text-sm border-collapse">
                <thead>
                  <tr class="bg-slate-50 text-dp-muted text-xs">
                    <th class="py-3 px-4 text-left font-medium border-b border-slate-200">{{ $t('data.billing_col_model') }}</th>
                    <th class="py-3 px-4 text-left font-medium border-b border-slate-200">{{ $t('data.billing_col_input_tokens') }}</th>
                    <th class="py-3 px-4 text-right font-medium border-b border-slate-200">{{ $t('data.billing_col_input_price') }}</th>
                    <th class="py-3 px-4 text-right font-medium border-b border-slate-200">{{ $t('data.billing_col_output_price') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <template v-for="model in billingModels" :key="model.model_name">
                    <!-- Hybrid model: display dynamic price range -->
                    <tr
                      v-if="model.vendor_type === 'hybrid' && model.price_range"
                      class="border-b border-slate-100 hover:bg-slate-50/50 transition-colors"
                    >
                      <td class="py-3 px-4 text-dp-title font-medium align-top border-r border-slate-100">
                        <div class="flex items-center gap-1.5">
                          {{ model.model_name }}
                          <span class="inline-block px-1.5 py-0.5 text-[10px] font-medium bg-blue-50 text-blue-600 rounded">Hybrid</span>
                        </div>
                        <div v-if="model.price_range.child_models?.length" class="text-xs text-dp-muted mt-0.5">
                          {{ $t('data.billing_hybrid_children', { count: model.price_range.child_models.length }) }}
                        </div>
                      </td>
                      <td class="py-3 px-4 text-dp-muted text-xs italic">
                        {{ $t('data.billing_hybrid_dynamic') }}
                      </td>
                      <td class="py-3 px-4 text-right text-dp-body tabular-nums font-mono">
                        {{ formatPriceRange(model.price_range.min_input_price, model.price_range.max_input_price) }}
                      </td>
                      <td class="py-3 px-4 text-right text-dp-body tabular-nums font-mono">
                        {{ formatPriceRange(model.price_range.min_output_price, model.price_range.max_output_price) }}
                      </td>
                    </tr>

                    <!-- Standard model: display tiered pricing rows -->
                    <tr
                      v-else
                      v-for="(tier, tierIdx) in model.pricing_tiers"
                      :key="`${model.model_name}-${tierIdx}`"
                      class="border-b border-slate-100 hover:bg-slate-50/50 transition-colors"
                    >
                      <td
                        v-if="tierIdx === 0"
                        :rowspan="model.pricing_tiers.length"
                        class="py-3 px-4 text-dp-title font-medium align-top border-r border-slate-100"
                      >
                        <div>{{ model.model_name }}</div>
                        <div v-if="model.param_scale" class="text-xs text-dp-muted mt-0.5">
                          {{ $t('data.billing_params', { scale: model.param_scale }) }}
                        </div>
                        <div v-if="model.max_context_length" class="text-xs text-dp-muted">
                          {{ $t('data.billing_context', { len: formatContextLength(model.max_context_length) }) }}
                        </div>
                      </td>
                      <td class="py-3 px-4 text-dp-body">
                        {{ formatTierRange(model.pricing_tiers, tierIdx) }}
                      </td>
                      <td class="py-3 px-4 text-right text-dp-body tabular-nums font-mono">
                        {{ tier.input_price }} {{ $t('data.billing_unit') }}
                      </td>
                      <td class="py-3 px-4 text-right text-dp-body tabular-nums font-mono">
                        {{ tier.output_price }} {{ $t('data.billing_unit') }}
                      </td>
                    </tr>
                  </template>
                </tbody>
              </table>
              <div class="mt-4 text-xs text-dp-muted leading-relaxed">
                <p>{{ $t('data.billing_note1') }}</p>
                <p>{{ $t('data.billing_note2') }}</p>
                <p>{{ $t('data.billing_note3') }}</p>
              </div>
            </div>
          </div>

          <!-- ═══ Usage Tabs: Filter + Table + Pagination ═══ -->
          <template v-if="activeTab !== 'billing'">

          <!-- 筛选栏 -->
          <div class="px-6 py-4 border-b border-slate-50 flex flex-wrap gap-3 items-center">
            <!-- API Key 筛选（仅消耗 tab 显示） -->
            <select
              v-if="activeTab === 'consumption'"
              v-model="filterAPIKeyID"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            >
              <option value="">{{ $t('data.filter_apikey') }}: {{ $t('data.filter_all') }}</option>
              <option v-for="k in apiKeyList" :key="k.id" :value="String(k.id)">{{ k.name }} ({{ k.key_prefix }}...)</option>
            </select>
            <select
              v-model="filterModel"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            >
              <option value="">{{ $t('data.filter_model') }}: {{ $t('data.filter_all') }}</option>
              <option v-for="m in modelList" :key="m" :value="m">{{ m }}</option>
            </select>
            <input
              v-model="filterStartDate"
              type="date"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <span class="text-dp-muted text-xs">—</span>
            <input
              v-model="filterEndDate"
              type="date"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <button
              class="px-4 py-1.5 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors"
              @click="fetchData"
            >
              {{ $t('data.search') }}
            </button>
          </div>

          <!-- 数据表格 -->
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-slate-50 text-dp-muted text-xs">
                  <th class="py-3 px-4 text-left font-medium">{{ $t('data.col_date') }}</th>
                  <th v-if="activeTab === 'contribution'" class="py-3 px-4 text-left font-medium">{{ $t('data.col_device') }}</th>
                  <th v-if="activeTab === 'consumption'" class="py-3 px-4 text-left font-medium">{{ $t('data.col_apikey') }}</th>
                  <th class="py-3 px-4 text-left font-medium">{{ $t('data.col_model') }}</th>
                  <th class="py-3 px-4 text-right font-medium">{{ $t('data.col_prompt') }}</th>
                  <th class="py-3 px-4 text-right font-medium">{{ $t('data.col_completion') }}</th>
                  <th class="py-3 px-4 text-right font-medium">{{ $t('data.col_total') }}</th>
                  <th class="py-3 px-4 text-right font-medium">{{ $t('data.col_requests') }}</th>
                  <th v-if="activeTab === 'consumption'" class="py-3 px-4 text-right font-medium">{{ $t('data.col_cost') }}</th>
                  <th v-if="activeTab === 'contribution'" class="py-3 px-4 text-right font-medium">{{ $t('data.col_earning') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="rows.length === 0">
                  <td :colspan="activeTab === 'contribution' ? 8 : 8" class="py-12 text-center text-dp-muted">{{ $t('data.empty') }}</td>
                </tr>
                <tr
                  v-for="(row, idx) in rows"
                  :key="idx"
                  class="border-t border-slate-50 hover:bg-slate-50/50 transition-colors"
                >
                  <td class="py-3 px-4 text-dp-body">{{ row.usage_date }}</td>
                  <td v-if="activeTab === 'contribution'" class="py-3 px-4 text-dp-body font-mono text-xs">{{ row.simei }}</td>
                  <td v-if="activeTab === 'consumption'" class="py-3 px-4 text-dp-body text-xs">
                    {{ row.api_key_name || '—' }}
                  </td>
                  <td class="py-3 px-4 text-dp-body">{{ row.model_name }}</td>
                  <td class="py-3 px-4 text-right text-dp-body tabular-nums">{{ formatNum(row.prompt_tokens) }}</td>
                  <td class="py-3 px-4 text-right text-dp-body tabular-nums">{{ formatNum(row.completion_tokens) }}</td>
                  <td class="py-3 px-4 text-right font-medium text-dp-title tabular-nums">{{ formatNum(row.total_tokens) }}</td>
                  <td class="py-3 px-4 text-right text-dp-body tabular-nums">{{ formatNum(row.request_count) }}</td>
                  <td v-if="activeTab === 'consumption'" class="py-3 px-4 text-right text-red-500 tabular-nums font-mono text-xs">{{ formatYuan(row.cost_yuan) }}</td>
                  <td v-if="activeTab === 'contribution'" class="py-3 px-4 text-right text-green-600 tabular-nums font-mono text-xs">{{ formatYuan(row.earning_yuan) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 分页 -->
          <div v-if="totalRows > pageSize" class="px-6 py-4 border-t border-slate-50 flex items-center justify-between">
            <span class="text-xs text-dp-muted">
              {{ totalRows }} {{ $t('data.records') }}
            </span>
            <div class="flex gap-1">
              <button
                v-for="p in totalPages"
                :key="p"
                class="w-8 h-8 rounded-lg text-xs font-medium transition-colors"
                :class="page === p
                  ? 'bg-dp-blue text-white'
                  : 'text-dp-muted hover:bg-slate-100'"
                @click="goPage(p)"
              >
                {{ p }}
              </button>
            </div>
          </div>

          </template><!-- end usage tabs -->
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getContribution, getConsumption, getUsageSummary } from '@/api/usage'
import { listAPIKeys, type APIKey } from '@/api/apikey'
import { getPublicModels, type PublicModel, type PricingTier, type PriceRange } from '@/api/model'

const { t } = useI18n()
const authStore = useAuthStore()

// Tab definition
const tabs = computed(() => [
  { key: 'contribution', label: t('data.tab_contribution') },
  { key: 'consumption', label: t('data.tab_consumption') },
  { key: 'billing', label: t('data.tab_billing') },
])
const activeTab = ref<'contribution' | 'consumption' | 'billing'>('contribution')

// 汇总数据
const summary = ref({
  contributed_tokens: 0,
  consumed_tokens: 0,
  contributed_requests: 0,
  consumed_requests: 0,
})

// 表格数据
interface UsageRow {
  usage_date: string
  user_id: number
  simei: string
  model_name: string
  api_key_id: number
  api_key_name: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  reasoning_tokens: number
  request_count: number
  cost_yuan: number
  earning_yuan: number
}
const rows = ref<UsageRow[]>([])
const totalRows = ref(0)
const page = ref(1)
const pageSize = 20

// 筛选
const filterModel = ref('')
const filterAPIKeyID = ref('')
const filterStartDate = ref('')
const filterEndDate = ref('')
const modelList = ref<string[]>([])
const apiKeyList = ref<APIKey[]>([])

const totalPages = computed(() => Math.max(1, Math.ceil(totalRows.value / pageSize)))

function sanitizeUsageRows(items: unknown[]): UsageRow[] {
  return items.map((item) => {
    const record = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>
    return {
      usage_date: String(record.usage_date || ''),
      user_id: Number(record.user_id || 0),
      simei: String(record.simei || ''),
      model_name: String(record.model_name || ''),
      api_key_id: Number(record.api_key_id || 0),
      api_key_name: String(record.api_key_name || ''),
      prompt_tokens: Number(record.prompt_tokens || 0),
      completion_tokens: Number(record.completion_tokens || 0),
      total_tokens: Number(record.total_tokens || 0),
      reasoning_tokens: Number(record.reasoning_tokens || 0),
      request_count: Number(record.request_count || 0),
      cost_yuan: Number(record.cost_yuan || 0),
      earning_yuan: Number(record.earning_yuan || 0),
    }
  })
}

function extractModelNames(items: UsageRow[]): string[] {
  return [...new Set(items.map(item => item.model_name).filter(Boolean))].sort((left, right) => left.localeCompare(right))
}

function switchTab(tab: 'contribution' | 'consumption' | 'billing') {
  activeTab.value = tab
  page.value = 1
  filterModel.value = ''
  filterAPIKeyID.value = ''
  if (tab === 'billing') {
    fetchModels()
  } else {
    fetchData()
  }
}

function goPage(p: number) {
  page.value = p
  fetchData()
}

async function fetchData() {
  if (!authStore.isLoggedIn) return

  const params: Record<string, string> = {
    page: String(page.value),
    page_size: String(pageSize),
  }
  if (filterModel.value) params.model = filterModel.value
  if (filterStartDate.value) params.start_date = filterStartDate.value
  if (filterEndDate.value) params.end_date = filterEndDate.value

  // API 消耗 tab：支持按 API Key ID 筛选
  if (activeTab.value === 'consumption' && filterAPIKeyID.value) {
    params.api_key_id = filterAPIKeyID.value
  }

  try {
    const api = activeTab.value === 'contribution' ? getContribution : getConsumption
    const res = await api(params)
    const data = res.data?.data || {}
    rows.value = sanitizeUsageRows(Array.isArray(data.items) ? data.items : [])
    totalRows.value = Number(data.total || 0)
    modelList.value = extractModelNames(rows.value)
  } catch {
    rows.value = []
    totalRows.value = 0
    modelList.value = []
  }
}

async function fetchSummary() {
  if (!authStore.isLoggedIn) return
  try {
    const res = await getUsageSummary()
    const data = res.data?.data || {}
    summary.value = {
      contributed_tokens: data.contributed_tokens || 0,
      consumed_tokens: data.consumed_tokens || 0,
      contributed_requests: data.contributed_requests || 0,
      consumed_requests: data.consumed_requests || 0,
    }
  } catch {
    // 静默
  }
}

/** 获取用户的 API Key 列表（用于筛选下拉框） */
async function fetchAPIKeys() {
  if (!authStore.isLoggedIn) return
  try {
    const res = await listAPIKeys()
    apiKeyList.value = res.data?.data || []
  } catch {
    apiKeyList.value = []
  }
}

// Billing tab: model pricing data
const billingModels = ref<PublicModel[]>([])

async function fetchModels() {
  try {
    const res = await getPublicModels()
    const data = res.data?.data
    // Include models with pricing_tiers (standard) or price_range (hybrid dynamic pricing).
    billingModels.value = Array.isArray(data)
      ? data.filter(m => m.pricing_tiers?.length > 0 || m.price_range)
      : []
  } catch {
    billingModels.value = []
  }
}

/** Format token threshold for billing table display (e.g. 32768 → "32K") */
function formatContextLength(tokens: number): string {
  if (!tokens) return '∞'
  if (tokens >= 1_000_000) return (tokens / 1_000_000).toFixed(0) + 'M'
  if (tokens >= 1_000) return (tokens / 1_000).toFixed(0) + 'K'
  return String(tokens)
}

/** Format tier range string, e.g. "0 < Token ≤ 32K" */
function formatTierRange(tiers: PricingTier[], idx: number): string {
  const tier = tiers[idx]
  const prevMax = idx > 0 ? tiers[idx - 1].max_input_tokens : 0
  const lower = prevMax > 0 ? formatContextLength(prevMax) : '0'
  const upper = tier.max_input_tokens > 0 ? formatContextLength(tier.max_input_tokens) : '∞'
  return `${lower} < Token ≤ ${upper}`
}

/** Format hybrid price range: "1.00 ~ 4.00 元" or "1.00 元" when min === max */
function formatPriceRange(min: number, max: number): string {
  const unit = t('data.billing_unit')
  if (min === max) return `${min} ${unit}`
  return `${min} ~ ${max} ${unit}`
}

/** Format large numbers with locale separators */
function formatNum(n: number): string {
  if (!n) return '0'
  return n.toLocaleString()
}

/** Format yuan with up to 10 decimal places, trimming trailing zeros */
function formatYuan(yuan: number): string {
  if (!yuan) return '0'
  // Use fixed 10 decimal places then strip trailing zeros
  const s = yuan.toFixed(10).replace(/0+$/, '').replace(/\.$/, '')
  return '¥' + s
}

/** 格式化 token 数（K/M/B） */
function formatTokens(n: number): string {
  if (!n) return '0'
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

onMounted(() => {
  if (authStore.isLoggedIn) {
    fetchSummary()
    fetchData()
    fetchAPIKeys()
  }
})
</script>
