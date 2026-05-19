<template>
  <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
    <!-- Chat area (3/4) -->
    <div
      class="lg:col-span-3 bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col"
      style="min-height: 680px"
    >
      <!-- Model & API Key selector bar -->
      <div class="px-6 py-4 border-b border-slate-100 flex flex-col gap-3">
        <div class="flex flex-wrap items-center gap-4">
          <!-- Model selector -->
          <div class="flex items-center gap-2">
            <label class="text-xs font-medium text-dp-muted whitespace-nowrap">Model</label>
            <div class="relative" ref="modelDropdownRef">
              <button
                type="button"
                :disabled="!hasAvailableModels"
                class="min-w-[400px] flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg border text-sm text-left focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-dp-placeholder"
                :class="
                  modelDropdownOpen ? 'border-dp-blue ring-2 ring-blue-100 bg-white' : 'border-slate-200 bg-white'
                "
                @click="modelDropdownOpen = !modelDropdownOpen"
              >
                <span v-if="!hasAvailableModels" class="text-dp-placeholder truncate">{{
                  $t('service.chat.no_models')
                }}</span>
                <template v-else-if="selectedModelOption">
                  <span class="truncate text-dp-body">{{ selectedModelOption.id }}</span>
                  <span
                    :class="vendorTypeTagClass(selectedModelOption.vendor_type)"
                    class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                    >{{ vendorTypeLabel(selectedModelOption.vendor_type) }}</span
                  >
                </template>
                <span v-else class="text-dp-placeholder truncate">{{ $t('service.chat.model') }}</span>
                <svg
                  class="w-4 h-4 shrink-0 text-slate-400 transition-transform"
                  :class="{ 'rotate-180': modelDropdownOpen }"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              <Transition
                enter-active-class="transition duration-100 ease-out"
                enter-from-class="opacity-0 -translate-y-1"
                enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition duration-75 ease-in"
                leave-from-class="opacity-100 translate-y-0"
                leave-to-class="opacity-0 -translate-y-1"
              >
                <ul
                  v-if="modelDropdownOpen"
                  class="absolute z-50 mt-1 max-h-80 w-full min-w-[400px] overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                >
                  <li class="sticky top-0 bg-white px-2 py-1.5 border-b border-slate-100">
                    <input
                      v-model="modelSearchQuery"
                      type="text"
                      placeholder="Search model name..."
                      class="w-full px-3 py-1.5 rounded-md border border-slate-200 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-400"
                      @click.stop
                    />
                  </li>
                  <li
                    v-for="model in filteredAvailableModels"
                    :key="model.id"
                    class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50"
                    :class="model.id === selectedModel ? 'bg-blue-50 text-dp-blue font-medium' : 'text-dp-body'"
                    @click="selectModel(model.id)"
                  >
                    <div class="flex-1 min-w-0">
                      <div class="truncate">{{ model.id }}</div>
                      <div class="flex flex-wrap items-center gap-1 mt-0.5">
                        <span v-if="model.max_context_length" class="text-[10px] text-slate-400">{{
                          formatModelCtx(model.max_context_length)
                        }}</span>
                        <span
                          v-for="tag in model.tags || []"
                          :key="tag"
                          class="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0 text-[10px] text-slate-500"
                          >{{ tag }}</span
                        >
                      </div>
                    </div>
                    <span
                      :class="vendorTypeTagClass(model.vendor_type)"
                      class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                      >{{ vendorTypeLabel(model.vendor_type) }}</span
                    >
                  </li>
                </ul>
              </Transition>
            </div>
            <div class="relative group flex items-center">
              <svg
                class="w-5 h-5 text-amber-500 cursor-help"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                />
              </svg>
              <div
                class="invisible group-hover:visible opacity-0 group-hover:opacity-100 absolute left-1/2 -translate-x-1/2 bottom-full mb-2 w-64 px-3 py-2 bg-slate-800 text-white text-xs leading-relaxed rounded-lg shadow-lg transition-all duration-200 z-50 pointer-events-none"
              >
                {{ $t('service.chat.hybrid_tip') }}
                <div
                  class="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0 border-x-[6px] border-x-transparent border-t-[6px] border-t-slate-800"
                />
              </div>
            </div>
          </div>

          <!-- API Key selector -->
          <div class="flex items-center gap-2">
            <label class="text-xs font-medium text-dp-muted whitespace-nowrap">API Key</label>
            <select
              :value="selectedAPIKeyId"
              @change="handleAPIKeySelect(Number(($event.target as HTMLSelectElement).value))"
              class="min-w-[200px] px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body bg-white focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            >
              <option v-if="apiKeys.length === 0" value="" disabled>{{ $t('service.apikey.empty') }}</option>
              <option v-for="key in apiKeys" :key="key.id" :value="key.id">
                {{ key.name }} ({{ key.key_prefix }}••••)
              </option>
            </select>
          </div>
        </div>

        <!-- Model info badges -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          <span class="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-dp-muted">{{
            $t('service.chat.available_models', { count: availableModels.length })
          }}</span>
          <span
            v-if="selectedModelOption"
            class="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-1 font-medium text-dp-blue"
            >{{ vendorTypeLabel(selectedModelOption.vendor_type) }}</span
          >
        </div>
      </div>
      <div v-if="modelLoadError" class="px-6 py-3 border-b border-rose-100 bg-rose-50 text-sm text-rose-600">
        {{ modelLoadError }}
      </div>
      <div
        v-else-if="!hasAvailableModels"
        class="px-6 py-3 border-b border-slate-100 bg-slate-50 text-sm text-dp-muted"
      >
        {{ $t('service.chat.no_models') }}
      </div>

      <!-- Chat messages -->
      <div ref="chatContainer" class="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        <div v-if="messages.length === 0" class="flex items-center justify-center h-full text-dp-muted text-sm">
          {{ $t('service.chat.placeholder') }}
        </div>
        <div
          v-for="(msg, i) in messages"
          :key="i"
          class="flex"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <div
            class="max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap"
            :class="
              msg.role === 'user'
                ? 'bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white rounded-br-md'
                : 'bg-slate-100 text-dp-body rounded-bl-md'
            "
          >
            <details v-if="msg.reasoning" class="mb-2">
              <summary class="cursor-pointer text-xs opacity-70 hover:opacity-100">
                {{ $t('service.chat.thinking') }}
              </summary>
              <div class="mt-1 text-xs opacity-60 border-l-2 border-slate-300 pl-2">{{ msg.reasoning }}</div>
            </details>
            <div v-if="msg.images && msg.images.length" class="flex flex-wrap gap-2 mb-2">
              <img
                v-for="(img, idx) in msg.images"
                :key="idx"
                :src="img"
                class="max-w-[200px] max-h-[200px] rounded-lg border border-white/20 object-cover cursor-pointer"
                @click="previewImage(img)"
              />
            </div>
            {{ msg.content }}
            <span
              v-if="msg.streaming"
              class="inline-block w-1.5 h-4 bg-dp-blue animate-pulse ml-0.5 align-text-bottom"
            />
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="px-6 py-4 border-t border-slate-100">
        <div v-if="pendingImages.length" class="flex flex-wrap gap-2 mb-3">
          <div v-for="(img, idx) in pendingImages" :key="idx" class="relative group">
            <img :src="img" class="w-16 h-16 rounded-lg border border-slate-200 object-cover" />
            <button
              @click="removePendingImage(idx)"
              class="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 shadow-sm"
            >
              ✕
            </button>
          </div>
          <div class="flex items-end">
            <span class="text-[10px] text-dp-placeholder">{{
              $t('service.chat.images_attached', { count: pendingImages.length })
            }}</span>
          </div>
        </div>
        <form @submit.prevent="sendMessage" class="flex gap-3">
          <div class="flex-1 relative">
            <input
              ref="chatInputRef"
              v-model="userInput"
              type="text"
              :placeholder="
                pendingImages.length
                  ? $t('service.chat.input_placeholder_with_image')
                  : $t('service.chat.input_placeholder')
              "
              :disabled="isSending"
              class="w-full px-4 py-2.5 rounded-xl border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200 disabled:opacity-60"
              @paste="handlePaste"
            />
          </div>
          <button
            type="submit"
            :disabled="isSending || (!userInput.trim() && !pendingImages.length)"
            class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white text-sm font-medium shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {{ isSending ? '...' : $t('service.chat.send') }}
          </button>
        </form>
        <div class="mt-1.5 text-[10px] text-dp-placeholder">{{ $t('service.chat.paste_image_tip') }}</div>
      </div>
    </div>
    <!-- end chat area -->

    <!-- Inference params sidebar (1/4) -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
      <h3 class="text-sm font-medium text-dp-body mb-3">{{ $t('service.params.title') }}</h3>
      <div class="space-y-4">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs font-medium text-dp-muted">Temperature</label>
            <span class="text-xs text-dp-placeholder font-mono">{{ inferParams.temperature.toFixed(2) }}</span>
          </div>
          <input
            v-model.number="inferParams.temperature"
            type="range"
            min="0"
            max="2"
            step="0.05"
            class="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-dp-blue [&::-webkit-slider-thumb]:shadow-sm"
          />
          <div class="flex justify-between text-[10px] text-dp-placeholder mt-0.5">
            <span>{{ $t('service.params.precise') }}</span
            ><span>{{ $t('service.params.creative') }}</span>
          </div>
        </div>
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1 block">Max Tokens</label>
          <input
            v-model.number="inferParams.maxTokens"
            type="number"
            min="1"
            max="32768"
            step="64"
            class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-xs font-medium text-dp-muted">Top P</label>
            <span class="text-xs text-dp-placeholder font-mono">{{ inferParams.topP.toFixed(2) }}</span>
          </div>
          <input
            v-model.number="inferParams.topP"
            type="range"
            min="0"
            max="1"
            step="0.05"
            class="w-full h-1.5 bg-slate-200 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-dp-blue [&::-webkit-slider-thumb]:shadow-sm"
          />
        </div>
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1 block">System Prompt</label>
          <textarea
            v-model="inferParams.systemPrompt"
            rows="3"
            :placeholder="$t('service.params.system_placeholder')"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder resize-none focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
        </div>
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1 block">{{ $t('service.params.stop') }}</label>
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span
              v-for="(s, i) in inferParams.stop"
              :key="i"
              class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-xs text-dp-body font-mono"
            >
              {{ s }}
              <button @click="inferParams.stop.splice(i, 1)" class="text-dp-placeholder hover:text-red-500 text-[10px]">
                ✕
              </button>
            </span>
          </div>
          <div class="flex gap-2">
            <input
              v-model="stopInput"
              type="text"
              :placeholder="$t('service.params.stop_placeholder')"
              class="flex-1 px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              @keydown.enter.prevent="addStop"
            />
            <button
              @click="addStop"
              :disabled="!stopInput.trim()"
              class="px-2.5 py-1.5 rounded-lg bg-slate-100 text-xs text-dp-muted hover:bg-slate-200 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              +
            </button>
          </div>
        </div>
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1 block">{{
            $t('service.params.reasoning_effort')
          }}</label>
          <select
            v-model="inferParams.reasoningEffort"
            @change="persistParams"
            class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 bg-white"
          >
            <option value="">{{ $t('service.params.reasoning_effort_default') }}</option>
            <option value="none">none</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
          <p class="text-[10px] text-dp-placeholder mt-0.5">{{ $t('service.params.reasoning_effort_desc') }}</p>
        </div>
        <button
          @click="resetParams"
          class="w-full py-1.5 rounded-lg border border-slate-200 text-xs text-dp-muted hover:bg-slate-50 transition-colors"
        >
          {{ $t('service.params.reset') }}
        </button>
      </div>

      <!-- API usage snippet -->
      <div class="mt-6 pt-5 border-t border-slate-100">
        <h3 class="text-sm font-medium text-dp-body mb-2">{{ $t('service.apikey.usage_title') }}</h3>
        <pre
          class="text-xs text-dp-muted bg-slate-50 p-3 rounded-lg overflow-x-auto leading-relaxed"
        ><code>curl {{ apiBaseUrl }}/chat/completions \
  -H "Authorization: Bearer dp-your-key" \
  -H "Content-Type: application/json" \
  -d '{
  "model": "{{ selectedModel }}",
  "messages": [
    {"role": "user", "content": "Hello"}
  ],
  "temperature": {{ inferParams.temperature }},
  "max_tokens": {{ inferParams.maxTokens }},
  "top_p": {{ inferParams.topP }}{{ inferParams.reasoningEffort ? `,\n  "reasoning_effort": "${inferParams.reasoningEffort}"` : '' }}
}'</code></pre>
      </div>
    </div>
    <!-- end params sidebar -->
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { listCustomModels, type CustomModel } from '@/api/custom-model'
import type { APIKey } from '@/api/apikey'

const { t } = useI18n()
const route = useRoute()

// ── Props ──
const props = defineProps<{
  apiKeys: APIKey[]
  /** Resolve full API Key secret by ID (provided by parent via ApiKeyManager). */
  getFullKey: (id: number) => Promise<string | null>
}>()

const emit = defineEmits<{
  (e: 'toast', message: string, type?: 'success' | 'info'): void
}>()

// ── Gateway model types ──

interface GatewayModelOption {
  id: string
  vendor_type?: string
  model_family?: string
  owned_by?: string
  param_scale?: number
  max_context_length?: number
  tags?: string[]
}

// ── Model state ──

const selectedModel = ref('')
const availableModels = ref<GatewayModelOption[]>([])
const modelLoadError = ref('')
const selectedModelOption = computed(() => availableModels.value.find((m) => m.id === selectedModel.value) || null)
const hasAvailableModels = computed(() => availableModels.value.length > 0)

// Custom model dropdown
const modelDropdownOpen = ref(false)
const modelDropdownRef = ref<HTMLElement>()
const modelSearchQuery = ref('')

const filteredAvailableModels = computed(() => {
  const q = modelSearchQuery.value.trim().toLowerCase()
  if (!q) return availableModels.value
  return availableModels.value.filter((m) => m.id.toLowerCase().includes(q))
})

function selectModel(id: string) {
  selectedModel.value = id
  modelDropdownOpen.value = false
  modelSearchQuery.value = ''
}

// ── API Key selection (persisted in localStorage) ──

const API_KEY_SELECTED_STORAGE_KEY = 'dp_service_selected_api_key_id'

const selectedAPIKeyId = ref<number | null>(loadSelectedAPIKeyId())

function loadSelectedAPIKeyId(): number | null {
  const raw = localStorage.getItem(API_KEY_SELECTED_STORAGE_KEY)
  if (!raw) return null
  const parsed = Number(raw)
  return Number.isFinite(parsed) ? parsed : null
}

function persistSelectedAPIKeyId(id: number | null) {
  if (id === null) {
    localStorage.removeItem(API_KEY_SELECTED_STORAGE_KEY)
    return
  }
  localStorage.setItem(API_KEY_SELECTED_STORAGE_KEY, String(id))
}

function handleAPIKeySelect(id: number) {
  selectedAPIKeyId.value = id
  persistSelectedAPIKeyId(id)
}

/** Sync selected API Key when keys list changes. */
function syncSelectedAPIKey() {
  const hasSelected = selectedAPIKeyId.value !== null && props.apiKeys.some((key) => key.id === selectedAPIKeyId.value)
  if (hasSelected) return
  const first = props.apiKeys[0]
  selectedAPIKeyId.value = first?.id ?? null
  persistSelectedAPIKeyId(selectedAPIKeyId.value)
}

async function getActiveAPIKey(): Promise<string | null> {
  if (selectedAPIKeyId.value === null) return null
  return props.getFullKey(selectedAPIKeyId.value)
}

// ── Chat state ──

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  reasoning?: string
  streaming?: boolean
  images?: string[]
}

const messages = ref<ChatMessage[]>([])
const userInput = ref('')
const isSending = ref(false)
const chatContainer = ref<HTMLElement>()
const chatInputRef = ref<HTMLInputElement>()

// ── Image paste support ──

const pendingImages = ref<string[]>([])
const MAX_PENDING_IMAGES = 5
const MAX_IMAGE_SIZE_MB = 10

function handlePaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return

  for (const item of items) {
    if (!item.type.startsWith('image/')) continue
    e.preventDefault()
    const file = item.getAsFile()
    if (!file) continue

    if (file.size > MAX_IMAGE_SIZE_MB * 1024 * 1024) {
      emit('toast', t('service.chat.image_too_large', { max: MAX_IMAGE_SIZE_MB }), 'info')
      continue
    }

    if (pendingImages.value.length >= MAX_PENDING_IMAGES) {
      emit('toast', t('service.chat.image_limit', { max: MAX_PENDING_IMAGES }), 'info')
      break
    }

    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        pendingImages.value.push(reader.result)
      }
    }
    reader.readAsDataURL(file)
  }
}

function removePendingImage(index: number) {
  pendingImages.value.splice(index, 1)
}

function previewImage(url: string) {
  window.open(url, '_blank')
}

// ── Inference parameters (persisted in localStorage) ──

const PARAMS_STORAGE_KEY = 'dp_service_infer_params'

interface InferParams {
  temperature: number
  maxTokens: number
  topP: number
  systemPrompt: string
  stop: string[]
  reasoningEffort: string
}

const defaultParams: InferParams = {
  temperature: 0.7,
  maxTokens: 2048,
  topP: 0.9,
  systemPrompt: '',
  stop: [],
  reasoningEffort: '',
}

function loadStoredParams(): InferParams {
  try {
    const raw = localStorage.getItem(PARAMS_STORAGE_KEY)
    if (!raw) return { ...defaultParams, stop: [] }
    const parsed = JSON.parse(raw)
    return {
      temperature: parsed.temperature ?? defaultParams.temperature,
      maxTokens: parsed.maxTokens ?? defaultParams.maxTokens,
      topP: parsed.topP ?? defaultParams.topP,
      systemPrompt: parsed.systemPrompt ?? defaultParams.systemPrompt,
      stop: Array.isArray(parsed.stop) ? parsed.stop : [],
      reasoningEffort: parsed.reasoningEffort ?? defaultParams.reasoningEffort,
    }
  } catch {
    return { ...defaultParams, stop: [] }
  }
}

function persistParams() {
  localStorage.setItem(PARAMS_STORAGE_KEY, JSON.stringify(inferParams.value))
}

const inferParams = ref<InferParams>(loadStoredParams())
const stopInput = ref('')

function addStop() {
  const val = stopInput.value.trim()
  if (!val || inferParams.value.stop.includes(val)) return
  if (inferParams.value.stop.length >= 8) return
  inferParams.value.stop.push(val)
  stopInput.value = ''
  persistParams()
}

function resetParams() {
  inferParams.value = { ...defaultParams, stop: [], reasoningEffort: '' }
  persistParams()
}

// ── Gateway base URL ──
const apiBaseUrl = import.meta.env.VITE_GATEWAY_BASE_URL || window.location.origin + '/v1'

// ── Send message with streaming ──

async function sendMessage() {
  const text = userInput.value.trim()
  if ((!text && !pendingImages.value.length) || isSending.value) return

  if (!selectedModel.value) {
    messages.value.push({ role: 'assistant', content: t('service.chat.need_model') })
    return
  }

  const apiKey = await getActiveAPIKey()
  if (!apiKey) {
    messages.value.push({ role: 'assistant', content: t('service.chat.need_apikey') })
    return
  }

  const imagesToSend = [...pendingImages.value]
  pendingImages.value = []

  messages.value.push({ role: 'user', content: text, images: imagesToSend.length ? imagesToSend : undefined })
  userInput.value = ''
  isSending.value = true
  scrollToBottom()

  messages.value.push({ role: 'assistant', content: '', streaming: true })
  const assistantIdx = messages.value.length - 1

  try {
    const chatMessages = messages.value
      .filter((message) => !message.streaming)
      .map((message) => {
        if (message.images && message.images.length > 0) {
          const contentParts: Array<Record<string, any>> = []
          if (message.content) {
            contentParts.push({ type: 'text', text: message.content })
          }
          for (const imgDataUrl of message.images) {
            contentParts.push({
              type: 'image_url',
              image_url: { url: imgDataUrl, detail: 'auto' },
            })
          }
          return { role: message.role, content: contentParts }
        }
        return { role: message.role, content: message.content }
      })
    if (inferParams.value.systemPrompt.trim()) {
      chatMessages.unshift({ role: 'system', content: inferParams.value.systemPrompt.trim() })
    }

    const requestBody: Record<string, any> = {
      model: selectedModel.value,
      messages: chatMessages,
      stream: true,
      temperature: inferParams.value.temperature,
      max_tokens: inferParams.value.maxTokens,
      top_p: inferParams.value.topP,
    }
    if (inferParams.value.stop.length > 0) {
      requestBody.stop = inferParams.value.stop
    }
    if (inferParams.value.reasoningEffort) {
      requestBody.reasoning_effort = inferParams.value.reasoningEffort
    }

    persistParams()

    const response = await fetch(`${apiBaseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify(requestBody),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      messages.value[assistantIdx].content = err?.error?.message || `Error: ${response.status}`
      messages.value[assistantIdx].streaming = false
      return
    }

    const reader = response.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data: ')) continue
        const data = trimmed.slice(6)
        if (data === '[DONE]') {
          messages.value[assistantIdx].streaming = false
          break
        }
        try {
          const chunk = JSON.parse(data)
          const delta = chunk.choices?.[0]?.delta
          if (delta?.content) {
            messages.value[assistantIdx].content += delta.content
          }
          if (delta?.reasoning_content) {
            messages.value[assistantIdx].reasoning =
              (messages.value[assistantIdx].reasoning || '') + delta.reasoning_content
          }
        } catch {
          // ignore parse errors
        }
      }
      scrollToBottom()
    }

    messages.value[assistantIdx].streaming = false
  } catch (err: any) {
    messages.value[assistantIdx].content = err?.message || 'Network error'
    messages.value[assistantIdx].streaming = false
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

// ── Model helpers ──

function vendorTypeTagClass(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider':
      return 'bg-emerald-100 text-emerald-700'
    case 'hybrid':
      return 'bg-amber-100 text-amber-700'
    default:
      return 'bg-blue-100 text-dp-blue'
  }
}

function vendorTypeLabel(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider':
      return 'Provider'
    case 'hybrid':
      return 'Hybrid'
    default:
      return 'DeepNode'
  }
}

function formatModelCtx(n: number): string {
  if (!n) return ''
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(0) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

function normalizeGatewayModels(items: unknown[]): GatewayModelOption[] {
  const seen = new Set<string>()
  return items
    .map((item): GatewayModelOption => {
      const record = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>
      return {
        id: String(record.id || '').trim(),
        vendor_type: String(record.vendor_type || '').trim(),
        model_family: String(record.model_family || '').trim(),
        owned_by: String(record.owned_by || '').trim(),
        param_scale: Number(record.param_scale || 0),
        max_context_length: Number(record.max_context_length || 0),
        tags: Array.isArray(record.tags) ? (record.tags as string[]) : [],
      }
    })
    .filter((model) => {
      if (!model.id || seen.has(model.id)) return false
      seen.add(model.id)
      return true
    })
    .sort((left, right) => left.id.localeCompare(right.id))
}

function syncSelectedModel(models: GatewayModelOption[]) {
  if (selectedModel.value && models.some((m) => m.id === selectedModel.value)) return
  selectedModel.value = models[0]?.id || ''
}

// Store gateway models separately for re-merging with custom models
const gatewayModels = ref<GatewayModelOption[]>([])
const customModels = ref<CustomModel[]>([])

async function fetchModels() {
  modelLoadError.value = ''
  try {
    const res = await fetch(`${apiBaseUrl}/models`)
    if (!res.ok) throw new Error(`gateway returned ${res.status}`)
    const json = await res.json()
    const items = Array.isArray(json?.data) ? json.data : []
    gatewayModels.value = normalizeGatewayModels(items)
    mergeModelsIntoDropdown()
  } catch (error) {
    console.error('[PlaygroundPanel] load models failed', error)
    gatewayModels.value = []
    availableModels.value = []
    selectedModel.value = ''
    modelLoadError.value = t('service.chat.load_models_failed')
  }
}

async function fetchCustomModels() {
  const res = await listCustomModels()
  customModels.value = res.data?.data || []
  mergeModelsIntoDropdown()
}

function mergeModelsIntoDropdown() {
  const seen = new Set(gatewayModels.value.map((m) => m.id))
  const customEntries: GatewayModelOption[] = customModels.value
    .filter((cm) => cm.enabled && !seen.has(cm.model_name))
    .map((cm) => ({
      id: cm.model_name,
      vendor_type: cm.vendor_type || 'hybrid',
      model_family: cm.model_family || '',
      owned_by: 'user',
      param_scale: 0,
      max_context_length: 0,
      tags: cm.tags && cm.tags.length ? [...cm.tags, 'custom'] : ['custom'],
    }))
  const merged = [...gatewayModels.value, ...customEntries].sort((a, b) => a.id.localeCompare(b.id))
  availableModels.value = merged
  syncSelectedModel(merged)
}

// ── Click outside handler for model dropdown ──

function handleClickOutsideDropdown(e: MouseEvent) {
  if (modelDropdownRef.value && !modelDropdownRef.value.contains(e.target as Node)) {
    modelDropdownOpen.value = false
  }
}

// ── Lifecycle ──

onMounted(async () => {
  document.addEventListener('click', handleClickOutsideDropdown)
  syncSelectedAPIKey()
  await Promise.all([fetchModels(), fetchCustomModels()])

  // Pre-select model from route query
  const queryModel = route.query.model as string
  if (queryModel && availableModels.value.some((m) => m.id === queryModel)) {
    selectedModel.value = queryModel
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutsideDropdown)
})

// ── Expose for parent access ──
defineExpose({
  availableModels,
  syncSelectedAPIKey,
  fetchCustomModels,
})
</script>
