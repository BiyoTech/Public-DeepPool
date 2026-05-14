<template>
  <!-- Full-screen overlay dialog -->
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" @click.self="$emit('close')">
    <div class="bg-white rounded-2xl shadow-2xl w-full max-w-[95vw] mx-4 overflow-hidden max-h-[90vh] flex flex-col">
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
            <MetaItem v-if="log.first_token_ms > 0" :label="$t('experiment.trace.logs.detail_ttft')">
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

            <!-- Request params (extracted from request body) -->
            <div v-if="requestParams.length > 0" class="pt-2 border-t border-slate-200">
              <h5 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-2">Parameters</h5>
              <div class="space-y-1">
                <div v-for="param in requestParams" :key="param.key" class="flex items-center justify-between text-xs">
                  <span class="text-dp-muted">{{ param.key }}</span>
                  <span class="font-mono text-dp-title">{{ param.value }}</span>
                </div>
              </div>
            </div>

            <!-- Tools summary -->
            <div v-if="toolsDefined.length > 0" class="pt-2 border-t border-slate-200">
              <h5 class="text-xs font-semibold text-dp-muted uppercase tracking-wider mb-2">Tools ({{ toolsDefined.length }})</h5>
              <div class="space-y-1">
                <div v-for="tool in toolsDefined" :key="tool.name" class="text-xs">
                  <span class="font-mono text-indigo-600">{{ tool.name }}</span>
                  <span v-if="tool.desc" class="text-dp-muted ml-1">— {{ tool.desc }}</span>
                </div>
              </div>
            </div>

            <!-- Error message -->
            <div v-if="!log.success && log.error_message" class="pt-2 border-t border-slate-200">
              <h5 class="text-xs font-semibold text-red-500 uppercase tracking-wider mb-1">{{ $t('experiment.trace.logs.detail_error') }}</h5>
              <p class="text-xs text-red-600 bg-red-50 rounded-lg p-2 break-all">{{ log.error_message }}</p>
            </div>

            <!-- Timestamp -->
            <MetaItem :label="$t('experiment.trace.logs.col_time')">{{ formatTime(log.created_at) }}</MetaItem>
          </div>
        </div>

        <!-- Right: Request / Response content + Evaluation panel -->
        <div class="flex-1 flex overflow-hidden min-w-0">
          <!-- Content area -->
          <div class="flex-1 flex flex-col overflow-hidden min-w-0">
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
                <!-- ═══ Pretty view ═══ -->
                <div v-if="viewMode === 'pretty'" class="space-y-4">
                  <template v-if="activeTab === 'request'">
                    <div v-for="(msg, i) in requestMessages" :key="i" class="flex gap-3">
                      <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5" :class="roleBadgeClass(msg.role)">{{ roleInitial(msg.role) }}</div>
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="text-xs font-medium text-dp-muted">{{ msg.role }}</span>
                          <span v-if="msg.name" class="text-[10px] font-mono text-slate-400">({{ msg.name }})</span>
                          <span v-if="msg.toolCallId" class="text-[10px] font-mono text-purple-400">{{ msg.toolCallId }}</span>
                        </div>
                        <div v-if="msg.content" class="bg-slate-50 rounded-lg p-3 text-sm text-dp-title whitespace-pre-wrap break-words">{{ msg.content }}</div>
                        <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="space-y-2" :class="{ 'mt-2': msg.content }">
                          <div v-for="(tc, j) in msg.toolCalls" :key="j" class="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                            <div class="flex items-center gap-2 mb-1.5">
                              <span class="text-[10px] font-semibold text-indigo-500 uppercase tracking-wider">Function Call</span>
                              <span class="font-mono text-xs text-indigo-700 font-medium">{{ tc.functionName }}</span>
                              <span v-if="tc.id" class="text-[10px] font-mono text-indigo-400 ml-auto">{{ tc.id }}</span>
                            </div>
                            <pre class="text-xs font-mono text-indigo-900 bg-indigo-100/50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">{{ tc.arguments }}</pre>
                          </div>
                        </div>
                      </div>
                    </div>
                    <div v-if="requestMessages.length === 0" class="text-sm text-dp-muted text-center py-8">No messages parsed — switch to JSON view</div>
                  </template>
                  <template v-else>
                    <div v-if="responseMeta" class="mb-4 bg-slate-50 rounded-lg px-4 py-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
                      <span v-if="responseMeta.id" class="text-dp-muted">id: <span class="font-mono text-dp-title">{{ responseMeta.id }}</span></span>
                      <span v-if="responseMeta.model" class="text-dp-muted">model: <span class="font-mono text-dp-title">{{ responseMeta.model }}</span></span>
                      <span v-if="responseMeta.created" class="text-dp-muted">created: <span class="text-dp-title">{{ formatTime(new Date(responseMeta.created * 1000).toISOString()) }}</span></span>
                    </div>
                    <div v-for="(choice, ci) in responseChoices" :key="ci" class="space-y-3">
                      <div v-if="responseChoices.length > 1" class="flex items-center gap-2 text-xs text-dp-muted">
                        <span class="font-medium">Choice {{ choice.index }}</span>
                        <span v-if="choice.finishReason" class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium" :class="finishReasonClass(choice.finishReason)">{{ choice.finishReason }}</span>
                      </div>
                      <div v-else-if="choice.finishReason" class="flex items-center gap-2 text-xs text-dp-muted mb-1">
                        <span>finish_reason:</span>
                        <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium" :class="finishReasonClass(choice.finishReason)">{{ choice.finishReason }}</span>
                      </div>
                      <div class="flex gap-3">
                        <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5" :class="roleBadgeClass(choice.message.role)">{{ roleInitial(choice.message.role) }}</div>
                        <div class="flex-1 min-w-0">
                          <div class="text-xs font-medium text-dp-muted mb-1">{{ choice.message.role }}</div>
                          <div v-if="choice.message.reasoning" class="bg-purple-50 rounded-lg p-3 text-sm text-purple-800 whitespace-pre-wrap break-words mb-2">
                            <span class="text-xs font-medium text-purple-500 block mb-1">Reasoning</span>
                            {{ choice.message.reasoning }}
                          </div>
                          <div v-if="choice.message.content" class="bg-slate-50 rounded-lg p-3 text-sm text-dp-title whitespace-pre-wrap break-words">{{ choice.message.content }}</div>
                          <div v-if="choice.message.toolCalls && choice.message.toolCalls.length > 0" class="space-y-2" :class="{ 'mt-2': choice.message.content }">
                            <div v-for="(tc, j) in choice.message.toolCalls" :key="j" class="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
                              <div class="flex items-center gap-2 mb-1.5">
                                <span class="text-[10px] font-semibold text-indigo-500 uppercase tracking-wider">Function Call</span>
                                <span class="font-mono text-xs text-indigo-700 font-medium">{{ tc.functionName }}</span>
                                <span v-if="tc.id" class="text-[10px] font-mono text-indigo-400 ml-auto">{{ tc.id }}</span>
                              </div>
                              <pre class="text-xs font-mono text-indigo-900 bg-indigo-100/50 rounded p-2 overflow-x-auto whitespace-pre-wrap break-all">{{ tc.arguments }}</pre>
                            </div>
                          </div>
                          <div v-if="!choice.message.content && (!choice.message.toolCalls || choice.message.toolCalls.length === 0) && !choice.message.reasoning" class="text-xs text-dp-muted italic">(empty response)</div>
                        </div>
                      </div>
                    </div>
                    <div v-if="responseMeta?.usage" class="mt-4 bg-slate-50 rounded-lg px-4 py-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-dp-muted">
                      <span>prompt_tokens: <span class="font-mono text-dp-title">{{ responseMeta.usage.prompt_tokens }}</span></span>
                      <span>completion_tokens: <span class="font-mono text-dp-title">{{ responseMeta.usage.completion_tokens }}</span></span>
                      <span>total_tokens: <span class="font-mono text-dp-title">{{ responseMeta.usage.total_tokens }}</span></span>
                      <span v-if="responseMeta.usage.reasoning_tokens">reasoning_tokens: <span class="font-mono text-dp-title">{{ responseMeta.usage.reasoning_tokens }}</span></span>
                    </div>
                    <div v-if="responseChoices.length === 0" class="text-sm text-dp-muted text-center py-8">No response content — switch to JSON view</div>
                  </template>
                </div>
                <!-- ═══ JSON view ═══ -->
                <div v-else>
                  <pre class="bg-slate-900 text-slate-100 rounded-xl p-4 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-[60vh]">{{ activeTab === 'request' ? formattedRequestJSON : formattedResponseJSON }}</pre>
                </div>
              </template>
            </div>
          </div>

          <!-- Drag handle for evaluation panel -->
          <div
            class="w-1.5 shrink-0 cursor-col-resize bg-slate-200 hover:bg-dp-blue/40 active:bg-dp-blue/60 transition-colors"
            @mousedown="onResizeStart"
          />

          <!-- Evaluation panel (always visible) -->
          <div class="shrink-0 border-l border-slate-200 bg-slate-50/50 flex flex-col overflow-hidden" :style="{ width: evalPanelWidth + 'px' }">
            <div class="px-4 py-3 border-b border-slate-200 shrink-0">
              <h4 class="text-xs font-semibold text-dp-muted uppercase tracking-wider">
                {{ $t('experiment.trace.logs.annotation.title') }}
              </h4>
            </div>
            <div class="flex-1 overflow-y-auto p-4 space-y-5">
              <!-- Feedback section -->
              <div>
                <div class="flex items-center justify-between mb-2">
                  <h5 class="text-xs font-semibold text-dp-title uppercase tracking-wider">{{ $t('experiment.trace.logs.annotation.feedback') }}</h5>
                  <button
                    class="text-xs text-dp-blue hover:text-dp-blue/80 font-medium"
                    @click="addFeedback"
                  >+ {{ $t('experiment.trace.logs.annotation.add_feedback') }}</button>
                </div>
                <div v-if="feedbacks.length === 0" class="text-xs text-dp-muted italic py-2">
                  {{ $t('experiment.trace.logs.annotation.feedback_empty') }}
                </div>
                <div v-for="(fb, i) in feedbacks" :key="i" class="bg-white rounded-lg border border-slate-200 p-3 mb-2 space-y-2">
                  <div class="flex items-center justify-between">
                    <span class="text-[10px] text-dp-muted font-medium uppercase shrink-0 mr-1">{{ $t('experiment.trace.logs.annotation.feedback_name') }} *</span>
                    <button class="text-xs text-red-400 hover:text-red-600 shrink-0 ml-2" @click="feedbacks.splice(i, 1)">
                      {{ $t('experiment.trace.logs.annotation.delete_feedback') }}
                    </button>
                  </div>
                  <input
                    v-model="fb.name"
                    :placeholder="$t('experiment.trace.logs.annotation.feedback_name_placeholder')"
                    class="w-full text-sm font-medium text-dp-title border border-slate-200 rounded-md px-2.5 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-dp-blue/50 focus:border-dp-blue/50"
                  />
                  <div class="flex items-center gap-3">
                    <span class="text-xs text-dp-muted">{{ $t('experiment.trace.logs.annotation.feedback_passed') }}</span>
                    <button
                      class="px-2 py-0.5 rounded text-xs font-medium transition-colors"
                      :class="fb.passed ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'"
                      @click="fb.passed = true"
                    >{{ $t('experiment.trace.logs.annotation.yes') }}</button>
                    <button
                      class="px-2 py-0.5 rounded text-xs font-medium transition-colors"
                      :class="!fb.passed ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-500'"
                      @click="fb.passed = false"
                    >{{ $t('experiment.trace.logs.annotation.no') }}</button>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-dp-muted">{{ $t('experiment.trace.logs.annotation.feedback_source') }}</span>
                    <span
                      class="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium"
                      :class="fb.source === 'ai_judge' ? 'bg-purple-100 text-purple-700' : 'bg-blue-50 text-dp-blue'"
                    >{{ fb.source === 'ai_judge' ? $t('experiment.trace.logs.annotation.source_ai_judge') : $t('experiment.trace.logs.annotation.source_human') }}</span>
                  </div>
                  <textarea
                    v-model="fb.reason"
                    :placeholder="$t('experiment.trace.logs.annotation.feedback_reason_placeholder')"
                    rows="2"
                    class="w-full text-xs border border-slate-200 rounded-md p-2 resize-none focus:outline-none focus:ring-1 focus:ring-dp-blue/50"
                  />
                </div>
              </div>

              <!-- Expectation section -->
              <div>
                <div class="flex items-center justify-between mb-2">
                  <h5 class="text-xs font-semibold text-dp-title uppercase tracking-wider">{{ $t('experiment.trace.logs.annotation.expectation') }}</h5>
                  <button
                    v-if="!expectation"
                    class="text-xs text-dp-blue hover:text-dp-blue/80 font-medium"
                    @click="addExpectation"
                  >+ {{ $t('experiment.trace.logs.annotation.add_expectation') }}</button>
                  <button
                    v-else
                    class="text-xs text-red-400 hover:text-red-600 font-medium"
                    @click="expectation = null"
                  >{{ $t('experiment.trace.logs.annotation.delete_expectation') }}</button>
                </div>
                <div v-if="!expectation" class="text-xs text-dp-muted italic py-2">
                  {{ $t('experiment.trace.logs.annotation.expectation_empty') }}
                </div>
                <div v-else class="bg-white rounded-lg border border-slate-200 p-3 space-y-2">
                  <div class="text-[10px] text-dp-muted font-medium uppercase">{{ $t('experiment.trace.logs.annotation.expectation_name') }} *</div>
                  <input
                    v-model="expectation.name"
                    :placeholder="$t('experiment.trace.logs.annotation.expectation_name_placeholder')"
                    class="w-full text-sm font-medium text-dp-title border border-slate-200 rounded-md px-2.5 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-dp-blue/50 focus:border-dp-blue/50"
                  />
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-dp-muted shrink-0">{{ $t('experiment.trace.logs.annotation.expectation_data_type') }}</span>
                    <select
                      v-model="expectation.data_type"
                      class="text-xs border border-slate-200 rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-dp-blue/50"
                    >
                      <option value="text">{{ $t('experiment.trace.logs.annotation.type_text') }}</option>
                      <option value="number">{{ $t('experiment.trace.logs.annotation.type_number') }}</option>
                      <option value="bool">{{ $t('experiment.trace.logs.annotation.type_bool') }}</option>
                      <option value="json">{{ $t('experiment.trace.logs.annotation.type_json') }}</option>
                    </select>
                  </div>
                  <textarea
                    v-model="expectation.content"
                    :placeholder="$t('experiment.trace.logs.annotation.expectation_content_placeholder')"
                    :rows="expectation.data_type === 'json' ? 5 : 2"
                    class="w-full text-xs border border-slate-200 rounded-md p-2 resize-none focus:outline-none focus:ring-1 focus:ring-dp-blue/50 font-mono"
                  />
                  <textarea
                    v-model="expectation.reason"
                    :placeholder="$t('experiment.trace.logs.annotation.expectation_reason_placeholder')"
                    rows="2"
                    class="w-full text-xs border border-slate-200 rounded-md p-2 resize-none focus:outline-none focus:ring-1 focus:ring-dp-blue/50"
                  />
                </div>
              </div>
            </div>

            <!-- Toast + Save button -->
            <div class="px-4 py-3 border-t border-slate-200 shrink-0 space-y-2">
              <div
                v-if="annotationToast"
                class="px-3 py-2 rounded-lg text-xs font-medium transition-all"
                :class="annotationToast.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'"
              >
                {{ annotationToast.message }}
              </div>
              <button
                class="w-full px-4 py-2 rounded-lg text-sm font-medium text-white transition-colors"
                :class="annotationSaving ? 'bg-dp-blue/60 cursor-not-allowed' : 'bg-dp-blue hover:bg-dp-blue/90'"
                :disabled="annotationSaving"
                @click="handleSaveAnnotation"
              >
                {{ annotationSaving ? $t('experiment.trace.logs.annotation.saving') : $t('experiment.trace.logs.annotation.save') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, h as createVNode } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getTraceLogDetail,
  getAnnotation,
  saveAnnotation,
  type TraceLogItem,
  type TraceLogDetail,
  type FeedbackItem,
  type ExpectationItem,
} from '@/api/experiment'

// Parsed tool call for pretty rendering
interface ToolCall {
  id: string
  functionName: string
  arguments: string // pretty-printed JSON
}

// Unified message structure for pretty view (request + response)
interface ChatMessage {
  role: string
  content: string
  name?: string        // function name (for tool role messages)
  toolCallId?: string  // tool_call_id (for tool role messages)
  toolCalls?: ToolCall[]
  reasoning?: string   // reasoning_content (for response)
}

// Request parameter extracted from body
interface RequestParam {
  key: string
  value: string
}

// Tool definition summary
interface ToolDef {
  name: string
  desc: string
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

// --- Annotation state ---
const feedbacks = ref<FeedbackItem[]>([])
const expectation = ref<ExpectationItem | null>(null)
const annotationSaving = ref(false)
const annotationToast = ref<{ type: 'success' | 'error'; message: string } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(type: 'success' | 'error', message: string) {
  annotationToast.value = { type, message }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { annotationToast.value = null }, 3000)
}

// --- Evaluation panel drag resize ---
const EVAL_MIN_W = 280
const EVAL_MAX_W = 600
const evalPanelWidth = ref(360)
let resizing = false
let startX = 0
let startWidth = 0

function onResizeStart(e: MouseEvent) {
  e.preventDefault()
  resizing = true
  startX = e.clientX
  startWidth = evalPanelWidth.value
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', onResizeEnd)
}

function onResizeMove(e: MouseEvent) {
  if (!resizing) return
  // Dragging left increases panel width, dragging right decreases it
  const delta = startX - e.clientX
  evalPanelWidth.value = Math.min(EVAL_MAX_W, Math.max(EVAL_MIN_W, startWidth + delta))
}

function onResizeEnd() {
  resizing = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', onResizeEnd)
})

// --- Annotation helpers ---
function addFeedback() {
  feedbacks.value.push({ name: '', passed: true, reason: '', source: 'human' })
}

function addExpectation() {
  expectation.value = { name: '', data_type: 'text', content: '', reason: '' }
}

async function handleSaveAnnotation() {
  // Frontend validation: all feedback items must have a name
  for (let i = 0; i < feedbacks.value.length; i++) {
    if (!feedbacks.value[i].name.trim()) {
      showToast('error', t('experiment.trace.logs.annotation.feedback_name_required', { index: i + 1 }))
      return
    }
  }
  // Expectation name is required if expectation exists
  if (expectation.value && !expectation.value.name.trim()) {
    showToast('error', t('experiment.trace.logs.annotation.expectation_name_required'))
    return
  }

  annotationSaving.value = true
  try {
    await saveAnnotation(props.traceId, props.log.id, {
      feedbacks: feedbacks.value,
      expectation: expectation.value,
    })
    showToast('success', t('experiment.trace.logs.annotation.save_success'))
  } catch (e: any) {
    console.error('[TraceLogDetail] save annotation failed:', e)
    const msg = e?.response?.data?.message || e?.message || t('experiment.trace.logs.annotation.save_error')
    showToast('error', msg)
  } finally {
    annotationSaving.value = false
  }
}

onMounted(async () => {
  try {
    const [detailRes, annotationRes] = await Promise.all([
      getTraceLogDetail(props.traceId, props.log.id),
      getAnnotation(props.traceId, props.log.id).catch(() => null),
    ])
    if (detailRes.data?.data) {
      detail.value = detailRes.data.data
    }
    if (annotationRes?.data?.data) {
      const ann = annotationRes.data.data
      feedbacks.value = ann.feedbacks || []
      expectation.value = ann.expectation || null
    }
  } catch (e: any) {
    console.error('[TraceLogDetail] fetch detail failed:', e)
  } finally {
    detailLoading.value = false
  }
})

/** Parse a tool_calls array into pretty ToolCall objects */
function parseToolCalls(toolCalls: any[]): ToolCall[] {
  if (!Array.isArray(toolCalls)) return []
  return toolCalls.map((tc: any) => ({
    id: tc.id || '',
    functionName: tc.function?.name || tc.type || 'unknown',
    arguments: prettyArgs(tc.function?.arguments),
  }))
}

/** Pretty-print function arguments (may be JSON string or object) */
function prettyArgs(args: any): string {
  if (!args) return ''
  if (typeof args === 'string') {
    try { return JSON.stringify(JSON.parse(args), null, 2) } catch { return args }
  }
  return JSON.stringify(args, null, 2)
}

/** Parse request body into full ChatMessage array with tool_calls support */
const requestMessages = computed<ChatMessage[]>(() => {
  if (!detail.value?.request_body) return []
  try {
    const parsed = JSON.parse(detail.value.request_body)
    if (!Array.isArray(parsed?.messages)) return []
    return parsed.messages.map((m: any) => {
      const msg: ChatMessage = {
        role: String(m.role || 'unknown'),
        content: typeof m.content === 'string' ? m.content : (m.content ? JSON.stringify(m.content, null, 2) : ''),
        name: m.name || undefined,
        toolCallId: m.tool_call_id || undefined,
      }
      if (Array.isArray(m.tool_calls) && m.tool_calls.length > 0) {
        msg.toolCalls = parseToolCalls(m.tool_calls)
      }
      return msg
    })
  } catch { return [] }
})

// Parsed OpenAI response metadata (top-level fields)
interface ResponseMeta {
  id?: string
  model?: string
  created?: number
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number; reasoning_tokens?: number }
}

// Parsed response choice with finish_reason
interface ResponseChoice {
  index: number
  finishReason: string
  message: ChatMessage
}

/** Parse response metadata from response body */
const responseMeta = computed<ResponseMeta | null>(() => {
  if (!detail.value?.response_body) return null
  try {
    const raw = detail.value.response_body.trim()
    if (raw.startsWith('{')) {
      const parsed = JSON.parse(raw)
      const meta: ResponseMeta = {}
      if (parsed.id) meta.id = parsed.id
      if (parsed.model) meta.model = parsed.model
      if (parsed.created) meta.created = parsed.created
      if (parsed.usage) {
        meta.usage = {
          prompt_tokens: parsed.usage.prompt_tokens || 0,
          completion_tokens: parsed.usage.completion_tokens || 0,
          total_tokens: parsed.usage.total_tokens || 0,
        }
        if (parsed.usage.completion_tokens_details?.reasoning_tokens) {
          meta.usage.reasoning_tokens = parsed.usage.completion_tokens_details.reasoning_tokens
        }
      }
      return meta
    }
    // SSE: extract metadata from last chunk with usage
    if (raw.startsWith('data:') || raw.includes('\ndata:')) {
      return parseSSEMeta(raw)
    }
  } catch { /* ignore */ }
  return null
})

/** Parse response choices (non-stream and SSE) */
const responseChoices = computed<ResponseChoice[]>(() => {
  if (!detail.value?.response_body) return []
  try {
    const raw = detail.value.response_body.trim()
    // Non-stream: standard JSON response
    if (raw.startsWith('{')) {
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed?.choices)) {
        return parsed.choices.map((c: any) => {
          const src = c.message || c.delta || {}
          const msg: ChatMessage = {
            role: String(src.role || 'assistant'),
            content: typeof src.content === 'string' ? src.content : (src.content ? JSON.stringify(src.content, null, 2) : ''),
            reasoning: src.reasoning_content || '',
          }
          if (Array.isArray(src.tool_calls) && src.tool_calls.length > 0) {
            msg.toolCalls = parseToolCalls(src.tool_calls)
          }
          return {
            index: c.index ?? 0,
            finishReason: c.finish_reason || '',
            message: msg,
          } as ResponseChoice
        })
      }
    }
    // SSE: aggregate delta chunks
    if (raw.startsWith('data:') || raw.includes('\ndata:')) {
      return parseSSEChoices(raw)
    }
  } catch { /* ignore */ }
  return []
})

/** Extract metadata from SSE stream (id, model from first chunk; usage from last chunk) */
function parseSSEMeta(raw: string): ResponseMeta {
  const meta: ResponseMeta = {}
  const lines = raw.split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('data:')) continue
    const payload = trimmed.slice(5).trim()
    if (!payload || payload === '[DONE]') continue
    try {
      const chunk = JSON.parse(payload)
      // First chunk usually has id and model
      if (chunk.id && !meta.id) meta.id = chunk.id
      if (chunk.model && !meta.model) meta.model = chunk.model
      if (chunk.created && !meta.created) meta.created = chunk.created
      // Last chunk usually has usage
      if (chunk.usage) {
        meta.usage = {
          prompt_tokens: chunk.usage.prompt_tokens || 0,
          completion_tokens: chunk.usage.completion_tokens || 0,
          total_tokens: chunk.usage.total_tokens || 0,
        }
        if (chunk.usage.completion_tokens_details?.reasoning_tokens) {
          meta.usage.reasoning_tokens = chunk.usage.completion_tokens_details.reasoning_tokens
        }
      }
    } catch { /* skip */ }
  }
  return meta
}

/** Aggregate SSE delta chunks into ResponseChoice objects */
function parseSSEChoices(raw: string): ResponseChoice[] {
  const lines = raw.split('\n')
  // Accumulate per-choice data (keyed by choice index)
  const choiceMap = new Map<number, {
    role: string
    contentParts: string[]
    reasoningParts: string[]
    toolCalls: Map<number, { id: string; name: string; args: string }>
    finishReason: string
  }>()

  function getOrCreate(idx: number) {
    if (!choiceMap.has(idx)) {
      choiceMap.set(idx, { role: 'assistant', contentParts: [], reasoningParts: [], toolCalls: new Map(), finishReason: '' })
    }
    return choiceMap.get(idx)!
  }

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed.startsWith('data:')) continue
    const payload = trimmed.slice(5).trim()
    if (!payload || payload === '[DONE]') continue
    try {
      const chunk = JSON.parse(payload)
      if (!Array.isArray(chunk?.choices)) continue
      for (const c of chunk.choices) {
        const idx = c.index ?? 0
        const acc = getOrCreate(idx)
        if (c.finish_reason) acc.finishReason = c.finish_reason
        const delta = c.delta
        if (!delta) continue
        if (delta.role) acc.role = delta.role
        if (delta.content) acc.contentParts.push(delta.content)
        if (delta.reasoning_content) acc.reasoningParts.push(delta.reasoning_content)
        if (Array.isArray(delta.tool_calls)) {
          for (const tc of delta.tool_calls) {
            const tcIdx = tc.index ?? acc.toolCalls.size
            const existing = acc.toolCalls.get(tcIdx)
            if (existing) {
              if (tc.function?.name) existing.name += tc.function.name
              if (tc.function?.arguments) existing.args += tc.function.arguments
            } else {
              acc.toolCalls.set(tcIdx, {
                id: tc.id || '',
                name: tc.function?.name || '',
                args: tc.function?.arguments || '',
              })
            }
          }
        }
      }
    } catch { /* skip */ }
  }

  // Convert accumulated data into ResponseChoice objects
  const choices: ResponseChoice[] = []
  for (const [idx, acc] of choiceMap) {
    const msg: ChatMessage = {
      role: acc.role,
      content: acc.contentParts.join(''),
      reasoning: acc.reasoningParts.join('') || undefined,
    }
    if (acc.toolCalls.size > 0) {
      msg.toolCalls = Array.from(acc.toolCalls.values()).map(tc => ({
        id: tc.id,
        functionName: tc.name,
        arguments: prettyArgs(tc.args),
      }))
    }
    choices.push({ index: idx, finishReason: acc.finishReason, message: msg })
  }
  return choices.sort((a, b) => a.index - b.index)
}

/** Extract request parameters (non-messages fields) for metadata panel */
const requestParams = computed<RequestParam[]>(() => {
  if (!detail.value?.request_body) return []
  try {
    const parsed = JSON.parse(detail.value.request_body)
    const params: RequestParam[] = []
    const paramKeys = ['model', 'temperature', 'top_p', 'max_tokens', 'stream', 'tool_choice', 'reasoning_effort', 'frequency_penalty', 'presence_penalty', 'seed']
    for (const key of paramKeys) {
      if (parsed[key] !== undefined && parsed[key] !== null) {
        params.push({ key, value: String(parsed[key]) })
      }
    }
    return params
  } catch { return [] }
})

/** Extract tool definitions summary for metadata panel */
const toolsDefined = computed<ToolDef[]>(() => {
  if (!detail.value?.request_body) return []
  try {
    const parsed = JSON.parse(detail.value.request_body)
    if (!Array.isArray(parsed?.tools)) return []
    return parsed.tools
      .filter((t: any) => t.type === 'function' && t.function)
      .map((t: any) => ({
        name: t.function.name || 'unknown',
        desc: truncate(t.function.description || '', 60),
      }))
  } catch { return [] }
})

const formattedRequestJSON = computed(() => {
  if (!detail.value?.request_body) return '(empty)'
  try { return JSON.stringify(JSON.parse(detail.value.request_body), null, 2) }
  catch { return detail.value.request_body }
})

const formattedResponseJSON = computed(() => {
  if (!detail.value?.response_body) return '(empty)'
  try { return JSON.stringify(JSON.parse(detail.value.response_body), null, 2) }
  catch { return detail.value.response_body }
})

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '...' : s
}

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
    case 'function': return 'bg-indigo-100 text-indigo-700'
    default: return 'bg-slate-100 text-slate-600'
  }
}

function finishReasonClass(reason: string): string {
  switch (reason) {
    case 'stop': return 'bg-green-100 text-green-700'
    case 'tool_calls': return 'bg-indigo-100 text-indigo-700'
    case 'function_call': return 'bg-indigo-100 text-indigo-700'
    case 'length': return 'bg-amber-100 text-amber-700'
    case 'content_filter': return 'bg-red-100 text-red-700'
    default: return 'bg-slate-100 text-slate-600'
  }
}

function roleInitial(role: string): string {
  return (role[0] || '?').toUpperCase()
}

// --- Sub-components rendered inline ---

const MetaItem = (props: { label: string; mono?: boolean }, { slots }: any) => {
  return createVNode('div', null, [
    createVNode('div', { class: 'text-xs text-dp-muted mb-0.5' }, props.label),
    createVNode('div', {
      class: ['text-sm text-dp-title break-all', props.mono ? 'font-mono text-xs' : ''].join(' ')
    }, slots.default?.())
  ])
}

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
