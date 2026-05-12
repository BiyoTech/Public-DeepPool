<template>
  <div>
    <!-- Breadcrumb navigation -->
    <div class="flex items-center gap-2 mb-6">
      <button
        class="flex items-center gap-1.5 text-sm text-dp-muted hover:text-dp-blue transition-colors"
        @click="$router.push('/experiment/trace')"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
        </svg>
        {{ $t('experiment.trace.logs.back') }}
      </button>
      <span class="text-slate-300">/</span>
      <h2 class="text-lg font-semibold text-dp-title">{{ traceName || $t('experiment.trace.logs.title') }}</h2>
    </div>

    <!-- Search filters -->
    <div class="bg-white rounded-xl border border-slate-200 p-4 mb-4">
      <div class="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.logs.model_name') }}</label>
          <input
            v-model.trim="filters.model_name"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.model_placeholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.logs.api_key_id') }}</label>
          <input
            v-model.trim="filters.api_key_id"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.api_key_placeholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.logs.request_id') }}</label>
          <input
            v-model.trim="filters.request_id"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.request_id_placeholder')"
          />
        </div>
      </div>
      <div class="flex items-end gap-3">
        <div class="flex-1">
          <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.logs.start_time') }}</label>
          <input
            v-model="filters.start_time"
            type="datetime-local"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
          />
        </div>
        <div class="flex-1">
          <label class="block text-xs font-medium text-dp-muted mb-1">{{ $t('experiment.trace.logs.end_time') }}</label>
          <input
            v-model="filters.end_time"
            type="datetime-local"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
          />
        </div>
        <button
          class="px-4 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all shadow-sm"
          @click="doSearch"
        >{{ $t('experiment.trace.logs.search') }}</button>
        <button
          class="px-4 py-2 rounded-lg text-sm font-medium text-dp-muted border border-slate-200 hover:text-dp-title hover:border-slate-300 transition-colors"
          @click="resetFilters"
        >{{ $t('experiment.trace.logs.reset') }}</button>
      </div>
    </div>

    <!-- Logs table -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div v-if="loading" class="text-center py-16 text-dp-muted text-sm">
        {{ $t('experiment.trace.logs.loading') }}
      </div>
      <div v-else-if="logs.length === 0" class="text-center py-16 text-dp-muted text-sm">
        {{ $t('experiment.trace.logs.empty') }}
      </div>
      <table v-else class="w-full text-sm">
        <thead class="bg-slate-50 text-dp-muted text-xs uppercase tracking-wider">
          <tr>
            <th class="px-4 py-3 text-left font-medium">{{ $t('experiment.trace.logs.col_request_id') }}</th>
            <th class="px-4 py-3 text-left font-medium">{{ $t('experiment.trace.logs.col_user_query') }}</th>
            <th class="px-4 py-3 text-left font-medium">{{ $t('experiment.trace.logs.col_model') }}</th>
            <th class="px-4 py-3 text-right font-medium">{{ $t('experiment.trace.logs.col_tokens') }}</th>
            <th class="px-4 py-3 text-right font-medium">{{ $t('experiment.trace.logs.col_duration') }}</th>
            <th class="px-4 py-3 text-center font-medium">{{ $t('experiment.trace.logs.col_status') }}</th>
            <th class="px-4 py-3 text-left font-medium">{{ $t('experiment.trace.logs.col_time') }}</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr
            v-for="log in logs"
            :key="log.id"
            class="hover:bg-blue-50/50 cursor-pointer transition-colors"
            @click="openDetail(log)"
          >
            <td class="px-4 py-3 font-mono text-xs text-dp-title" :title="log.request_id">
              {{ truncateId(log.request_id) }}
            </td>
            <td class="px-4 py-3 text-dp-muted max-w-[240px]">
              <span class="block truncate" :title="log.user_query">{{ log.user_query || '—' }}</span>
            </td>
            <td class="px-4 py-3">
              <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-dp-blue">
                {{ log.model_name }}
              </span>
            </td>
            <td class="px-4 py-3 text-right font-mono text-xs text-dp-title">{{ log.total_tokens }}</td>
            <td class="px-4 py-3 text-right font-mono text-xs text-dp-title">{{ formatDuration(log.duration_ms) }}</td>
            <td class="px-4 py-3 text-center">
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="log.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
              >
                {{ log.success ? $t('experiment.trace.logs.status_success') : $t('experiment.trace.logs.status_failed') }}
              </span>
            </td>
            <td class="px-4 py-3 text-xs text-dp-muted whitespace-nowrap">{{ formatTime(log.created_at) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="total > 0" class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
        <span class="text-xs text-dp-muted">{{ $t('experiment.trace.logs.total_records', { count: total }) }}</span>
        <div class="flex items-center gap-1">
          <button
            class="px-3 py-1 rounded text-xs font-medium border border-slate-200 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page <= 1"
            @click="goPage(page - 1)"
          >&lsaquo; Prev</button>
          <span class="px-3 py-1 text-xs text-dp-title font-medium">{{ page }} / {{ totalPages }}</span>
          <button
            class="px-3 py-1 rounded text-xs font-medium border border-slate-200 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            :disabled="page >= totalPages"
            @click="goPage(page + 1)"
          >Next &rsaquo;</button>
        </div>
      </div>
    </div>

    <!-- Log Detail Dialog -->
    <TraceLogDetailDialog
      v-if="selectedLog"
      :trace-id="Number(traceId)"
      :log="selectedLog"
      @close="selectedLog = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { getTraceLogs, type TraceLogItem } from '@/api/experiment'
import TraceLogDetailDialog from './TraceLogDetailDialog.vue'

const props = defineProps<{ traceId: string }>()
const { t } = useI18n()
const route = useRoute()

const traceName = ref('')
const logs = ref<TraceLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const selectedLog = ref<TraceLogItem | null>(null)

const filters = reactive({
  model_name: '',
  api_key_id: '',
  request_id: '',
  start_time: '',
  end_time: '',
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

onMounted(async () => {
  // Read trace name from query param (set by TraceView on navigation)
  traceName.value = (route.query.name as string) || ''
  await fetchLogs()
})

/** Fetch logs from API with current filters and pagination */
async function fetchLogs() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize,
    }
    if (filters.model_name) params.model_name = filters.model_name
    if (filters.api_key_id) params.api_key_id = Number(filters.api_key_id)
    if (filters.request_id) params.request_id = filters.request_id
    if (filters.start_time) params.start_time = new Date(filters.start_time).toISOString()
    if (filters.end_time) params.end_time = new Date(filters.end_time).toISOString()

    const res = await getTraceLogs(Number(props.traceId), params)
    if (res.data?.data) {
      logs.value = res.data.data.logs || []
      total.value = res.data.data.total || 0
    }
  } catch (e: any) {
    console.error('[TraceLogsView] fetch logs failed:', e)
    logs.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function doSearch() {
  page.value = 1
  fetchLogs()
}

function resetFilters() {
  filters.model_name = ''
  filters.api_key_id = ''
  filters.request_id = ''
  filters.start_time = ''
  filters.end_time = ''
  page.value = 1
  fetchLogs()
}

function goPage(p: number) {
  page.value = p
  fetchLogs()
}

function openDetail(log: TraceLogItem) {
  selectedLog.value = log
}

/** Truncate request ID to 12 chars + ellipsis */
function truncateId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) + '...' : id
}

/** Format duration in ms to human-readable */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

/** Format UTC timestamp to readable local time */
function formatTime(ts: string): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}
</script>
