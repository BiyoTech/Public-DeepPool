<template>
  <div class="endpoints-view space-y-4">
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <t-input
          v-model="keyword"
          placeholder="Search by name / upstream model / URL"
          clearable
          class="w-96"
          @enter="fetchEndpoints"
          @clear="fetchEndpoints"
        >
          <template #prefix-icon><SearchIcon /></template>
        </t-input>
        <t-button theme="primary" @click="fetchEndpoints">Search</t-button>
      </div>
      <t-button theme="primary" @click="openCreateDialog">
        <template #icon><AddIcon /></template>
        New Endpoint
      </t-button>
    </div>

    <div class="bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <t-table
        :data="endpoints"
        :columns="columns"
        :loading="loading"
        row-key="id"
        :hover="true"
        :stripe="true"
        size="medium"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #model_family="{ row }">
          <t-tag theme="warning" variant="light" size="small">{{ row.model_family || '-' }}</t-tag>
        </template>

        <template #endpoint_url="{ row }">
          <span class="text-dp-text-2 text-xs font-mono max-w-[200px] truncate block">{{ row.endpoint_url }}</span>
        </template>

        <template #api_key_masked="{ row }">
          <span class="text-dp-text-2 text-xs font-mono">{{ row.api_key_masked || '-' }}</span>
        </template>

        <template #price_level="{ row }">
          <div class="flex items-center gap-0.5">
            <span v-for="i in 5" :key="i" class="text-xs" :class="i <= row.price_level ? 'text-yellow-400' : 'text-gray-600'">★</span>
          </div>
        </template>

        <template #enabled="{ row }">
          <t-tag v-if="row.enabled" theme="success" variant="light" size="small">Enabled</t-tag>
          <t-tag v-else theme="default" variant="light" size="small">Disabled</t-tag>
        </template>

        <template #created_at="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatTime(row.created_at) }}</span>
        </template>

        <template #op="{ row }">
          <div class="flex items-center gap-2">
            <t-button variant="text" theme="primary" size="small" @click="openEditDialog(row)">Edit</t-button>
            <t-button variant="text" theme="primary" size="small" @click="openTestDialog(row)">Test</t-button>
            <t-button
              variant="text"
              :theme="row.enabled ? 'warning' : 'success'"
              size="small"
              @click="toggleEnabled(row)"
            >
              {{ row.enabled ? 'Disable' : 'Enable' }}
            </t-button>
            <t-popconfirm content="Confirm delete this endpoint?" @confirm="handleDelete(row.id)">
              <t-button variant="text" theme="danger" size="small">Delete</t-button>
            </t-popconfirm>
          </div>
        </template>
      </t-table>
    </div>

    <!-- Create/Edit Dialog -->
    <t-dialog
      v-model:visible="dialogVisible"
      :header="isEdit ? 'Edit Endpoint' : 'New Endpoint'"
      :confirm-btn="{ loading: saving }"
      width="640px"
      @confirm="handleSave"
    >
      <t-form :data="formData" label-width="140px" class="mt-4">
        <t-form-item label="Name" required>
          <t-input v-model="formData.name" placeholder="Unique endpoint name, e.g. openrouter-gpt4o" />
        </t-form-item>

        <t-form-item label="Model Family" required>
          <t-select v-model="formData.model_family" :options="modelFamilyOptions" />
        </t-form-item>

        <t-form-item label="Upstream Model" required>
          <t-input v-model="formData.upstream_model" placeholder="e.g. gpt-4o, claude-sonnet-4-20250514" />
        </t-form-item>

        <t-form-item label="Endpoint URL" required>
          <t-input v-model="formData.endpoint_url" placeholder="e.g. https://openrouter.ai/api/v1" />
        </t-form-item>

        <t-form-item label="API Key" :required="!isEdit">
          <t-input v-model="formData.api_key" type="password" :placeholder="isEdit ? 'Leave empty to keep current' : 'Enter API key'" />
        </t-form-item>

        <t-form-item label="Source" required>
          <t-select v-model="formData.source" :options="sourceOptions" />
        </t-form-item>

        <t-form-item label="RPM Limit">
          <t-input-number v-model="formData.rpm_limit" :min="0" :step="10" />
        </t-form-item>

        <t-form-item label="TPM Limit">
          <t-input-number v-model="formData.tpm_limit" :min="0" :step="10000" />
        </t-form-item>

        <t-form-item label="Price Level">
          <t-slider v-model="formData.price_level" :min="1" :max="5" :step="1" :marks="{ 1: '1 Cheap', 3: '3', 5: '5 Expensive' }" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Quick Test Dialog -->
    <t-drawer
      v-model:visible="testVisible"
      :header="`Test: ${testEndpoint?.name || ''}`"
      size="500px"
      placement="right"
    >
      <div class="flex flex-col h-full">
        <div class="flex-1 overflow-y-auto space-y-3 pb-4">
          <div v-for="(msg, idx) in testMessages" :key="idx" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
            <div class="max-w-[80%] rounded-lg px-3 py-2 text-sm" :class="msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-dp-bg-2 text-dp-text-1'">
              {{ msg.content }}
            </div>
          </div>
          <div v-if="testLoading" class="text-dp-text-3 text-sm">Generating...</div>
        </div>
        <div class="flex gap-2 pt-3 border-t border-white/5">
          <t-input v-model="testInput" placeholder="Type a message..." @enter="sendTestMessage" />
          <t-button theme="primary" :loading="testLoading" @click="sendTestMessage">Send</t-button>
        </div>
      </div>
    </t-drawer>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { SearchIcon, AddIcon } from 'tdesign-icons-vue-next'
import { MessagePlugin } from 'tdesign-vue-next'
import { getEndpoints, createEndpoint, updateEndpoint, deleteEndpoint } from '@/api/admin'
import http from '@/api/http'

interface EndpointRow {
  id: number
  name: string
  model_family: string
  upstream_model: string
  endpoint_url: string
  api_key_masked?: string
  source: string
  rpm_limit: number
  tpm_limit: number
  price_level: number
  enabled: boolean
  created_at?: string
}

const modelFamilyOptions = [
  { label: 'GPT (OpenAI)', value: 'gpt' },
  { label: 'Claude (Anthropic)', value: 'claude' },
  { label: 'Gemini (Google)', value: 'gemini' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Qwen (Alibaba)', value: 'qwen' },
  { label: 'Kimi (Moonshot)', value: 'kimi' },
  { label: 'GLM (Zhipu)', value: 'glm' },
  { label: 'Qianfan (Baidu)', value: 'qianfan' },
  { label: 'MiniMax', value: 'minimax' },
  { label: 'Gemma (Google)', value: 'gemma' },
  { label: 'LLaMA (Meta)', value: 'llama' },
  { label: 'Mistral', value: 'mistral' },
  { label: 'Custom / Other', value: 'custom' },
]

const sourceOptions = [
  { label: 'OpenAI', value: 'openai' },
  { label: 'Anthropic', value: 'anthropic' },
  { label: 'Google (Gemini)', value: 'google' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'Alibaba (通义千问)', value: 'alibaba' },
  { label: 'Baidu (百度千帆)', value: 'baidu' },
  { label: 'Tencent (腾讯混元)', value: 'tencent' },
  { label: 'Kimi (Moonshot)', value: 'kimi' },
  { label: 'Zhipu (智谱 GLM)', value: 'zhipu' },
  { label: 'MiniMax', value: 'minimax' },
  { label: 'Mistral', value: 'mistral' },
  { label: 'Cohere', value: 'cohere' },
  { label: 'OpenRouter', value: 'openrouter' },
  { label: 'Azure', value: 'azure' },
  { label: 'AWS Bedrock', value: 'aws' },
  { label: 'Databricks', value: 'databricks' },
  { label: 'Together AI', value: 'together' },
  { label: 'Groq', value: 'groq' },
  { label: 'SiliconFlow (硅基流动)', value: 'siliconflow' },
  { label: 'Custom', value: 'custom' },
]

const loading = ref(true)
const keyword = ref('')
const endpoints = ref<EndpointRow[]>([])

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
  { colKey: 'name', title: 'Name', width: 180 },
  { colKey: 'model_family', title: 'Model Family', width: 120, cell: 'model_family' },
  { colKey: 'upstream_model', title: 'Upstream Model', width: 180 },
  { colKey: 'endpoint_url', title: 'Endpoint URL', minWidth: 200, cell: 'endpoint_url' },
  { colKey: 'api_key_masked', title: 'API Key', width: 150, cell: 'api_key_masked' },
  { colKey: 'source', title: 'Source', width: 110 },
  { colKey: 'rpm_limit', title: 'RPM', width: 80 },
  { colKey: 'tpm_limit', title: 'TPM', width: 100 },
  { colKey: 'price_level', title: 'Price', width: 120, cell: 'price_level' },
  { colKey: 'enabled', title: 'Status', width: 90, cell: 'enabled' },
  { colKey: 'created_at', title: 'Created', width: 160, cell: 'created_at' },
  { colKey: 'op', title: 'Actions', width: 220, cell: 'op', fixed: 'right' },
]

async function fetchEndpoints() {
  loading.value = true
  try {
    const res = await getEndpoints({
      keyword: keyword.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    })
    const data = res?.data?.data || {}
    endpoints.value = data.items || []
    pagination.total = data.total || 0
  } catch {
    endpoints.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

function onPageChange(pageInfo: { current: number; pageSize: number }) {
  pagination.current = pageInfo.current
  pagination.pageSize = pageInfo.pageSize
  fetchEndpoints()
}

// ── Create/Edit Dialog ──
const dialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const editingId = ref(0)

const defaultForm = {
  name: '',
  model_family: 'gpt',
  upstream_model: '',
  endpoint_url: '',
  api_key: '',
  source: 'custom',
  rpm_limit: 60,
  tpm_limit: 100000,
  price_level: 3,
}

const formData = reactive({ ...defaultForm })

function openCreateDialog() {
  isEdit.value = false
  editingId.value = 0
  Object.assign(formData, { ...defaultForm })
  dialogVisible.value = true
}

function openEditDialog(row: EndpointRow) {
  isEdit.value = true
  editingId.value = row.id
  formData.name = row.name
  formData.model_family = row.model_family
  formData.upstream_model = row.upstream_model
  formData.endpoint_url = row.endpoint_url
  formData.api_key = ''
  formData.source = row.source
  formData.rpm_limit = row.rpm_limit
  formData.tpm_limit = row.tpm_limit
  formData.price_level = row.price_level
  dialogVisible.value = true
}

async function handleSave() {
  if (!formData.name.trim()) {
    MessagePlugin.warning('Name is required')
    return
  }
  if (!formData.endpoint_url.trim()) {
    MessagePlugin.warning('Endpoint URL is required')
    return
  }
  if (!formData.upstream_model.trim()) {
    MessagePlugin.warning('Upstream Model is required')
    return
  }
  if (!isEdit.value && !formData.api_key.trim()) {
    MessagePlugin.warning('API Key is required for new endpoints')
    return
  }

  const payload: Record<string, any> = { ...formData }
  if (isEdit.value && !payload.api_key) {
    delete payload.api_key
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateEndpoint(editingId.value, payload)
      MessagePlugin.success('Updated')
    } else {
      await createEndpoint(payload)
      MessagePlugin.success('Created')
    }
    dialogVisible.value = false
    fetchEndpoints()
  } catch (error: any) {
    MessagePlugin.error(error?.response?.data?.message || 'Operation failed')
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row: EndpointRow) {
  try {
    await updateEndpoint(row.id, { enabled: !row.enabled })
    MessagePlugin.success(row.enabled ? 'Disabled' : 'Enabled')
    fetchEndpoints()
  } catch (error: any) {
    MessagePlugin.error(error?.response?.data?.message || 'Operation failed')
  }
}

async function handleDelete(id: number) {
  try {
    await deleteEndpoint(id)
    MessagePlugin.success('Deleted')
    fetchEndpoints()
  } catch (error: any) {
    MessagePlugin.error(error?.response?.data?.message || 'Delete failed')
  }
}

// ── Quick Test Dialog ──
const testVisible = ref(false)
const testEndpoint = ref<EndpointRow | null>(null)
const testInput = ref('')
const testLoading = ref(false)
const testMessages = ref<Array<{ role: string; content: string }>>([])

function openTestDialog(row: EndpointRow) {
  testEndpoint.value = row
  testMessages.value = []
  testInput.value = ''
  testVisible.value = true
}

async function sendTestMessage() {
  const msg = testInput.value.trim()
  if (!msg || !testEndpoint.value) return

  testMessages.value.push({ role: 'user', content: msg })
  testInput.value = ''
  testLoading.value = true

  try {
    // Use the gateway endpoint for testing via the endpoint's endpoint_url directly.
    const res = await http.post('/admin/endpoints/' + testEndpoint.value.id + '/test', {
      message: msg,
      stream: false,
    })
    const reply = res?.data?.data?.reply || res?.data?.data?.content || 'No response'
    testMessages.value.push({ role: 'assistant', content: reply })
  } catch (error: any) {
    const errMsg = error?.response?.data?.message || error?.message || 'Request failed'
    testMessages.value.push({ role: 'assistant', content: `[Error] ${errMsg}` })
  } finally {
    testLoading.value = false
  }
}

function formatTime(value?: string) {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN')
}

onMounted(() => fetchEndpoints())
</script>
