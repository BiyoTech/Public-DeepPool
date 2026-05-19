<template>
  <div>
    <!-- Header with create button -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-lg font-semibold text-dp-title">{{ $t('experiment.trace.title') }}</h2>
        <p class="text-sm text-dp-muted mt-1">{{ $t('experiment.trace.desc') }}</p>
      </div>
      <button
        class="px-4 py-2 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white text-sm font-medium hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all shadow-sm hover:shadow-md"
        @click="openCreate()"
      >
        + {{ $t('experiment.trace.create') }}
      </button>
    </div>

    <!-- Trace list -->
    <div v-if="loading" class="text-center py-16 text-dp-muted text-sm">{{ $t('experiment.loading') }}...</div>
    <div v-else-if="traces.length === 0" class="bg-white rounded-xl border border-slate-200 p-6">
      <div class="text-center py-12">
        <svg
          class="w-12 h-12 mx-auto text-slate-300 mb-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="1.5"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.808-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.98 0 13.788M12 12h.008v.008H12V12z"
          />
        </svg>
        <p class="text-sm text-dp-muted">{{ $t('experiment.trace.empty') }}</p>
      </div>
    </div>
    <div v-else class="space-y-3">
      <div
        v-for="trace in traces"
        :key="trace.id"
        class="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <h3
                class="font-semibold text-dp-title hover:text-dp-blue cursor-pointer transition-colors"
                @click="viewLogs(trace)"
              >
                {{ trace.name }}
              </h3>
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="trace.status === 'running' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'"
              >
                <span
                  v-if="trace.status === 'running'"
                  class="w-1.5 h-1.5 rounded-full bg-green-500 mr-1 animate-pulse"
                />
                {{
                  trace.status === 'running'
                    ? $t('experiment.trace.status_running')
                    : $t('experiment.trace.status_stopped')
                }}
              </span>
            </div>
            <div class="mt-2 flex flex-wrap gap-4 text-xs text-dp-muted">
              <span>
                <span
                  v-if="trace.storage_type === 'builtin'"
                  class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-blue-50 text-dp-blue"
                  >{{ $t('experiment.trace.storage_builtin') }}</span
                >
                <span
                  v-else
                  class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-500"
                  >{{ trace.db_type }}</span
                >
              </span>
              <span
                >{{ $t('experiment.trace.api_keys') }}:
                <b class="text-dp-title">{{ trace.api_key_ids?.length || 0 }}</b></span
              >
              <span
                >{{ $t('experiment.trace.models') }}:
                <b class="text-dp-title">{{
                  trace.model_names?.length ? trace.model_names.join(', ') : $t('experiment.trace.all_models')
                }}</b></span
              >
              <span>{{ $t('experiment.trace.created') }}: {{ trace.created_at }}</span>
            </div>
          </div>
          <div class="flex items-center gap-2 ml-4">
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors"
              @click="viewLogs(trace)"
            >
              {{ $t('experiment.trace.view_logs') }}
            </button>
            <button
              v-if="trace.status === 'stopped'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-dp-blue hover:bg-blue-100 transition-colors"
              @click="openEdit(trace)"
            >
              {{ $t('experiment.trace.edit') }}
            </button>
            <button
              v-if="trace.status === 'stopped'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-green-50 text-green-600 hover:bg-green-100 transition-colors"
              @click="toggleStatus(trace, 'running')"
            >
              {{ $t('experiment.trace.start') }}
            </button>
            <button
              v-else
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-50 text-amber-600 hover:bg-amber-100 transition-colors"
              @click="toggleStatus(trace, 'stopped')"
            >
              {{ $t('experiment.trace.stop') }}
            </button>
            <button
              class="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-50 text-red-600 hover:bg-red-100 transition-colors"
              @click="confirmDelete(trace)"
            >
              {{ $t('experiment.trace.delete') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create / Edit dialog -->
    <div
      v-if="showDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      @click.self="showDialog = false"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div class="px-6 py-4 border-b border-slate-200">
          <h3 class="text-lg font-semibold text-dp-title">
            {{ editingTrace ? $t('experiment.trace.edit_title') : $t('experiment.trace.create_title') }}
          </h3>
        </div>
        <div class="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <!-- Name -->
          <div>
            <label class="block text-sm font-medium text-dp-title mb-1">{{ $t('experiment.trace.name_label') }}</label>
            <input
              v-model="form.name"
              class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
              :placeholder="$t('experiment.trace.name_placeholder')"
            />
          </div>

          <!-- API Key selection -->
          <div>
            <label class="block text-sm font-medium text-dp-title mb-1">{{
              $t('experiment.trace.select_apikeys')
            }}</label>
            <div v-if="apiKeys.length === 0" class="text-xs text-dp-muted py-2">
              {{ $t('experiment.trace.no_apikeys') }}
            </div>
            <div v-else class="space-y-1.5 max-h-32 overflow-y-auto">
              <label
                v-for="key in apiKeys"
                :key="key.id"
                class="flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer text-sm"
                :class="form.api_key_ids.includes(key.id) ? 'border-dp-blue bg-blue-50/50' : ''"
              >
                <input type="checkbox" :value="key.id" v-model="form.api_key_ids" class="rounded text-dp-blue" />
                <span class="font-medium text-dp-title">{{ key.name }}</span>
                <span class="text-dp-muted text-xs ml-auto">{{ key.key_prefix }}</span>
              </label>
            </div>
          </div>

          <!-- Model selection (search dropdown) -->
          <div>
            <label class="block text-sm font-medium text-dp-title mb-1">{{
              $t('experiment.trace.select_models')
            }}</label>
            <p class="text-xs text-dp-muted mb-2">{{ $t('experiment.trace.models_hint') }}</p>

            <!-- Search dropdown -->
            <div class="relative" ref="modelDropdownRef">
              <button
                type="button"
                class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-sm text-left focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
                :class="
                  modelDropdownOpen ? 'border-dp-blue ring-2 ring-blue-100 bg-white' : 'border-slate-300 bg-white'
                "
                @click="modelDropdownOpen = !modelDropdownOpen"
              >
                <span class="text-dp-muted truncate">{{ $t('experiment.trace.models_search_placeholder') }}</span>
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
                  class="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
                >
                  <!-- Search input inside dropdown -->
                  <li class="sticky top-0 bg-white px-2 py-1.5 border-b border-slate-100">
                    <input
                      v-model="modelSearchQuery"
                      type="text"
                      :placeholder="$t('experiment.trace.models_search_input')"
                      class="w-full px-3 py-1.5 rounded-md border border-slate-200 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-400"
                      @click.stop
                    />
                  </li>
                  <li
                    v-for="model in filteredModels"
                    :key="model.id"
                    class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50"
                    :class="form.model_names.includes(model.id) ? 'bg-blue-50/60' : 'text-dp-body'"
                    @click="toggleModel(model.id)"
                  >
                    <div class="flex-1 min-w-0">
                      <div
                        class="truncate"
                        :class="form.model_names.includes(model.id) ? 'text-dp-blue font-medium' : ''"
                      >
                        {{ model.id }}
                      </div>
                      <div class="flex flex-wrap items-center gap-1 mt-0.5">
                        <span
                          v-for="tag in model.tags || []"
                          :key="tag"
                          class="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0 text-[10px] text-slate-500"
                          >{{ tag }}</span
                        >
                      </div>
                    </div>
                    <span
                      class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none"
                      :class="vendorTypeTagClass(model.vendor_type)"
                      >{{ model.vendor_type }}</span
                    >
                    <!-- Checkmark for selected -->
                    <svg
                      v-if="form.model_names.includes(model.id)"
                      class="w-4 h-4 text-dp-blue shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </li>
                  <li v-if="filteredModels.length === 0" class="px-3 py-3 text-xs text-dp-muted text-center">
                    {{ $t('experiment.trace.no_models_found') }}
                  </li>
                </ul>
              </Transition>
            </div>

            <!-- Selected model tags -->
            <div v-if="form.model_names.length" class="flex flex-wrap gap-1.5 mt-2">
              <span
                v-for="(m, i) in form.model_names"
                :key="i"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-blue-50 text-xs text-dp-blue font-medium"
              >
                {{ m }}
                <button
                  class="text-dp-blue/50 hover:text-red-500 transition-colors"
                  @click="form.model_names.splice(i, 1)"
                >
                  &times;
                </button>
              </span>
            </div>
          </div>

          <!-- Storage Engine Selection -->
          <div>
            <label class="block text-sm font-medium text-dp-title mb-1.5">{{
              $t('experiment.trace.storage_engine')
            }}</label>
            <div class="flex gap-2">
              <button
                v-if="builtinAvailable"
                type="button"
                class="flex-1 px-3 py-2.5 rounded-lg border text-sm font-medium transition-all"
                :class="
                  form.storage_type === 'builtin'
                    ? 'border-dp-blue bg-blue-50 text-dp-blue shadow-sm'
                    : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                "
                @click="form.storage_type = 'builtin'"
              >
                <div class="flex items-center justify-center gap-1.5">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"
                    />
                  </svg>
                  {{ $t('experiment.trace.storage_builtin') }}
                </div>
                <p class="text-[10px] mt-0.5 font-normal opacity-70">
                  {{ $t('experiment.trace.storage_builtin_desc') }}
                </p>
              </button>
              <button
                type="button"
                class="flex-1 px-3 py-2.5 rounded-lg border text-sm font-medium transition-all"
                :class="
                  form.storage_type === 'external'
                    ? 'border-dp-blue bg-blue-50 text-dp-blue shadow-sm'
                    : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                "
                @click="form.storage_type = 'external'"
              >
                <div class="flex items-center justify-center gap-1.5">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
                    />
                  </svg>
                  {{ $t('experiment.trace.storage_external') }}
                </div>
                <p class="text-[10px] mt-0.5 font-normal opacity-70">
                  {{ $t('experiment.trace.storage_external_desc') }}
                </p>
              </button>
            </div>
          </div>

          <!-- Database config (only shown for external storage) -->
          <div v-if="form.storage_type === 'external'">
            <label class="block text-sm font-medium text-dp-title mb-1">{{ $t('experiment.trace.db_config') }}</label>
            <div class="mb-3">
              <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.db_type') }}</label>
              <select
                :value="form.db_type"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-dp-blue/40 focus:border-dp-blue appearance-none bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2216%22%20height%3D%2216%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2394a3b8%22%20stroke-width%3D%222%22%3E%3Cpath%20d%3D%22M6%209l6%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-[length:16px] bg-[right_12px_center] bg-no-repeat"
                @change="onDBTypeChange(($event.target as HTMLSelectElement).value)"
              >
                <option v-for="dbOpt in dbOptions" :key="dbOpt.value" :value="dbOpt.value">
                  {{ dbOpt.label }}
                </option>
              </select>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.db_host') }}</label>
                <input
                  v-model.trim="form.db_host"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
                  :placeholder="$t('experiment.trace.db_host_placeholder')"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.db_port') }}</label>
                <input
                  v-model.number="form.db_port"
                  type="number"
                  min="1"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
                  :placeholder="String(defaultPortForDBType(form.db_type))"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.db_user') }}</label>
                <input
                  v-model.trim="form.db_user"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
                  :placeholder="$t('experiment.trace.db_user_placeholder')"
                />
              </div>
              <div>
                <label class="block text-xs font-medium text-dp-muted mb-1">{{
                  $t('experiment.trace.db_password')
                }}</label>
                <input
                  v-model="form.db_password"
                  type="password"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
                  :placeholder="
                    editingTrace
                      ? $t('experiment.trace.db_password_keep')
                      : $t('experiment.trace.db_password_placeholder')
                  "
                />
              </div>
              <div class="col-span-2">
                <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.db_name') }}</label>
                <input
                  v-model.trim="form.db_name"
                  class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
                  :placeholder="$t('experiment.trace.db_name_placeholder')"
                />
              </div>
            </div>

            <p class="mt-2 text-xs text-dp-muted">{{ $t('experiment.trace.db_password_hint') }}</p>
            <p v-if="dbConnectionPreview" class="mt-1 text-xs text-dp-muted font-mono">
              {{ $t('experiment.trace.db_preview') }}: <span class="text-dp-title">{{ dbConnectionPreview }}</span>
            </p>

            <button
              class="mt-3 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 text-dp-muted hover:text-dp-title hover:border-slate-300 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="testing || !canTestConnection"
              @click="testConnection"
            >
              {{ testing ? $t('experiment.trace.testing') : $t('experiment.trace.test_connection') }}
            </button>
            <span
              v-if="testResult !== null"
              class="ml-2 text-xs"
              :class="testResult ? 'text-green-600' : 'text-red-500'"
            >
              {{ testResult ? $t('experiment.trace.test_pass') : testError }}
            </span>
          </div>
        </div>
        <div class="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg text-sm font-medium text-dp-muted hover:text-dp-title transition-colors"
            @click="showDialog = false"
          >
            {{ $t('experiment.trace.cancel') }}
          </button>
          <button
            class="px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all shadow-sm"
            :disabled="submitting"
            @click="submitForm"
          >
            {{ submitting ? '...' : editingTrace ? $t('experiment.trace.save') : $t('experiment.trace.confirm') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div
      v-if="deleteTarget"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      @click.self="deleteTarget = null"
    >
      <div class="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <p class="text-sm text-dp-title mb-4">
          {{ $t('experiment.trace.delete_confirm', { name: deleteTarget.name }) }}
        </p>
        <div class="flex justify-end gap-3">
          <button class="px-4 py-2 rounded-lg text-sm text-dp-muted hover:text-dp-title" @click="deleteTarget = null">
            {{ $t('experiment.trace.cancel') }}
          </button>
          <button
            class="px-4 py-2 rounded-lg text-sm font-medium bg-red-500 text-white hover:bg-red-600 transition-colors"
            @click="doDelete"
          >
            {{ $t('experiment.trace.delete') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  listTraces,
  createTrace as apiCreateTrace,
  updateTraceStatus,
  updateTrace as apiUpdateTrace,
  deleteTrace as apiDeleteTrace,
  testDBConnection,
  getTraceStorageOptions,
  type TraceConfig,
} from '@/api/experiment'
import { listAPIKeys, type APIKey } from '@/api/apikey'
import { listCustomModels } from '@/api/custom-model'

const { t } = useI18n()
const router = useRouter()

const traces = ref<TraceConfig[]>([])
const apiKeys = ref<APIKey[]>([])
const loading = ref(true)
const showDialog = ref(false)
const submitting = ref(false)
const editingTrace = ref<TraceConfig | null>(null) // null = create mode, non-null = edit mode
const testing = ref(false)
const testResult = ref<boolean | null>(null)
const testError = ref('')
const deleteTarget = ref<TraceConfig | null>(null)
const builtinAvailable = ref(false)

// --- Model dropdown state (search + multi-select) ---

interface ModelOption {
  id: string
  vendor_type?: string
  model_family?: string
  tags?: string[]
}

const allModels = ref<ModelOption[]>([])
const modelDropdownOpen = ref(false)
const modelDropdownRef = ref<HTMLElement>()
const modelSearchQuery = ref('')

const filteredModels = computed(() => {
  const q = modelSearchQuery.value.trim().toLowerCase()
  if (!q) return allModels.value
  return allModels.value.filter((m) => m.id.toLowerCase().includes(q))
})

/** Toggle a model in/out of the selected list. */
function toggleModel(id: string) {
  const idx = form.model_names.indexOf(id)
  if (idx >= 0) {
    form.model_names.splice(idx, 1)
  } else {
    form.model_names.push(id)
  }
}

function vendorTypeTagClass(vendorType?: string): string {
  switch (vendorType) {
    case 'hybrid':
      return 'bg-purple-100 text-purple-700'
    case 'provider':
      return 'bg-emerald-100 text-emerald-700'
    case 'deepnode':
      return 'bg-blue-100 text-blue-700'
    default:
      return 'bg-slate-100 text-slate-500'
  }
}

/** Click outside handler to close dropdown. */
function handleClickOutside(e: MouseEvent) {
  if (modelDropdownRef.value && !modelDropdownRef.value.contains(e.target as Node)) {
    modelDropdownOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

/** Fetch available models from gateway /v1/models + user custom models. */
async function fetchModels() {
  try {
    const token = localStorage.getItem('dp_token')
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    // Gateway models endpoint is at /v1/models (not under /api/v1)
    const gatewayBase = baseUrl.replace(/\/api\/v1\/?$/, '/v1')

    // Fetch platform models and user custom models in parallel
    const [gatewayRes, customRes] = await Promise.allSettled([
      fetch(`${gatewayBase}/models`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      }),
      listCustomModels(),
    ])

    const models: ModelOption[] = []

    // Platform models from gateway
    if (gatewayRes.status === 'fulfilled' && gatewayRes.value.ok) {
      const json = await gatewayRes.value.json()
      const items = Array.isArray(json?.data) ? json.data : []
      for (const item of items) {
        const id = String(item.id || '').trim()
        if (id) {
          models.push({
            id,
            vendor_type: String(item.vendor_type || ''),
            model_family: String(item.model_family || ''),
            tags: Array.isArray(item.tags) ? item.tags : [],
          })
        }
      }
    }

    // User custom models (via manager API with session auth)
    if (customRes.status === 'fulfilled') {
      const customModels = customRes.value.data?.data || []
      for (const cm of customModels) {
        if (cm.enabled && !models.some((m) => m.id === cm.model_name)) {
          models.push({
            id: cm.model_name,
            vendor_type: cm.vendor_type || 'provider',
            model_family: cm.model_family || '',
            tags: [...(cm.tags || []), 'custom'],
          })
        }
      }
    }

    allModels.value = models.sort((a, b) => a.id.localeCompare(b.id))
  } catch {
    // Silent — models list is optional for trace creation
  }
}

// --- End model dropdown ---

const dbOptions = [
  { value: 'mysql', label: 'MySQL' },
  { value: 'postgresql', label: 'PostgreSQL' },
  { value: 'clickhouse', label: 'ClickHouse' },
]

const form = reactive({
  name: '',
  api_key_ids: [] as number[],
  model_names: [] as string[],
  storage_type: 'builtin' as 'builtin' | 'external',
  db_type: 'mysql',
  db_host: '',
  db_port: 3306,
  db_user: '',
  db_password: '',
  db_name: '',
})

function defaultPortForDBType(dbType: string): number {
  switch (dbType) {
    case 'postgresql':
      return 5432
    case 'clickhouse':
      return 9000
    default:
      return 3306
  }
}

function onDBTypeChange(dbType: string) {
  form.db_type = dbType
  form.db_port = defaultPortForDBType(dbType)
  testResult.value = null
  testError.value = ''
}

const canTestConnection = computed(() => {
  return Boolean(form.db_host.trim() && form.db_port > 0 && form.db_user.trim() && form.db_name.trim())
})

const dbConnectionPreview = computed(() => {
  const host = form.db_host.trim()
  const user = form.db_user.trim()
  const dbName = form.db_name.trim()
  if (!host || !dbName) return ''
  const port = form.db_port > 0 ? form.db_port : defaultPortForDBType(form.db_type)
  return `${user ? `${user}@` : ''}${host}:${port}/${dbName}`
})

onMounted(async () => {
  try {
    const [tracesRes, keysRes, , storageRes] = await Promise.allSettled([
      listTraces(),
      listAPIKeys(),
      fetchModels(),
      getTraceStorageOptions(),
    ])
    if (tracesRes.status === 'fulfilled') {
      traces.value = tracesRes.value.data?.data || []
    }
    if (keysRes.status === 'fulfilled') {
      apiKeys.value = keysRes.value.data?.data || []
    }
    if (storageRes.status === 'fulfilled') {
      builtinAvailable.value = storageRes.value.data?.data?.builtin_available ?? false
    }
    // Default to external if builtin is not available
    if (!builtinAvailable.value) {
      form.storage_type = 'external'
    }
  } finally {
    loading.value = false
  }
})

async function testConnection() {
  if (!canTestConnection.value) return
  testing.value = true
  testResult.value = null
  testError.value = ''
  try {
    const res = await testDBConnection({
      db_type: form.db_type,
      db_host: form.db_host.trim(),
      db_port: form.db_port,
      db_user: form.db_user.trim(),
      db_password: form.db_password,
      db_name: form.db_name.trim(),
    })
    if (res.data?.code === 0) {
      testResult.value = true
    } else {
      testResult.value = false
      testError.value = res.data?.message || 'Connection failed'
    }
  } catch (e: any) {
    testResult.value = false
    testError.value = e.response?.data?.message || 'Connection failed'
  } finally {
    testing.value = false
  }
}

/** Open dialog in create mode */
function openCreate() {
  resetForm()
  editingTrace.value = null
  showDialog.value = true
}

/** Navigate to trace logs view */
function viewLogs(trace: TraceConfig) {
  router.push({ name: 'ExperimentTraceLogs', params: { traceId: String(trace.id) }, query: { name: trace.name } })
}

/** Open dialog in edit mode, pre-filling form from existing trace */
function openEdit(trace: TraceConfig) {
  resetForm()
  editingTrace.value = trace
  form.name = trace.name
  form.api_key_ids = [...(trace.api_key_ids || [])]
  form.model_names = [...(trace.model_names || [])]
  form.storage_type = (trace.storage_type as 'builtin' | 'external') || 'external'
  form.db_type = trace.db_type || 'mysql'
  form.db_host = trace.db_host || ''
  form.db_port = trace.db_port || defaultPortForDBType(form.db_type)
  form.db_user = trace.db_user || ''
  form.db_name = trace.db_name || ''
  // Password is never returned by the backend — user must re-enter if changing DB config
  showDialog.value = true
}

/** Unified submit: delegates to create or update based on editingTrace */
async function submitForm() {
  if (editingTrace.value) {
    await doUpdateTrace()
  } else {
    await doCreateTrace()
  }
}

async function doCreateTrace() {
  if (!form.name.trim() || form.api_key_ids.length === 0) return
  // For external storage, validate DB fields
  if (form.storage_type === 'external' && !canTestConnection.value) return

  submitting.value = true
  try {
    const params: Record<string, any> = {
      name: form.name.trim(),
      api_key_ids: form.api_key_ids,
      model_names: form.model_names,
      storage_type: form.storage_type,
    }
    if (form.storage_type === 'external') {
      params.db_type = form.db_type
      params.db_host = form.db_host.trim()
      params.db_port = form.db_port
      params.db_user = form.db_user.trim()
      params.db_password = form.db_password
      params.db_name = form.db_name.trim()
    }

    const res = await apiCreateTrace(params as any)
    if (res.data?.data) {
      traces.value.unshift(res.data.data)
    }
    showDialog.value = false
    resetForm()
  } catch (e: any) {
    alert(e.response?.data?.message || 'Create failed')
  } finally {
    submitting.value = false
  }
}

async function doUpdateTrace() {
  if (!editingTrace.value || !form.name.trim() || form.api_key_ids.length === 0) return
  submitting.value = true
  try {
    const params: Record<string, any> = {
      name: form.name.trim(),
      api_key_ids: form.api_key_ids,
      model_names: form.model_names,
      // Always send DB config fields (pre-filled from existing config).
      // Empty db_password means keep the existing password on the server side.
      db_type: form.db_type,
      db_host: form.db_host.trim(),
      db_port: form.db_port,
      db_user: form.db_user.trim(),
      db_name: form.db_name.trim(),
    }
    // Only include db_password when user explicitly entered a new one
    if (form.db_password) {
      params.db_password = form.db_password
    }
    const res = await apiUpdateTrace(editingTrace.value.id, params)
    if (res.data?.data) {
      // Update the trace in-place in the list
      const idx = traces.value.findIndex((t) => t.id === editingTrace.value!.id)
      if (idx >= 0) {
        traces.value[idx] = res.data.data
      }
    }
    showDialog.value = false
    resetForm()
  } catch (e: any) {
    alert(e.response?.data?.message || 'Update failed')
  } finally {
    submitting.value = false
  }
}

async function toggleStatus(trace: TraceConfig, status: string) {
  try {
    await updateTraceStatus(trace.id, status)
    trace.status = status
  } catch (e: any) {
    alert(e.response?.data?.message || 'Update failed')
  }
}

function confirmDelete(trace: TraceConfig) {
  deleteTarget.value = trace
}

async function doDelete() {
  if (!deleteTarget.value) return
  try {
    await apiDeleteTrace(deleteTarget.value.id)
    traces.value = traces.value.filter((t) => t.id !== deleteTarget.value!.id)
    deleteTarget.value = null
  } catch (e: any) {
    alert(e.response?.data?.message || 'Delete failed')
  }
}

function resetForm() {
  form.name = ''
  form.api_key_ids = []
  form.model_names = []
  form.storage_type = builtinAvailable.value ? 'builtin' : 'external'
  form.db_type = 'mysql'
  form.db_host = ''
  form.db_port = 3306
  form.db_user = ''
  form.db_password = ''
  form.db_name = ''
  testResult.value = null
  testError.value = ''
  modelSearchQuery.value = ''
  modelDropdownOpen.value = false
}
</script>
