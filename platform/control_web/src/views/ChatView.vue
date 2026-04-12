<template>
  <div class="chat-view flex h-[calc(100vh-7rem)] gap-4">
    <aside class="w-80 bg-dp-bg-3 rounded-xl border border-white/5 flex flex-col shrink-0 overflow-hidden">
      <div class="p-4 border-b border-white/5">
        <h3 class="text-dp-text-1 font-medium mb-4">Chat 调试</h3>

        <div class="space-y-3">
          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">统一调度模式</label>
            <div class="rounded-lg border border-white/10 bg-dp-bg-4 px-3 py-2 text-xs text-dp-text-2">
              Gateway 会根据模型来源自动调度到 DeepNode 或 Provider。
            </div>
          </div>

          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">NodeManager 节点（仅观测）</label>
            <t-select
              v-model="selectedNode"
              placeholder="未选择节点也可调试 Provider 模型"
              :options="nodeOptions"
              clearable
            />
          </div>

          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">模型名称</label>
            <t-select
              v-model="modelName"
              placeholder="选择模型"
              :options="modelOptions"
              :disabled="modelOptions.length === 0"
              filterable
            />
            <div v-if="selectedModelMeta" class="mt-2 text-xs text-dp-text-3 space-y-1">
              <div>来源：{{ vendorLabel(selectedModelMeta.vendorType) }}</div>
              <div v-if="selectedModelMeta.providerType">Provider：{{ selectedModelMeta.providerType }}</div>
            </div>
          </div>

          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">API Key</label>
            <t-input v-model="apiKey" placeholder="dp-xxxxxx" type="password" />
          </div>

          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">Temperature: {{ temperature }}</label>
            <t-slider v-model="temperature" :min="0" :max="2" :step="0.1" />
          </div>

          <div>
            <label class="text-dp-text-3 text-xs mb-1 block">Max Tokens: {{ maxTokens }}</label>
            <t-slider v-model="maxTokens" :min="64" :max="8192" :step="64" />
          </div>

          <div class="rounded-lg border border-white/10 bg-dp-bg-4 px-3 py-3 text-xs text-dp-text-2 space-y-1">
            <div class="font-medium text-dp-text-1">最近一次路由</div>
            <div>Backend: {{ lastRoute.backend || '-' }}</div>
            <div>Target: {{ lastRoute.target || '-' }}</div>
            <div v-if="lastRoute.providerType">Provider: {{ lastRoute.providerType }}</div>
          </div>
        </div>
      </div>

      <div class="flex-1 p-4 overflow-auto">
        <div class="flex items-center justify-between mb-3">
          <span class="text-dp-text-3 text-xs">历史会话</span>
          <t-button size="small" variant="text" theme="primary" @click="newSession">
            <template #icon><AddIcon /></template>
            新建
          </t-button>
        </div>
        <div class="space-y-1">
          <div
            v-for="(session, idx) in sessions"
            :key="idx"
            class="px-3 py-2 rounded-lg cursor-pointer text-sm truncate transition-colors"
            :class="[currentSession === idx ? 'bg-dp-blue/10 text-dp-blue' : 'text-dp-text-2 hover:bg-white/5']"
            @click="switchSession(idx)"
          >
            {{ session.title || `会话 ${idx + 1}` }}
          </div>
        </div>
      </div>
    </aside>

    <div class="flex-1 flex flex-col bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <div ref="chatContainer" class="flex-1 overflow-auto p-6 space-y-4">
        <div v-if="currentMessages.length === 0" class="flex items-center justify-center h-full">
          <div class="text-center">
            <ChatIcon class="w-16 h-16 text-dp-text-3 mx-auto mb-4 opacity-30" />
            <p class="text-dp-text-3">选择统一模型并输入 API Key，开始调试对话</p>
          </div>
        </div>

        <div v-for="(msg, idx) in currentMessages" :key="idx" class="flex" :class="[msg.role === 'user' ? 'justify-end' : 'justify-start']">
          <div
            class="max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed"
            :class="[
              msg.role === 'user'
                ? 'bg-dp-blue text-white rounded-br-md'
                : 'bg-dp-bg-4 text-dp-text-1 rounded-bl-md border border-white/5'
            ]"
          >
            <div v-if="msg.reasoning" class="mb-3">
              <t-collapse>
                <t-collapse-panel header="思考过程" class="!bg-yellow-900/20 !rounded-lg !border-yellow-500/20">
                  <pre class="text-xs text-dp-yellow whitespace-pre-wrap">{{ msg.reasoning }}</pre>
                </t-collapse-panel>
              </t-collapse>
            </div>
            <div class="whitespace-pre-wrap">{{ msg.content }}<span v-if="msg.streaming" class="animate-pulse">▌</span></div>
            <div v-if="msg.role === 'assistant' && !msg.streaming && msg.timing" class="mt-2 pt-2 border-t border-white/5 flex gap-3 text-[11px] text-dp-text-3">
              <span>首次响应: {{ msg.timing.ttft }}ms</span>
              <span>总耗时: {{ msg.timing.total }}ms</span>
            </div>
          </div>
        </div>
      </div>

      <div class="p-4 border-t border-white/5">
        <div class="flex gap-3">
          <t-textarea
            v-model="inputText"
            placeholder="输入消息... (Ctrl+Enter 发送)"
            :autosize="{ minRows: 1, maxRows: 4 }"
            class="flex-1"
            @keydown="handleKeydown"
          />
          <t-button
            theme="primary"
            :loading="isSending"
            :disabled="!canSend"
            class="self-end !h-10"
            @click="sendMessage"
          >
            <template #icon><SendIcon /></template>
            发送
          </t-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ChatIcon, SendIcon, AddIcon } from 'tdesign-icons-vue-next'
import { getNodeManagers, getEnabledModels } from '@/api/admin'

interface TimingInfo {
  ttft: number
  total: number
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  streaming?: boolean
  timing?: TimingInfo
}

interface Session {
  title: string
  messages: Message[]
}

interface ModelOptionItem {
  label: string
  value: string
  vendorType: string
  providerType: string
}

const selectedNode = ref('')
const modelName = ref('')
const apiKey = ref(localStorage.getItem('dp_chat_api_key') || '')
const temperature = ref(0.7)
const maxTokens = ref(2048)
const inputText = ref('')
const isSending = ref(false)
const chatContainer = ref<HTMLElement | null>(null)
const nodeOptions = ref<{ label: string; value: string }[]>([])
const availableModels = ref<ModelOptionItem[]>([])
const lastRoute = ref({ backend: '', target: '', providerType: '' })

const sessions = ref<Session[]>([{ title: '新会话', messages: [] }])
const currentSession = ref(0)

const currentMessages = computed(() => sessions.value[currentSession.value]?.messages || [])
const canSend = computed(() => inputText.value.trim() && modelName.value && apiKey.value.trim() && !isSending.value)
const selectedModelMeta = computed(() => availableModels.value.find((item) => item.value === modelName.value) || null)

watch(apiKey, (val) => {
  if (val) localStorage.setItem('dp_chat_api_key', val)
  else localStorage.removeItem('dp_chat_api_key')
})

const modelOptions = computed(() => {
  return availableModels.value.map((item) => ({
    label: item.label,
    value: item.value,
  }))
})

// Fetch all enabled models via admin API (includes models with allow_external_call=false).
async function fetchModels() {
  try {
    const res = await getEnabledModels()
    const items = res?.data?.data || []
    const models = items
      .map((item: any) => ({
        label: item.provider_type ? `${item.model_name} (${item.provider_type}/${item.vendor_type})` : `${item.model_name} (${item.vendor_type || 'deepnode'})`,
        value: item.model_name,
        vendorType: item.vendor_type || 'deepnode',
        providerType: item.provider_type || '',
      }))
      .filter((item: ModelOptionItem) => item.value)
    availableModels.value = models
    if (models.length > 0 && !modelName.value) {
      modelName.value = models[0].value
    }
  } catch {
    availableModels.value = []
  }
}

onMounted(async () => {
  const [nodeRes] = await Promise.all([
    getNodeManagers().catch(() => null),
    fetchModels(),
  ])
  if (nodeRes?.data?.data) {
    nodeOptions.value = nodeRes.data.data.map((nm: any) => ({
      label: `${nm.name} (${nm.addr})`,
      value: nm.addr,
    }))
    if (nodeOptions.value.length > 0) {
      selectedNode.value = nodeOptions.value[0].value
    }
  }
})

function newSession() {
  sessions.value.push({ title: `会话 ${sessions.value.length + 1}`, messages: [] })
  currentSession.value = sessions.value.length - 1
}

function switchSession(idx: number) {
  currentSession.value = idx
}

function handleKeydown(e: KeyboardEvent) {
  if (e.ctrlKey && e.key === 'Enter') {
    e.preventDefault()
    sendMessage()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(currentMessages, () => scrollToBottom(), { deep: true })

async function sendMessage() {
  if (!canSend.value) return

  const text = inputText.value.trim()
  inputText.value = ''

  const session = sessions.value[currentSession.value]
  session.messages.push({ role: 'user', content: text })
  if (session.title.startsWith('会话') || session.title === '新会话') {
    session.title = text.slice(0, 20) + (text.length > 20 ? '...' : '')
  }

  const apiMessages = session.messages
    .filter((item) => !item.streaming)
    .map((item) => ({ role: item.role, content: item.content }))

  session.messages.push({ role: 'assistant', content: '', streaming: true })
  const assistantIdx = session.messages.length - 1
  isSending.value = true

  const body = {
    model: modelName.value,
    messages: apiMessages,
    temperature: temperature.value,
    max_tokens: maxTokens.value,
    stream: true,
  }

  const startTime = performance.now()
  let firstTokenTime = 0

  const gatewayBase = import.meta.env.VITE_GATEWAY_BASE_URL || '/v1'
  const response = await fetch(`${gatewayBase}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey.value.trim()}`,
    },
    body: JSON.stringify(body),
  }).catch((err) => {
    session.messages[assistantIdx].content = `请求失败: ${err.message}`
    session.messages[assistantIdx].streaming = false
    isSending.value = false
    return null
  })

  if (!response) return

  lastRoute.value = {
    backend: response.headers.get('X-DeepPool-Backend') || '',
    target: response.headers.get('X-DeepPool-Route-Target') || '',
    providerType: response.headers.get('X-DeepPool-Provider-Type') || '',
  }

  if (!response.ok) {
    const errText = await response.text()
    session.messages[assistantIdx].content = `错误 ${response.status}: ${errText}`
    session.messages[assistantIdx].streaming = false
    isSending.value = false
    return
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  if (!reader) {
    session.messages[assistantIdx].content = '无法读取响应流'
    session.messages[assistantIdx].streaming = false
    isSending.value = false
    return
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed || !trimmed.startsWith('data: ')) continue
      const data = trimmed.slice(6)
      if (data === '[DONE]') break

      try {
        const parsed = JSON.parse(data)
        const delta = parsed.choices?.[0]?.delta
        if (!delta) continue

        if (!firstTokenTime && (delta.reasoning_content || delta.content)) {
          firstTokenTime = performance.now()
        }

        if (delta.reasoning_content) {
          session.messages[assistantIdx].reasoning =
            (session.messages[assistantIdx].reasoning || '') + delta.reasoning_content
        }
        if (delta.content) {
          session.messages[assistantIdx].content += delta.content
        }
      } catch {
        // ignore invalid chunk
      }
    }
  }

  const totalTime = performance.now()
  session.messages[assistantIdx].timing = {
    ttft: Math.round(firstTokenTime ? firstTokenTime - startTime : totalTime - startTime),
    total: Math.round(totalTime - startTime),
  }
  session.messages[assistantIdx].streaming = false
  isSending.value = false
}

function vendorLabel(vendorType: string) {
  if (vendorType === 'provider') return 'Provider'
  if (vendorType === 'hybrid') return 'Hybrid'
  return 'DeepNode'
}
</script>
