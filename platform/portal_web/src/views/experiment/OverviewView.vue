<template>
  <div class="space-y-6">
    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-24">
      <div class="w-8 h-8 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
    </div>

    <template v-else>
      <!-- ============ Section 1: Trace Overview ============ -->
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-base font-semibold text-dp-title mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-dp-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.808-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.98 0 13.788M12 12h.008v.008H12V12z"/>
          </svg>
          {{ $t('experiment.overview.trace_section') }}
        </h2>

        <div class="grid grid-cols-3 gap-4">
          <!-- API Keys card -->
          <div class="rounded-lg border border-slate-100 bg-slate-50/50 p-4">
            <p class="text-xs font-medium text-dp-muted uppercase tracking-wide mb-2">API Keys</p>
            <div class="flex items-baseline gap-2">
              <span class="text-2xl font-bold text-dp-title">{{ stats.totalApiKeys }}</span>
              <span class="text-xs text-dp-muted">{{ $t('experiment.overview.total') }}</span>
            </div>
            <div class="mt-1.5 flex items-center gap-1.5 text-xs">
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {{ stats.tracedApiKeys }}
              </span>
              <span class="text-dp-muted">{{ $t('experiment.overview.traced') }}</span>
            </div>
          </div>

          <!-- Models card -->
          <div class="rounded-lg border border-slate-100 bg-slate-50/50 p-4">
            <p class="text-xs font-medium text-dp-muted uppercase tracking-wide mb-2">{{ $t('experiment.overview.models') }}</p>
            <div class="flex items-baseline gap-2">
              <span class="text-2xl font-bold text-dp-title">{{ stats.totalModels }}</span>
              <span class="text-xs text-dp-muted">{{ $t('experiment.overview.total') }}</span>
            </div>
            <div class="mt-1.5 flex items-center gap-3 text-xs">
              <span class="text-dp-muted">
                <b class="text-dp-title">{{ stats.customModels }}</b> {{ $t('experiment.overview.custom') }}
              </span>
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                {{ stats.tracedModels }}
              </span>
              <span class="text-dp-muted">{{ $t('experiment.overview.traced') }}</span>
            </div>
          </div>

          <!-- Traces card -->
          <div class="rounded-lg border border-slate-100 bg-slate-50/50 p-4">
            <p class="text-xs font-medium text-dp-muted uppercase tracking-wide mb-2">Traces</p>
            <div class="flex items-baseline gap-2">
              <span class="text-2xl font-bold text-dp-title">{{ stats.totalTraces }}</span>
              <span class="text-xs text-dp-muted">{{ $t('experiment.overview.total') }}</span>
            </div>
            <div class="mt-1.5 flex items-center gap-3 text-xs">
              <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-600 font-medium">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                {{ stats.runningTraces }}
              </span>
              <span class="text-dp-muted">{{ $t('experiment.overview.running') }}</span>
              <span class="text-dp-muted">
                <b class="text-slate-500">{{ stats.stoppedTraces }}</b> {{ $t('experiment.overview.stopped') }}
              </span>
            </div>
            <div class="mt-1.5 text-[11px] text-dp-muted">
              {{ $t('experiment.overview.tracking') }}:
              <b class="text-dp-title">{{ stats.tracedApiKeys }}</b> keys,
              <b class="text-dp-title">{{ stats.tracedModels }}</b> models
            </div>
          </div>
        </div>
      </div>

      <!-- ============ Section 2: Judge Overview ============ -->
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-base font-semibold text-dp-title mb-4 flex items-center gap-2">
          <svg class="w-5 h-5 text-dp-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.97zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.97z"/>
          </svg>
          {{ $t('experiment.overview.judge_section') }}
          <span class="ml-2 text-xs font-normal text-dp-muted">{{ $t('experiment.overview.judge_total', { count: judges.length }) }}</span>
        </h2>

        <div v-if="judges.length === 0" class="text-center py-10 text-sm text-dp-muted">
          {{ $t('experiment.overview.judge_empty') }}
        </div>
        <div v-else>
          <!-- Judge pass rate table -->
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-200">
                <th class="py-2.5 px-3 text-left text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_name') }}</th>
                <th class="py-2.5 px-3 text-left text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_model') }}</th>
                <th class="py-2.5 px-3 text-left text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_scorer') }}</th>
                <th class="py-2.5 px-3 text-left text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_target') }}</th>
                <th class="py-2.5 px-3 text-center text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_status') }}</th>
                <th class="py-2.5 px-3 text-right text-xs font-medium text-dp-muted">{{ $t('experiment.overview.col_pass_rate') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="j in judgeRows" :key="j.id" class="border-b border-slate-100 hover:bg-slate-50/50">
                <td class="py-2.5 px-3 font-medium text-dp-title">{{ j.name }}</td>
                <td class="py-2.5 px-3">
                  <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-dp-blue">
                    {{ j.judge_model }}
                  </span>
                </td>
                <td class="py-2.5 px-3 text-xs">
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-medium"
                    :class="j.scorer_type === 'builtin' ? 'bg-blue-50 text-blue-600' : 'bg-violet-50 text-violet-600'">
                    {{ j.scorer_type === 'builtin' ? j.scorer_name : 'Custom' }}
                  </span>
                </td>
                <td class="py-2.5 px-3 text-xs text-dp-muted">{{ targetLabel(j) }}</td>
                <td class="py-2.5 px-3 text-center">
                  <span class="px-2 py-0.5 rounded-full text-[10px] font-medium" :class="statusClass(j.status)">
                    {{ j.status }}
                  </span>
                </td>
                <td class="py-2.5 px-3 text-right">
                  <template v-if="j.latestRunPassRate !== null">
                    <span class="text-sm font-bold" :class="passRateColor(j.latestRunPassRate)">
                      {{ j.latestRunPassRate.toFixed(1) }}%
                    </span>
                    <span class="text-[10px] text-dp-muted ml-1">
                      ({{ j.latestRunCompleted }}/{{ j.latestRunTotal }})
                    </span>
                  </template>
                  <span v-else class="text-xs text-dp-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ============ Section 3: Evaluation (placeholder) ============ -->
      <div class="bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-base font-semibold text-dp-title mb-2 flex items-center gap-2">
          <svg class="w-5 h-5 text-dp-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625z"/>
          </svg>
          {{ $t('experiment.overview.eval_section') }}
          <span class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 font-normal">{{ $t('experiment.coming_soon') }}</span>
        </h2>
        <p class="text-sm text-dp-muted">{{ $t('experiment.overview.eval_placeholder') }}</p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { listTraces, listJudges, listJudgeRuns, type TraceConfig, type JudgeDTO, type JudgeRunDTO } from '@/api/experiment'
import { listAPIKeys } from '@/api/apikey'
import { listCustomModels } from '@/api/custom-model'

const { t } = useI18n()
const loading = ref(true)

// --- Trace stats ---
const stats = reactive({
  totalApiKeys: 0,
  tracedApiKeys: 0,
  totalModels: 0,
  customModels: 0,
  tracedModels: 0,
  totalTraces: 0,
  runningTraces: 0,
  stoppedTraces: 0,
})

// --- Judge data ---
const judges = ref<JudgeDTO[]>([])

interface JudgeRow extends JudgeDTO {
  latestRunPassRate: number | null
  latestRunTotal: number
  latestRunCompleted: number
}
const judgeRows = ref<JudgeRow[]>([])

onMounted(async () => {
  try {
    // Fetch all data sources in parallel
    const [keysRes, tracesRes, customRes, gatewayRes, judgesRes] = await Promise.allSettled([
      listAPIKeys(),
      listTraces(),
      listCustomModels(),
      fetchGatewayModels(),
      listJudges(),
    ])

    // --- Compute trace overview stats ---
    const apiKeys = keysRes.status === 'fulfilled' ? (keysRes.value.data?.data || []) : []
    const traces: TraceConfig[] = tracesRes.status === 'fulfilled' ? (tracesRes.value.data?.data || []) : []
    const customModels = customRes.status === 'fulfilled' ? (customRes.value.data?.data || []) : []
    const gatewayModels: string[] = gatewayRes.status === 'fulfilled' ? (gatewayRes.value || []) : []

    stats.totalApiKeys = apiKeys.length

    // Collect all unique model names (gateway + custom)
    const allModelNames = new Set<string>()
    for (const m of gatewayModels) allModelNames.add(m)
    for (const cm of customModels) if (cm.model_name) allModelNames.add(cm.model_name)
    stats.totalModels = allModelNames.size
    stats.customModels = customModels.length

    // Compute traced API keys and models from trace configs
    const tracedKeySet = new Set<number>()
    const tracedModelSet = new Set<string>()
    for (const tr of traces) {
      for (const kid of (tr.api_key_ids || [])) tracedKeySet.add(kid)
      for (const mn of (tr.model_names || [])) tracedModelSet.add(mn)
      // Empty model_names means "all models" — count all gateway models
      if (!tr.model_names?.length) {
        for (const m of allModelNames) tracedModelSet.add(m)
      }
    }
    stats.tracedApiKeys = tracedKeySet.size
    stats.tracedModels = tracedModelSet.size
    stats.totalTraces = traces.length
    stats.runningTraces = traces.filter(t => t.status === 'running').length
    stats.stoppedTraces = traces.filter(t => t.status === 'stopped').length

    // --- Judge overview: fetch latest run for each judge ---
    const rawJudges = judgesRes.status === 'fulfilled' ? (judgesRes.value.data?.data || []) : []
    judges.value = rawJudges

    // Fetch latest run pass_rate for each judge in parallel
    const runsPromises = rawJudges.map(j => listJudgeRuns(j.id).catch(() => null))
    const runsResults = await Promise.allSettled(runsPromises)

    judgeRows.value = rawJudges.map((j, idx) => {
      let latestRunPassRate: number | null = null
      let latestRunTotal = 0
      let latestRunCompleted = 0

      const runsRes = runsResults[idx]
      if (runsRes.status === 'fulfilled' && runsRes.value) {
        const runs: JudgeRunDTO[] = runsRes.value.data?.data || []
        // Runs are ordered by created_at DESC, first one is latest
        const latestRun = runs.find(r => r.status === 'completed')
        if (latestRun) {
          latestRunPassRate = latestRun.pass_rate
          latestRunTotal = latestRun.total_count
          latestRunCompleted = latestRun.completed_count
        }
      }

      return { ...j, latestRunPassRate, latestRunTotal, latestRunCompleted }
    })
  } finally {
    loading.value = false
  }
})

/** Fetch model IDs from gateway /v1/models */
async function fetchGatewayModels(): Promise<string[]> {
  const gatewayBaseUrl = import.meta.env.VITE_GATEWAY_BASE_URL || (window.location.origin + '/v1')
  try {
    const res = await fetch(`${gatewayBaseUrl}/models`)
    if (!res.ok) return []
    const json = await res.json()
    const items = Array.isArray(json?.data) ? json.data : []
    return items.map((m: any) => String(m?.id || '').trim()).filter(Boolean)
  } catch {
    return []
  }
}

function targetLabel(j: JudgeDTO): string {
  if (j.scope === 'trace_log') return `Logs: ${j.scope_value}`
  if (j.scope === 'model') return `Model: ${j.scope_value}`
  if (j.scope === 'apikey') return `Key: ${j.scope_value}`
  if (j.trace_id) return `Trace #${j.trace_id}`
  return 'All'
}

function statusClass(status: string): string {
  switch (status) {
    case 'pending': return 'bg-slate-100 text-slate-600'
    case 'running': return 'bg-amber-100 text-amber-700'
    case 'completed': return 'bg-emerald-100 text-emerald-700'
    case 'failed': return 'bg-red-100 text-red-600'
    default: return 'bg-slate-100 text-slate-500'
  }
}

function passRateColor(rate: number): string {
  if (rate >= 80) return 'text-emerald-600'
  if (rate >= 50) return 'text-amber-600'
  return 'text-red-500'
}
</script>
