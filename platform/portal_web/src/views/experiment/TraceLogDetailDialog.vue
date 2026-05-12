<template>
  <!-- Full-screen overlay dialog -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl mx-4 overflow-hidden max-h-[90vh] flex flex-col">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-200 flex items-center justify-between shrink-0">
        <div class="flex items-center gap-3">
          <h3 class="text-lg font-semibold text-dp-title">{{ $t('experiment.trace.logs.detail_title') }}</h3>
          <span
            class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
            :class="log.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
          >
            {{ log.success ? $t('experiment.trace.logs.status_success') : $t('experiment.trace.logs.status_failed') }}
          </span>
        </div>
        <button class="p-1 rounded-lg text-dp-muted hover:text-dp-title hover:bg-slate-100 transition-colors" @click="$emit('close')">
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Body: metadata sidebar + content area -->
      <div class="flex-1 flex overflow-hidden">
        <!-- Left: Metadata panel -->
        <div class="w-72 shrink-0 border-r border-slate-200 bg-slate-50/50 p-5 overflow-y-auto">
          <h4 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-4">
            {{ $t('experiment.trace.logs.detail_meta') }}
          </h4>
          <div class="space-y-3">
            <MetaItem label="Request ID" :mono="true">{{ log.request_id }}</MetaItem>
            <MetaItem :label="$t('experiment.trace.logs.col_model')">
              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-dp-blue">
                {{ log.model_name }}
              </span>
            </MetaItem>
            <MetaItem label="API Key ID" :mono="true">{{ log.api_key_id }}</MetaItem>
            <MetaItem :label="log.is_stream ? $t('experiment.trace.logs.detail_stream') : $t('experiment.trace.logs.detail_non_stream')">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="log.is_stream ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'"
              >
                {{ log.is_stream ? 'SSE' : 'JSON' }}
              </span>
            </MetaItem>
            <MetaItem v-if="log.is_stream && log.first_token_ms > 0" :label="$t('experiment.trace.logs.detail_ttft')">
              {{ log.first_token_ms }}ms
            </MetaItem>

            <!-- Token usage -->
            <div class="pt-2 border-t border-slate-200">
              <h5 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-2">Tokens</h5>
              <div class="grid grid-cols-2 gap-2">
                <TokenStat :label="$t('experiment.trace.logs.detail_prompt_tokens')" :value="log.prompt_tokens" color="blue" />
                <TokenStat :label="$t('experiment.trace.logs.detail_completion_tokens')" :value="log.completion_tokens" color="green" />
                <TokenStat :label="$t('experiment.trace.logs.detail_total_tokens')" :value="log.total_tokens" color="slate" />
                <TokenStat v-if="log.reasoning_tokens > 0" :label="$t('experiment.trace.logs.detail_reasoning_tokens')" :value="log.reasoning_tokens" color="purple" />
              </div>
            </div>

            <!-- Duration -->
            <MetaItem :label="$t('experiment.trace.logs.detail_duration')">
              <span class="font-mono text-sm font-medium text-dp-title">{{ formatDuration(log.duration_ms) }}</span>
            </MetaItem>

            <!-- Error message -->
            <div v-if="!log.success && log.error_message" class="pt-2 border-t border-slate-200">
              <h5 class="text-xs font-semibold text-red-500 uppercase tracking-wider mb-1">{{ $t('experiment.trace.logs.detail_error') }}</h5>
              <p class="text-xs text-red-600 bg-red-50 rounded-lg p-2 break-all">{{ log.error_message }}</p>
            </div>

            <!-- Timestamp -->
            <MetaItem :label="$t('experiment.trace.logs.col_time')">{{ formatTime(log.created_at) }}</MetaItem>
          </div>
        </div>

        <!-- Right: Request / Response content -->
        <div class="flex-1 flex flex-col overflow-hidden">
          <!-- Tabs -->
          <div class="flex items-center border-b border-slate-200 px-6 shrink-0">
            <button
              v-for="tab in tabs"
              :key="tab"
              class="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
              :class="activeTab === tab
                ? 'border-dp-blue text-dp-blue'
                : 'border-transparent text-dp-muted hover:text-dp-title'"
              @click="activeTab = tab"
            >
              {{ tab === 'request' ? $t('experiment.trace.logs.detail_request') : $t('experiment.trace.logs.detail_response') }}
            </button>
            <!-- View mode toggle -->
            <div class="ml-auto flex items-center gap-1 bg-slate-100 rounded-lg p-0.5">
              <button
                v-for="mode in viewModes"
                :key="mode"
                class="px-3 py-1 rounded-md text-xs font-medium transition-colors"
                :class="viewMode === mode ? 'bg-white text-dp-title shadow-sm' : 'text-dp-muted hover:text-dp-title'"
                @click="viewMode = mode"
              >{{ mode === 'pretty' ? $t('experiment.trace.logs.detail_pretty') : $t('experiment.trace.logs.detail_json') }}</button>
            </div>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto p-6">
            <div v-if="detailLoading" class="text-center py-16 text-dp-muted text-sm">
              {{ $t('experiment.trace.logs.detail_loading') }}
            </div>
            <template v-else>
              <!-- Pretty view: render messages as chat bubbles -->
              <div v-if="viewMode === 'pretty'" class="space-y-4">
                <template v-if="activeTab === 'request'">
                  <div v-for="(msg, i) in requestMessages" :key="i" class="flex gap-3">
                    <div
                      class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                      :class="roleBadgeClass(msg.role)"
                    >{{ roleInitial(msg.role) }}</div>
                    <div class="flex-1 min-w-0">
                      <div class="text-xs font-medium text-dp-muted mb-1">{{ msg.role }}</div>
                      <div class="bg-slate-50 rounded-lg p-3 text-sm text-dp-title whitespace-pre-wrap break-words">{{ msg.content }}</div>
                    </div>
                  </div>
                  <div v-if="requestMessages.length === 0" class="text-sm text-dp-muted text-center py-8">
                    No messages parsed — switch to JSON view
                  </div>
                </template>
                <template v-else>
                  <div v-for="(msg, i) in responseMessages" :key="i" class="flex gap-3">
                    <div
                      class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
                      :class="roleBadgeClass(msg.role)"
                    >{{ roleInitial(msg.role) }}</div>
                    <div class="flex-1 min-w-0">
                      <div class="text-xs font-medium text-dp-muted mb-1">{{ msg.role }}</div>
                      <div v-if="msg.reasoning" class="bg-purple-50 rounded-lg p-3 text-sm text-purple-800 whitespace-pre-wrap break-words mb-2">
                        <span class="text-xs font-medium text-purple-500 block mb-1">💭 Reasoning</span>
                        {{ msg.reasoning }}
                      </div>
                      <div class="bg-slate-50 rounded-lg p-3 text-sm text-dp-title whitespace-pre-wrap break-words">{{ msg.content }}</div>
                    </div>
                  </div>
                  <div v-if="responseMessages.length === 0" class="text-sm text-dp-muted text-center py-8">
                    No response content — switch to JSON view
                  </div>
                </template>
              </div>

              <!-- JSON view: formatted JSON tree -->
              <div v-else>
                <pre class="bg-slate-900 text-slate-100 rounded-xl p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-[60vh]">{{ activeTab === 'request' ? formattedRequestJSON : formattedResponseJSON }}</pre>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, h as createVNode } from 'vue'
import { useI18n } from 'vue-i18n'
import { getTraceLogDetail, type TraceLogItem, type TraceLogDetail } from '@/api/experiment'

interface ChatMessage {
  role: string
  content: string
  reasoning?: string
}

const props = defineProps<{
  traceId: number
  log: TraceLogItem
}>()

defineEmits<{ close: [] }>()

const { t } = useI18n()
const tabs = ['request', 'response'] as const
const viewModes = ['pretty', 'json'] as const
const activeTab = ref<'request' | 'response'>('request')
const viewMode = ref<'pretty' | 'json'>('pretty')
const detailLoading = ref(true)
const detail = ref<TraceLogDetail | null>(null)

onMounted(async () => {
  try {
    const res = await getTraceLogDetail(props.traceId, props.log.id)
    if (res.data?.data) {
      detail.value = res.data.data
    }
  } catch (e: any) {
    console.error('[TraceLogDetail] fetch detail failed:', e)
  } finally {
    detailLoading.value = false
  }
})

/** Parse request body JSON into chat messages */
const requestMessages = computed<ChatMessage[]>(() => {
  if (!detail.value?.request_body) return []
  try {
    const parsed = JSON.parse(detail.value.request_body)
    if (Array.isArray(parsed?.messages)) {
      return parsed.messages.map((m: any) => ({
        role: String(m.role || 'unknown'),
        content: typeof m.content === 'string' ? m.content : JSON.stringify(m.content, null, 2),
      }))
    }
  } catch { /* ignore parse errors */ }
  return []
})

/** Parse response body JSON into assistant message(s) */
const responseMessages = computed<ChatMessage[]>(() => {
  if (!detail.value?.response_body) return []
  try {
    const parsed = JSON.parse(detail.value.response_body)
    // Standard OpenAI format: choices[].message
    if (Array.isArray(parsed?.choices)) {
      return parsed.choices
        .filter((c: any) => c.message)
        .map((c: any) => ({
          role: String(c.message.role || 'assistant'),
          content: typeof c.message.content === 'string' ? c.message.content : JSON.stringify(c.message.content, null, 2),
          reasoning: c.message.reasoning_content || '',
        }))
    }
  } catch { /* ignore parse errors */ }
  return []
})

const formattedRequestJSON = computed(() => {
  if (!detail.value?.request_body) return '(empty)'
  try {
    return JSON.stringify(JSON.parse(detail.value.request_body), null, 2)
  } catch {
    return detail.value.request_body
  }
})

const formattedResponseJSON = computed(() => {
  if (!detail.value?.response_body) return '(empty)'
  try {
    return JSON.stringify(JSON.parse(detail.value.response_body), null, 2)
  } catch {
    return detail.value.response_body
  }
})

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: string): string {
  if (!ts) return ''
  try { return new Date(ts).toLocaleString() } catch { return ts }
}

function roleBadgeClass(role: string): string {
  switch (role) {
    case 'system': return 'bg-amber-100 text-amber-700'
    case 'user': return 'bg-blue-100 text-blue-700'
    case 'assistant': return 'bg-green-100 text-green-700'
    case 'tool': return 'bg-purple-100 text-purple-700'
    default: return 'bg-slate-100 text-slate-600'
  }
}

function roleInitial(role: string): string {
  return (role[0] || '?').toUpperCase()
}

// --- Sub-components rendered inline ---

/** MetaItem: label + value row in metadata panel */
const MetaItem = (props: { label: string; mono?: boolean }, { slots }: any) => {
  return createVNode('div', null, [
    createVNode('div', { class: 'text-xs text-dp-muted mb-0.5' }, props.label),
    createVNode('div', {
      class: ['text-sm text-dp-title break-all', props.mono ? 'font-mono text-xs' : ''].join(' ')
    }, slots.default?.())
  ])
}

/** TokenStat: compact stat tile */
const TokenStat = (props: { label: string; value: number; color: string }) => {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    green: 'bg-green-50 text-green-700',
    purple: 'bg-purple-50 text-purple-700',
    slate: 'bg-slate-100 text-dp-title',
  }
  return createVNode('div', { class: `rounded-lg p-2 ${colorClasses[props.color] || colorClasses.slate}` }, [
    createVNode('div', { class: 'text-[10px] font-medium opacity-70 truncate' }, props.label),
    createVNode('div', { class: 'text-sm font-bold font-mono mt-0.5' }, String(props.value.toLocaleString()))
  ])
}
</script>
