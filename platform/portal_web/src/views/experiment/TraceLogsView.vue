<template>
  <div>
    <!-- Breadcrumb navigation -->
    <div class="flex items-center gap-2 mb-6">
      <button
        class="flex items-center gap-1.5 text-sm text-dp-muted hover:text-dp-blue transition-colors"
        @click="$router.push('/experiment/trace')"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
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
          <label class="block text-xs font-medium text-dp-muted mb-1">{{
            $t('experiment.trace.logs.model_name')
          }}</label>
          <input
            v-model.trim="filters.model_name"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.model_placeholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-dp-muted mb-1">{{
            $t('experiment.trace.logs.api_key_id')
          }}</label>
          <input
            v-model.trim="filters.api_key_id"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.api_key_placeholder')"
          />
        </div>
        <div>
          <label class="block text-xs font-medium text-dp-muted mb-1">{{
            $t('experiment.trace.logs.request_id')
          }}</label>
          <input
            v-model.trim="filters.request_id"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-dp-blue/40"
            :placeholder="$t('experiment.trace.logs.request_id_placeholder')"
          />
        </div>
      </div>
      <div class="flex items-end gap-3">
        <div class="flex-1">
          <label class="block text-xs font-medium text-dp-muted mb-1">{{
            $t('experiment.trace.logs.start_time')
          }}</label>
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
        >
          {{ $t('experiment.trace.logs.search') }}
        </button>
        <button
          class="px-4 py-2 rounded-lg text-sm font-medium text-dp-muted border border-slate-200 hover:text-dp-title hover:border-slate-300 transition-colors"
          @click="resetFilters"
        >
          {{ $t('experiment.trace.logs.reset') }}
        </button>
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
            <th class="px-4 py-3 text-center font-medium">{{ $t('experiment.trace.logs.col_feedback') }}</th>
            <th class="px-4 py-3 text-center font-medium">{{ $t('experiment.trace.logs.col_expectation') }}</th>
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
              <span
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-dp-blue"
              >
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
                {{
                  log.success ? $t('experiment.trace.logs.status_success') : $t('experiment.trace.logs.status_failed')
                }}
              </span>
            </td>
            <td class="px-4 py-3 text-center">
              <span v-if="!annotationMap[log.id]" class="text-xs text-dp-muted">{{
                $t('experiment.trace.logs.feedback_none')
              }}</span>
              <span
                v-else-if="annotationMap[log.id].has_feedback"
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                :class="
                  annotationMap[log.id].feedback_passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                "
              >
                {{
                  annotationMap[log.id].feedback_passed
                    ? $t('experiment.trace.logs.feedback_all_passed')
                    : $t('experiment.trace.logs.feedback_has_failed')
                }}
                <span class="ml-1 text-[10px] opacity-70">({{ annotationMap[log.id].feedback_count }})</span>
              </span>
              <span v-else class="text-xs text-dp-muted">{{ $t('experiment.trace.logs.feedback_none') }}</span>
            </td>
            <td class="px-4 py-3 text-center">
              <span
                v-if="annotationMap[log.id]?.has_expectation"
                class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-dp-blue"
                >{{ $t('experiment.trace.logs.expectation_yes') }}</span
              >
              <span v-else class="text-xs text-dp-muted">{{ $t('experiment.trace.logs.expectation_none') }}</span>
            </td>
            <td class="px-4 py-3 text-xs text-dp-muted whitespace-nowrap">{{ formatTime(log.created_at) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Infinite scroll sentinel -->
      <div v-if="logs.length > 0 && hasMore" ref="scrollSentinel" class="flex justify-center py-4">
        <div
          v-if="loadingMore"
          class="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"
        ></div>
        <span v-else class="text-xs text-dp-muted">Scroll to load more</span>
      </div>
      <div v-if="logs.length > 0 && !hasMore" class="text-center py-3 text-xs text-dp-muted">— End —</div>
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
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { getTraceLogs, batchGetAnnotationSummaries, type TraceLogItem, type AnnotationSummary } from '@/api/experiment'
import TraceLogDetailDialog from './TraceLogDetailDialog.vue'

const props = defineProps<{ traceId: string }>()
const { t } = useI18n()
const route = useRoute()

const traceName = ref('')
const logs = ref<TraceLogItem[]>([])
const page = ref(1)
const pageSize = 30
const hasMore = ref(false)
const loading = ref(true)
const loadingMore = ref(false)
const selectedLog = ref<TraceLogItem | null>(null)
const annotationMap = ref<Record<number, AnnotationSummary>>({})
const scrollSentinel = ref<HTMLElement | null>(null)

let observer: IntersectionObserver | null = null

const filters = reactive({
  model_name: '',
  api_key_id: '',
  request_id: '',
  start_time: '',
  end_time: '',
})

onMounted(async () => {
  traceName.value = (route.query.name as string) || ''
  await fetchLogs()
  setupObserver()
})

onBeforeUnmount(() => {
  observer?.disconnect()
})

// Re-attach observer when sentinel element appears
watch(scrollSentinel, () => {
  setupObserver()
})

function setupObserver() {
  observer?.disconnect()
  if (!scrollSentinel.value) return
  observer = new IntersectionObserver(
    (entries) => {
      if (entries[0]?.isIntersecting && hasMore.value && !loadingMore.value) {
        loadMore()
      }
    },
    { threshold: 0.1 },
  )
  observer.observe(scrollSentinel.value)
}

/** Fetch first page of logs */
async function fetchLogs() {
  loading.value = true
  page.value = 1
  logs.value = []
  annotationMap.value = {}
  try {
    const data = await doFetch(1)
    logs.value = data.logs
    hasMore.value = data.has_more
    if (logs.value.length > 0) {
      fetchAnnotationSummaries(logs.value.map((l) => l.id))
    }
  } finally {
    loading.value = false
    await nextTick()
    setupObserver()
  }
}

/** Load next page and append */
async function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  loadingMore.value = true
  try {
    const nextPage = page.value + 1
    const data = await doFetch(nextPage)
    if (data.logs.length > 0) {
      page.value = nextPage
      logs.value.push(...data.logs)
      hasMore.value = data.has_more
      // Fetch annotation summaries for newly loaded logs
      fetchAnnotationSummaries(data.logs.map((l) => l.id))
    } else {
      hasMore.value = false
    }
  } finally {
    loadingMore.value = false
  }
}

/** Execute API call for a specific page */
async function doFetch(p: number): Promise<{ logs: TraceLogItem[]; has_more: boolean }> {
  const params: Record<string, any> = { page: p, page_size: pageSize }
  if (filters.model_name) params.model_name = filters.model_name
  if (filters.api_key_id) params.api_key_id = Number(filters.api_key_id)
  if (filters.request_id) params.request_id = filters.request_id
  if (filters.start_time) params.start_time = new Date(filters.start_time).toISOString()
  if (filters.end_time) params.end_time = new Date(filters.end_time).toISOString()

  const res = await getTraceLogs(Number(props.traceId), params)
  const d = res.data?.data
  return { logs: d?.logs || [], has_more: d?.has_more ?? false }
}

/** Fetch annotation summaries for a batch of log IDs (non-blocking) */
async function fetchAnnotationSummaries(logIds: number[]) {
  try {
    const res = await batchGetAnnotationSummaries(Number(props.traceId), logIds)
    if (res.data?.data) {
      const raw = res.data.data
      for (const [key, val] of Object.entries(raw)) {
        annotationMap.value[Number(key)] = val
      }
    }
  } catch (e: any) {
    console.error('[TraceLogsView] fetch annotation summaries failed:', e)
  }
}

function doSearch() {
  fetchLogs()
}

function resetFilters() {
  filters.model_name = ''
  filters.api_key_id = ''
  filters.request_id = ''
  filters.start_time = ''
  filters.end_time = ''
  fetchLogs()
}

function openDetail(log: TraceLogItem) {
  selectedLog.value = log
}

function truncateId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) + '...' : id
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatTime(ts: string): string {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}
</script>
