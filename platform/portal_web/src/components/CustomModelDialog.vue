<template>
  <!-- Custom Model Create/Edit Drawer (slides from right) -->
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-x-full"
    enter-to-class="translate-x-0"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-x-0"
    leave-to-class="translate-x-full"
  >
    <div v-if="visible" class="fixed inset-y-0 right-0 z-50 w-[500px] max-w-full bg-white shadow-2xl flex flex-col">
      <!-- Header -->
      <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
        <h3 class="text-lg font-bold text-slate-800">{{ editingModel ? 'Edit Model' : 'Create Custom Model' }}</h3>
        <button class="p-1.5 rounded-lg hover:bg-slate-100 transition" @click="emit('close')">
          <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Body (scrollable) -->
      <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
        <!-- Model Family selector (create only) -->
        <div v-if="!editingModel">
          <label class="text-xs font-medium text-slate-500 mb-1.5 block">Model Family</label>
          <div class="flex gap-3">
            <button
              type="button"
              @click="form.vendorType = 'hybrid'"
              class="flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors"
              :class="form.vendorType === 'hybrid' ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'"
            >
              Hybrid
            </button>
            <button
              type="button"
              @click="form.vendorType = 'provider'"
              class="flex-1 px-3 py-2 rounded-lg border text-sm font-medium transition-colors"
              :class="form.vendorType === 'provider' ? 'border-emerald-500 bg-emerald-50 text-emerald-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'"
            >
              Provider
            </button>
          </div>
          <p class="text-[10px] text-slate-400 mt-1">
            {{ form.vendorType === 'hybrid' ? 'Hybrid: intelligent routing across multiple child models' : 'Provider: register your own API endpoint (free of charge)' }}
          </p>
          <router-link
            v-if="form.vendorType === 'hybrid'"
            to="/docs/getting-started/custom-hybrid-model"
            class="inline-flex items-center gap-1 mt-1.5 text-[11px] text-blue-500 hover:text-blue-600 transition"
            @click.stop
          >
            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>
            </svg>
            Learn about Hybrid models →
          </router-link>
        </div>

        <!-- Display Name (create only) -->
        <div v-if="!editingModel">
          <label class="text-xs font-medium text-slate-500 mb-1 block">Model Name</label>
          <input
            v-model="form.displayName"
            type="text"
            placeholder="e.g. anthropic/claude-opus-4.6 (2-64 chars)"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
          <p class="text-[10px] text-slate-400 mt-1">Final model ID: u{{ userId }}-{{ form.displayName || '...' }}</p>
        </div>

        <!-- ═══ Hybrid Form ═══ -->
        <template v-if="form.vendorType === 'hybrid'">
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">Child Models (select ≥ 2)</label>
            <div class="max-h-40 overflow-y-auto border border-slate-200 rounded-lg p-2 space-y-1">
              <label
                v-for="pm in childCandidates"
                :key="pm.model_name"
                class="flex items-center gap-2 px-2 py-1 rounded hover:bg-slate-50 cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  :value="pm.model_name"
                  v-model="form.childModels"
                  class="rounded border-slate-300 text-blue-600 focus:ring-blue-200"
                />
                <span class="text-slate-700">{{ pm.model_name }}</span>
                <span class="text-[10px] text-slate-400">{{ pm.vendor_type }}</span>
                <span v-if="pm.is_user_provider" class="text-[10px] text-emerald-500">(mine)</span>
              </label>
            </div>
            <p class="text-[10px] text-slate-400 mt-1">Selected {{ form.childModels.length }}</p>
          </div>

          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">Routing Policy (YAML)</label>
            <textarea
              v-model="form.routingPolicy"
              rows="6"
              placeholder="Leave empty for default least-inflight strategy."
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-mono resize-y focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              style="min-height: 80px;"
            ></textarea>
          </div>
        </template>

        <!-- ═══ Provider Form ═══ -->
        <template v-if="form.vendorType === 'provider'">
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">Model Family</label>
            <select
              v-model="form.modelFamily"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            >
              <option value="">Select...</option>
              <option v-for="mf in modelFamilyOptions" :key="mf.value" :value="mf.value">{{ mf.label }}</option>
            </select>
          </div>

          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">Endpoint (API Base URL)</label>
            <input
              v-model="form.endpoint"
              type="text"
              placeholder="https://api.openai.com/v1"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">Upstream Model Name</label>
            <input
              v-model="form.upstreamModel"
              type="text"
              placeholder="gpt-4o / claude-sonnet-4-20250514"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">API Key</label>
            <input
              v-model="form.apiKey"
              type="password"
              :placeholder="editingModel ? 'Leave empty to keep current' : 'Enter API Key (stored encrypted)'"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            />
          </div>

          <div>
            <label class="text-xs font-medium text-slate-500 mb-2 block">Capabilities</label>
            <div class="flex flex-wrap gap-4">
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-slate-700">
                <input type="checkbox" v-model="form.supportsReasoning" class="rounded border-slate-300 text-blue-600 focus:ring-blue-200" />
                Reasoning
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-slate-700">
                <input type="checkbox" v-model="form.supportsVision" class="rounded border-slate-300 text-blue-600 focus:ring-blue-200" />
                Vision
              </label>
              <label class="flex items-center gap-1.5 cursor-pointer text-sm text-slate-700">
                <input type="checkbox" v-model="form.supportsFunctionCall" class="rounded border-slate-300 text-blue-600 focus:ring-blue-200" />
                Function Call
              </label>
            </div>
          </div>
        </template>

        <!-- Tags (common) -->
        <div>
          <label class="text-xs font-medium text-slate-500 mb-1 block">Tags</label>
          <div class="flex flex-wrap gap-1.5 mb-2">
            <span
              v-for="(tag, idx) in form.tags"
              :key="idx"
              class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-1 text-xs text-blue-600"
            >
              {{ tag }}
              <button @click="form.tags.splice(idx, 1)" class="text-blue-300 hover:text-red-400 text-[10px]">&times;</button>
            </span>
          </div>
          <input
            v-model="tagInput"
            type="text"
            placeholder="Type tag and press Enter"
            class="w-full px-3 py-1.5 rounded-lg border border-slate-200 text-xs focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
            @keydown.enter.prevent="addTag"
          />
        </div>

        <!-- Error -->
        <div v-if="error" class="px-3 py-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-600">
          {{ error }}
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-slate-100 flex justify-end gap-3 shrink-0">
        <button
          @click="emit('close')"
          class="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-500 hover:bg-slate-50 transition"
        >Cancel</button>
        <button
          @click="handleSave"
          :disabled="saving"
          class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition disabled:opacity-50"
        >{{ saving ? 'Saving...' : 'Save' }}</button>
      </div>
    </div>
  </Transition>

  <!-- Backdrop -->
  <Transition
    enter-active-class="transition duration-200"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="visible"
      class="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
      @click="emit('close')"
    />
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { createCustomModel, updateCustomModel, type CustomModel } from '@/api/custom-model'
import { getPublicModels, type PublicModel } from '@/api/model'

const props = defineProps<{
  visible: boolean
  editingModel?: CustomModel | null
  customModels?: CustomModel[] // for hybrid child candidates (user's own provider models)
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

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
  { label: 'Custom / Other', value: 'custom' },
]

const userId = computed(() => {
  const user = JSON.parse(localStorage.getItem('dp_user') || '{}')
  return user.id || 0
})

const form = ref(defaultForm())
const tagInput = ref('')
const saving = ref(false)
const error = ref('')
const publicModels = ref<PublicModel[]>([])

function defaultForm() {
  return {
    displayName: '',
    vendorType: 'hybrid' as 'hybrid' | 'provider',
    childModels: [] as string[],
    routingPolicy: '',
    modelFamily: '',
    endpoint: '',
    upstreamModel: '',
    apiKey: '',
    supportsReasoning: false,
    supportsVision: false,
    supportsFunctionCall: false,
    tags: [] as string[],
  }
}

// Child model candidates for hybrid: platform non-hybrid models + user's own provider models.
interface ChildCandidate {
  model_name: string
  vendor_type: string
  is_user_provider?: boolean
}
const childCandidates = computed<ChildCandidate[]>(() => {
  const platform: ChildCandidate[] = publicModels.value
    .filter(m => m.vendor_type !== 'hybrid')
    .map(m => ({ model_name: m.model_name, vendor_type: m.vendor_type }))
  const userProviders: ChildCandidate[] = (props.customModels || [])
    .filter(cm => cm.vendor_type === 'provider' && cm.enabled)
    .map(cm => ({ model_name: cm.model_name, vendor_type: 'provider', is_user_provider: true }))
  return [...platform, ...userProviders]
})

// Reset form when dialog opens.
watch(() => props.visible, async (v) => {
  if (v) {
    error.value = ''
    if (props.editingModel) {
      const cm = props.editingModel
      form.value = {
        displayName: cm.display_name,
        vendorType: cm.vendor_type || 'hybrid',
        childModels: [...(cm.child_models || [])],
        routingPolicy: cm.routing_policy || '',
        modelFamily: cm.model_family || '',
        endpoint: cm.endpoint || '',
        upstreamModel: cm.upstream_model || '',
        apiKey: '',
        supportsReasoning: cm.supports_reasoning || false,
        supportsVision: cm.supports_vision || false,
        supportsFunctionCall: cm.supports_function_call || false,
        tags: [...(cm.tags || [])],
      }
    } else {
      form.value = defaultForm()
    }
    // Fetch public models for hybrid child candidates.
    if (publicModels.value.length === 0) {
      try {
        const res = await getPublicModels()
        publicModels.value = (res?.data?.data || []).filter((m: PublicModel) => m.vendor_type !== 'hybrid')
      } catch { /* ignore */ }
    }
  }
})

function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.value.tags.includes(tag) && form.value.tags.length < 10) {
    form.value.tags.push(tag)
  }
  tagInput.value = ''
}

async function handleSave() {
  error.value = ''
  const f = form.value

  // Validation.
  if (!props.editingModel) {
    const name = f.displayName.trim()
    if (!name) { error.value = 'Model name is required'; return }
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_./-]{1,63}$/.test(name)) {
      error.value = 'Name must be 2-64 chars, start with letter/digit, allow letters/digits/-/_/./'; return
    }
  }
  if (f.vendorType === 'hybrid' && f.childModels.length < 2) {
    error.value = 'Select at least 2 child models'; return
  }
  if (f.vendorType === 'provider') {
    if (!f.modelFamily) { error.value = 'Select a model family'; return }
    if (!f.endpoint) { error.value = 'Endpoint URL is required'; return }
    if (!f.upstreamModel) { error.value = 'Upstream model name is required'; return }
    if (!props.editingModel && !f.apiKey) { error.value = 'API Key is required'; return }
  }

  saving.value = true
  try {
    if (props.editingModel) {
      const payload: Record<string, any> = { tags: f.tags }
      if (f.vendorType === 'hybrid') {
        payload.child_models = f.childModels
        payload.routing_policy = f.routingPolicy
      } else {
        payload.model_family = f.modelFamily
        payload.endpoint = f.endpoint
        payload.upstream_model = f.upstreamModel
        if (f.apiKey) payload.api_key = f.apiKey
        payload.supports_reasoning = f.supportsReasoning
        payload.supports_vision = f.supportsVision
        payload.supports_function_call = f.supportsFunctionCall
      }
      await updateCustomModel(props.editingModel.id, payload)
    } else {
      const payload: any = {
        display_name: f.displayName.trim(),
        vendor_type: f.vendorType,
        tags: f.tags,
      }
      if (f.vendorType === 'hybrid') {
        payload.child_models = f.childModels
        payload.routing_policy = f.routingPolicy
      } else {
        payload.model_family = f.modelFamily
        payload.endpoint = f.endpoint
        payload.upstream_model = f.upstreamModel
        payload.api_key = f.apiKey
        payload.supports_reasoning = f.supportsReasoning
        payload.supports_vision = f.supportsVision
        payload.supports_function_call = f.supportsFunctionCall
      }
      await createCustomModel(payload)
    }
    emit('saved')
    emit('close')
  } catch (err: any) {
    error.value = err?.response?.data?.message || err?.message || 'Save failed'
  } finally {
    saving.value = false
  }
}
</script>
