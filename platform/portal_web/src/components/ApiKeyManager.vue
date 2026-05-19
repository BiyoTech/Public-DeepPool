<template>
  <div class="max-w-6xl mx-auto">
    <!-- API Key Detail View -->
    <div v-if="detailKey" class="bg-white rounded-2xl shadow-sm border border-slate-100">
      <!-- Detail header -->
      <div class="flex items-center gap-3 px-6 py-4 border-b border-slate-100">
        <button @click="detailKey = null" class="p-1 rounded-lg hover:bg-slate-100 transition">
          <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
        <div class="flex-1 min-w-0">
          <h2 class="text-lg font-bold text-dp-title truncate">{{ detailKey.name }}</h2>
          <div class="text-xs text-dp-muted font-mono">{{ detailKey.key_prefix }}••••••</div>
        </div>
        <button
          @click="handleCopyStoredKey(detailKey.id)"
          class="px-3 py-1.5 rounded-lg border border-slate-200 text-xs text-dp-blue hover:bg-blue-50 transition-colors"
        >
          {{ $t('service.apikey.copy') }}
        </button>
      </div>

      <!-- Detail inner tabs -->
      <div class="flex border-b border-slate-100 px-6">
        <button
          @click="detailTab = 'settings'"
          class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="
            detailTab === 'settings'
              ? 'border-dp-blue text-dp-blue'
              : 'border-transparent text-dp-muted hover:text-dp-body'
          "
        >
          {{ $t('service.apikey.tab_settings') }}
        </button>
        <button
          @click="switchDetailTab('data')"
          class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="
            detailTab === 'data' ? 'border-dp-blue text-dp-blue' : 'border-transparent text-dp-muted hover:text-dp-body'
          "
        >
          {{ $t('service.apikey.tab_data') }}
        </button>
        <button
          @click="switchDetailTab('guardrails')"
          class="px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px"
          :class="
            detailTab === 'guardrails'
              ? 'border-dp-blue text-dp-blue'
              : 'border-transparent text-dp-muted hover:text-dp-body'
          "
        >
          {{ $t('service.apikey.tab_guardrails') }}
        </button>
      </div>

      <!-- Tab: Basic Settings -->
      <div v-show="detailTab === 'settings'" class="p-6 space-y-5">
        <!-- Name -->
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1.5 block">{{ $t('service.apikey.detail_name') }}</label>
          <div class="flex gap-2">
            <input
              v-model="detailEditName"
              type="text"
              class="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <button
              @click="handleUpdateName"
              :disabled="!detailEditName.trim() || detailEditName === detailKey.name"
              class="px-3 py-2 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {{ $t('service.apikey.save') }}
            </button>
          </div>
        </div>

        <!-- Rate Limits -->
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1.5 block">{{
            $t('service.apikey.detail_rate_limit')
          }}</label>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-[10px] text-dp-placeholder block mb-1">RPM (0=∞)</label>
              <input
                v-model.number="detailEditRPM"
                type="number"
                min="0"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <div>
              <label class="text-[10px] text-dp-placeholder block mb-1">TPM (0=∞)</label>
              <input
                v-model.number="detailEditTPM"
                type="number"
                min="0"
                step="100000"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              />
            </div>
          </div>
          <div class="flex items-center justify-between mt-2">
            <p class="text-[10px] text-dp-placeholder">{{ $t('service.apikey.detail_rate_limit_hint') }}</p>
            <button
              @click="handleUpdateRateLimit"
              :disabled="detailEditRPM === detailKey.rate_limit_rpm && detailEditTPM === detailKey.rate_limit_tpm"
              class="px-3 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {{ $t('service.apikey.save') }}
            </button>
          </div>
        </div>

        <!-- Quota info -->
        <div>
          <label class="text-xs font-medium text-dp-muted mb-1.5 block">{{ $t('service.apikey.detail_quota') }}</label>
          <div v-if="detailKey.quota_total >= 0" class="flex items-center gap-3">
            <div class="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all"
                :class="
                  quotaPercent(detailKey) > 90
                    ? 'bg-red-400'
                    : quotaPercent(detailKey) > 70
                      ? 'bg-amber-400'
                      : 'bg-emerald-400'
                "
                :style="{ width: quotaPercent(detailKey) + '%' }"
              />
            </div>
            <span class="text-xs text-dp-muted shrink-0"
              >{{ formatTokens(detailKey.quota_used) }} / {{ formatTokens(detailKey.quota_total) }}</span
            >
          </div>
          <div v-else class="text-sm text-dp-muted">{{ $t('service.apikey.quota_unlimited') }}</div>
        </div>

        <!-- Meta info -->
        <div class="text-xs text-dp-placeholder space-y-1">
          <div>ID: {{ detailKey.id }}</div>
          <div>
            {{
              detailKey.last_used_at
                ? $t('service.apikey.last_used', { time: formatTime(detailKey.last_used_at) })
                : $t('service.apikey.never_used')
            }}
          </div>
        </div>
      </div>

      <!-- Tab: Data (usage charts) -->
      <div v-show="detailTab === 'data'" class="p-6">
        <!-- Date range filter -->
        <div class="flex flex-wrap items-center gap-3 mb-5">
          <input
            v-model="chartStartDate"
            type="date"
            class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
          <span class="text-dp-muted text-xs">—</span>
          <input
            v-model="chartEndDate"
            type="date"
            class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
          <button
            @click="fetchKeyUsageData"
            class="px-4 py-1.5 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors"
          >
            {{ $t('data.search') }}
          </button>
        </div>

        <!-- Summary cards -->
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-5">
          <div class="bg-slate-50 rounded-lg p-4">
            <div class="text-xs text-dp-muted mb-1">{{ $t('service.apikey.chart_requests') }}</div>
            <div class="text-xl font-bold text-dp-title">{{ chartSummary.totalRequests.toLocaleString() }}</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-4">
            <div class="text-xs text-dp-muted mb-1">{{ $t('service.apikey.chart_tokens') }}</div>
            <div class="text-xl font-bold text-dp-title">{{ formatTokens(chartSummary.totalTokens) }}</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-4">
            <div class="text-xs text-dp-muted mb-1">{{ $t('service.apikey.chart_prompt_tokens') }}</div>
            <div class="text-xl font-bold text-dp-title">{{ formatTokens(chartSummary.promptTokens) }}</div>
          </div>
          <div class="bg-slate-50 rounded-lg p-4">
            <div class="text-xs text-dp-muted mb-1">{{ $t('service.apikey.chart_completion_tokens') }}</div>
            <div class="text-xl font-bold text-dp-title">{{ formatTokens(chartSummary.completionTokens) }}</div>
          </div>
        </div>

        <!-- Charts -->
        <div v-if="chartLoading" class="text-center py-12 text-dp-muted text-sm">Loading...</div>
        <div v-else-if="chartData.length === 0" class="text-center py-12 text-dp-muted text-sm">
          {{ $t('data.empty') }}
        </div>
        <template v-else>
          <div class="mb-6">
            <h4 class="text-xs font-medium text-dp-muted mb-2">{{ $t('service.apikey.chart_requests') }}</h4>
            <div ref="requestsChartRef" style="width: 100%; height: 260px"></div>
          </div>
          <div class="mb-6">
            <h4 class="text-xs font-medium text-dp-muted mb-2">{{ $t('service.apikey.chart_tokens') }}</h4>
            <div ref="tokensChartRef" style="width: 100%; height: 260px"></div>
          </div>
          <div>
            <h4 class="text-xs font-medium text-dp-muted mb-2">{{ $t('service.apikey.chart_users') }}</h4>
            <div ref="usersChartRef" style="width: 100%; height: 260px"></div>
          </div>
        </template>
      </div>

      <!-- Tab: Guardrails -->
      <div v-show="detailTab === 'guardrails'" class="p-6">
        <!-- Output guardrail stream notice -->
        <div
          v-if="guardrailList.some((g) => g.phase === 'output' && g.enabled)"
          class="mb-4 p-3 rounded-lg bg-blue-50 border border-blue-200 flex items-start gap-2"
        >
          <svg class="w-4 h-4 text-blue-500 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <p class="text-xs text-blue-700">{{ $t('service.apikey.guardrails_output_stream_notice') }}</p>
        </div>

        <!-- Inner tabs: Rules / Results -->
        <div class="flex items-center justify-between mb-4">
          <div class="flex gap-2">
            <button
              @click="grInnerTab = 'rules'"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="
                grInnerTab === 'rules' ? 'bg-dp-blue text-white' : 'bg-slate-100 text-dp-muted hover:bg-slate-200'
              "
            >
              {{ $t('service.apikey.guardrails_title') }}
            </button>
            <button
              @click="switchGrInnerTab('results')"
              class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
              :class="
                grInnerTab === 'results' ? 'bg-dp-blue text-white' : 'bg-slate-100 text-dp-muted hover:bg-slate-200'
              "
            >
              {{ $t('service.apikey.guardrails_results_tab') }}
            </button>
          </div>
          <button
            v-if="grInnerTab === 'rules'"
            @click="openGrCreateForm()"
            class="px-3 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors"
          >
            + {{ $t('service.apikey.guardrails_add') }}
          </button>
        </div>

        <!-- Rules list -->
        <div v-if="grInnerTab === 'rules'">
          <div v-if="guardrailList.length === 0" class="text-center py-12">
            <svg
              class="w-10 h-10 text-slate-300 mx-auto mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"
              />
            </svg>
            <p class="text-sm text-dp-muted">{{ $t('service.apikey.guardrails_empty') }}</p>
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="gr in guardrailList"
              :key="gr.id"
              class="flex items-center gap-3 p-3 rounded-lg border border-slate-100 hover:border-slate-200 transition group"
            >
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-0.5">
                  <span class="text-sm font-medium text-dp-title truncate">{{ gr.name }}</span>
                  <span
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    :class="gr.phase === 'input' ? 'bg-cyan-50 text-cyan-700' : 'bg-purple-50 text-purple-700'"
                  >
                    {{
                      gr.phase === 'input'
                        ? $t('service.apikey.guardrails_phase_input')
                        : $t('service.apikey.guardrails_phase_output')
                    }}
                  </span>
                  <span
                    class="px-1.5 py-0.5 rounded text-[10px] font-medium"
                    :class="gr.action === 'block' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'"
                  >
                    {{
                      gr.action === 'block'
                        ? $t('service.apikey.guardrails_action_block')
                        : $t('service.apikey.guardrails_action_log')
                    }}
                  </span>
                </div>
                <p class="text-xs text-dp-muted truncate">{{ gr.evaluator_model }} · {{ gr.storage_type }}</p>
              </div>
              <!-- Toggle enabled -->
              <button
                @click="handleToggleGuardrail(gr)"
                class="px-2 py-1 rounded text-[10px] font-medium transition-colors"
                :class="
                  gr.enabled
                    ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                    : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                "
              >
                {{ gr.enabled ? $t('service.apikey.guardrails_enabled') : $t('service.apikey.guardrails_disabled') }}
              </button>
              <!-- Edit -->
              <button
                @click="openGrEditForm(gr)"
                class="p-1 rounded hover:bg-slate-100 transition opacity-0 group-hover:opacity-100"
              >
                <svg class="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                  />
                </svg>
              </button>
              <!-- Delete -->
              <button
                @click="handleDeleteGuardrail(gr)"
                class="p-1 rounded hover:bg-red-50 transition opacity-0 group-hover:opacity-100"
              >
                <svg class="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- Results -->
        <div v-if="grInnerTab === 'results'">
          <!-- Time range filter -->
          <div class="flex flex-wrap items-center gap-3 mb-4">
            <input
              v-model="grResultsStartTime"
              type="date"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <span class="text-dp-muted text-xs">—</span>
            <input
              v-model="grResultsEndTime"
              type="date"
              class="px-3 py-1.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
            <button
              @click="resetAndFetchGrResults"
              class="px-4 py-1.5 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors"
            >
              {{ $t('data.search') }}
            </button>
          </div>

          <!-- Initial loading -->
          <div v-if="grResultsLoading && grResultsList.length === 0" class="text-center py-12 text-dp-muted text-sm">
            Loading...
          </div>
          <!-- Empty state -->
          <div v-else-if="grResultsList.length === 0" class="text-center py-12 text-dp-muted text-sm">
            {{ $t('service.apikey.guardrails_results_empty') }}
          </div>
          <!-- Results table with scroll-based loading -->
          <div v-else>
            <div ref="grResultsScrollRef" class="overflow-y-auto max-h-[520px]" @scroll="onGrResultsScroll">
              <table class="w-full text-xs">
                <thead class="sticky top-0 bg-white z-[1]">
                  <tr class="border-b border-slate-100 text-dp-muted">
                    <th class="text-left py-2 pr-3 font-medium">{{ $t('service.apikey.guardrails_results_time') }}</th>
                    <th class="text-left py-2 pr-3 font-medium">
                      {{ $t('service.apikey.guardrails_results_request_id') }}
                    </th>
                    <th class="text-left py-2 pr-3 font-medium">{{ $t('service.apikey.guardrails_phase') }}</th>
                    <th class="text-left py-2 pr-3 font-medium">
                      {{ $t('service.apikey.guardrails_results_flagged') }}
                    </th>
                    <th class="text-left py-2 pr-3 font-medium">
                      {{ $t('service.apikey.guardrails_results_confidence') }}
                    </th>
                    <th class="text-left py-2 pr-3 font-medium">
                      {{ $t('service.apikey.guardrails_results_blocked') }}
                    </th>
                    <th class="text-left py-2 pr-3 font-medium">
                      {{ $t('service.apikey.guardrails_results_duration') }}
                    </th>
                    <th class="text-left py-2 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="res in grResultsList" :key="res.id" class="border-b border-slate-50 hover:bg-slate-50">
                    <td class="py-2 pr-3 text-dp-muted whitespace-nowrap">{{ res.created_at }}</td>
                    <td class="py-2 pr-3 font-mono text-dp-body max-w-[120px]">
                      <span
                        class="inline-flex items-center gap-1 cursor-pointer hover:text-dp-blue transition-colors"
                        :title="res.request_id"
                        @click="copyRequestId(res.request_id)"
                      >
                        {{ res.request_id.slice(0, 12) }}…
                        <svg
                          class="w-3 h-3 text-slate-400 shrink-0"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                          stroke-width="2"
                        >
                          <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
                          />
                        </svg>
                      </span>
                    </td>
                    <td class="py-2 pr-3">
                      <span
                        class="px-1.5 py-0.5 rounded text-[10px] font-medium"
                        :class="res.phase === 'input' ? 'bg-cyan-50 text-cyan-700' : 'bg-purple-50 text-purple-700'"
                        >{{ res.phase }}</span
                      >
                    </td>
                    <td class="py-2 pr-3">
                      <span v-if="res.flagged" class="text-red-600 font-medium">Yes</span>
                      <span v-else class="text-emerald-600">No</span>
                    </td>
                    <td class="py-2 pr-3 text-dp-body">{{ (res.confidence * 100).toFixed(1) }}%</td>
                    <td class="py-2 pr-3">
                      <span v-if="res.blocked" class="text-red-600 font-medium">Yes</span>
                      <span v-else class="text-dp-muted">No</span>
                    </td>
                    <td class="py-2 pr-3 text-dp-muted">{{ res.duration_ms }}ms</td>
                    <td
                      class="py-2 text-dp-muted max-w-[260px] truncate"
                      :title="parseEvalReason(res.evaluator_response)"
                    >
                      {{ parseEvalReason(res.evaluator_response) }}
                    </td>
                  </tr>
                </tbody>
              </table>
              <!-- Loading more indicator -->
              <div v-if="grResultsLoadingMore" class="text-center py-3 text-dp-muted text-xs">Loading...</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Guardrail Create/Edit Slide-over -->
      <div v-if="grFormVisible" class="fixed inset-0 z-50 flex justify-end">
        <div class="absolute inset-0 bg-black/30" @click="grFormVisible = false"></div>
        <div class="relative w-full max-w-lg bg-white shadow-xl overflow-y-auto">
          <div class="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between z-10">
            <h3 class="text-base font-bold text-dp-title">
              {{
                grEditingId ? $t('service.apikey.guardrails_edit_title') : $t('service.apikey.guardrails_create_title')
              }}
            </h3>
            <button @click="grFormVisible = false" class="p-1 rounded-lg hover:bg-slate-100">
              <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="p-6 space-y-4">
            <!-- Template selector -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_template')
              }}</label>
              <select
                v-model="grFormTemplate"
                @change="onGrTemplateChange"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              >
                <option value="">{{ $t('service.apikey.guardrails_template_custom') }}</option>
                <option v-for="t in grTemplates" :key="t.name" :value="t.name">{{ t.display_name }}</option>
              </select>
            </div>
            <!-- Name -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_name')
              }}</label>
              <input
                v-model="grFormName"
                type="text"
                :placeholder="$t('service.apikey.guardrails_name_placeholder')"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              />
            </div>
            <!-- Phase -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_phase')
              }}</label>
              <div class="flex gap-2">
                <button
                  @click="grFormPhase = 'input'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormPhase === 'input'
                      ? 'border-dp-blue bg-blue-50 text-dp-blue'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_phase_input') }}
                </button>
                <button
                  @click="grFormPhase = 'output'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormPhase === 'output'
                      ? 'border-dp-blue bg-blue-50 text-dp-blue'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_phase_output') }}
                </button>
              </div>
              <!-- Output stream warning -->
              <div
                v-if="grFormPhase === 'output'"
                class="mt-2 p-2.5 rounded-lg bg-amber-50 border border-amber-200 flex items-start gap-2"
              >
                <svg
                  class="w-4 h-4 text-amber-500 mt-0.5 shrink-0"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
                  />
                </svg>
                <p class="text-xs text-amber-700">{{ $t('service.apikey.guardrails_output_stream_warning') }}</p>
              </div>
            </div>
            <!-- Action -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_action')
              }}</label>
              <div class="flex gap-2">
                <button
                  @click="grFormAction = 'block'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormAction === 'block'
                      ? 'border-red-400 bg-red-50 text-red-700'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_action_block') }}
                </button>
                <button
                  @click="grFormAction = 'log'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormAction === 'log'
                      ? 'border-amber-400 bg-amber-50 text-amber-700'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_action_log') }}
                </button>
              </div>
            </div>
            <!-- Evaluator model -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_evaluator_model')
              }}</label>
              <select
                v-model="grFormEvalModel"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              >
                <option value="" disabled>{{ $t('service.apikey.guardrails_evaluator_model_placeholder') }}</option>
                <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.id }}</option>
              </select>
            </div>
            <!-- Evaluator API Key -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_evaluator_apikey')
              }}</label>
              <select
                v-model="grFormEvalAPIKeyId"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
              >
                <option :value="0" disabled>{{ $t('service.apikey.guardrails_evaluator_apikey_placeholder') }}</option>
                <option v-for="k in apiKeys" :key="k.id" :value="k.id">{{ k.name }} ({{ k.key_prefix }}…)</option>
              </select>
            </div>
            <!-- Prompt -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_prompt')
              }}</label>
              <textarea
                v-model="grFormPrompt"
                rows="8"
                :placeholder="$t('service.apikey.guardrails_prompt_placeholder')"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm font-mono focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 resize-y"
              ></textarea>
              <p class="text-[10px] text-dp-placeholder mt-1">{{ grFormPrompt.length }} / 5000</p>
            </div>
            <!-- Storage type -->
            <div>
              <label class="text-xs font-medium text-dp-muted mb-1 block">{{
                $t('service.apikey.guardrails_storage_type')
              }}</label>
              <div class="flex gap-2">
                <button
                  @click="grFormStorageType = 'builtin'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormStorageType === 'builtin'
                      ? 'border-dp-blue bg-blue-50 text-dp-blue'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_storage_builtin') }}
                </button>
                <button
                  @click="grFormStorageType = 'external'"
                  class="flex-1 px-3 py-2 rounded-lg text-sm font-medium border transition-colors"
                  :class="
                    grFormStorageType === 'external'
                      ? 'border-dp-blue bg-blue-50 text-dp-blue'
                      : 'border-slate-200 text-dp-muted hover:bg-slate-50'
                  "
                >
                  {{ $t('service.apikey.guardrails_storage_external') }}
                </button>
              </div>
            </div>
            <!-- External DB fields -->
            <div
              v-if="grFormStorageType === 'external'"
              class="space-y-3 p-3 rounded-lg bg-slate-50 border border-slate-100"
            >
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="text-[10px] text-dp-placeholder block mb-1">{{
                    $t('service.apikey.guardrails_db_type')
                  }}</label>
                  <select v-model="grFormDBType" class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs">
                    <option value="mysql">MySQL</option>
                    <option value="postgresql">PostgreSQL</option>
                    <option value="clickhouse">ClickHouse</option>
                  </select>
                </div>
                <div>
                  <label class="text-[10px] text-dp-placeholder block mb-1">{{
                    $t('service.apikey.guardrails_db_port')
                  }}</label>
                  <input
                    v-model.number="grFormDBPort"
                    type="number"
                    class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs"
                  />
                </div>
              </div>
              <div>
                <label class="text-[10px] text-dp-placeholder block mb-1">{{
                  $t('service.apikey.guardrails_db_host')
                }}</label>
                <input
                  v-model="grFormDBHost"
                  type="text"
                  class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs"
                />
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="text-[10px] text-dp-placeholder block mb-1">{{
                    $t('service.apikey.guardrails_db_user')
                  }}</label>
                  <input
                    v-model="grFormDBUser"
                    type="text"
                    class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs"
                  />
                </div>
                <div>
                  <label class="text-[10px] text-dp-placeholder block mb-1">{{
                    $t('service.apikey.guardrails_db_password')
                  }}</label>
                  <input
                    v-model="grFormDBPassword"
                    type="password"
                    class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs"
                  />
                </div>
              </div>
              <div>
                <label class="text-[10px] text-dp-placeholder block mb-1">{{
                  $t('service.apikey.guardrails_db_name')
                }}</label>
                <input
                  v-model="grFormDBName"
                  type="text"
                  class="w-full px-2 py-1.5 rounded border border-slate-200 text-xs"
                />
              </div>
            </div>
            <!-- Submit -->
            <button
              @click="handleGrSubmit"
              :disabled="
                grFormSubmitting ||
                !grFormName.trim() ||
                !grFormPrompt.trim() ||
                !grFormEvalModel ||
                !grFormEvalAPIKeyId
              "
              class="w-full py-2.5 rounded-xl bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {{
                grFormSubmitting ? '...' : grEditingId ? $t('service.apikey.save') : $t('service.apikey.guardrails_add')
              }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- API Key List View -->
    <div v-else class="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-bold text-dp-title">{{ $t('service.apikey.title') }}</h2>
        <button
          @click="showCreateDialog = true"
          class="px-3 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition-colors"
        >
          + {{ $t('service.apikey.create') }}
        </button>
      </div>
      <div v-if="newlyCreatedKey" class="mb-4 p-3 rounded-lg bg-green-50 border border-green-200">
        <p class="text-xs font-medium text-green-800 mb-1">{{ $t('service.apikey.created_tip') }}</p>
        <div class="flex items-center gap-2">
          <code class="flex-1 text-xs bg-green-100 px-2 py-1 rounded font-mono break-all">{{ newlyCreatedKey }}</code>
          <button
            @click="copyKey(newlyCreatedKey!)"
            class="shrink-0 text-xs text-green-700 hover:text-green-900 font-medium"
          >
            {{ $t('service.apikey.copy') }}
          </button>
        </div>
        <button @click="newlyCreatedKey = null" class="mt-2 text-xs text-green-600 hover:underline">
          {{ $t('service.apikey.dismiss') }}
        </button>
      </div>
      <div v-if="apiKeys.length === 0 && !keysLoading" class="text-center text-dp-muted text-sm py-8">
        {{ $t('service.apikey.empty') }}
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="key in apiKeys"
          :key="key.id"
          class="group flex items-center gap-3 p-3 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50/50 cursor-pointer transition-all"
          @click="openKeyDetail(key)"
        >
          <!-- Key icon -->
          <div class="shrink-0 w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center">
            <svg
              class="w-4.5 h-4.5 text-dp-blue"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
              />
            </svg>
          </div>
          <!-- Key info -->
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-dp-body truncate">{{ key.name }}</div>
            <div class="text-xs text-dp-muted font-mono">{{ key.key_prefix }}••••••</div>
          </div>
          <!-- Rate limit badge -->
          <div class="hidden sm:block text-[10px] text-dp-placeholder shrink-0">
            RPM {{ key.rate_limit_rpm === 0 ? '∞' : key.rate_limit_rpm }} · TPM
            {{ key.rate_limit_tpm === 0 ? '∞' : formatTokens(key.rate_limit_tpm) }}
          </div>
          <!-- Delete button -->
          <button
            @click.stop="handleDelete(key.id)"
            class="shrink-0 p-2 rounded-lg text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
            :title="$t('service.apikey.delete')"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
              />
            </svg>
          </button>
          <!-- Copy button -->
          <button
            @click.stop="handleCopyStoredKey(key.id)"
            class="shrink-0 p-2 rounded-lg text-slate-400 hover:text-dp-blue hover:bg-blue-50 transition-colors"
            :title="$t('service.apikey.copy')"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"
              />
            </svg>
          </button>
          <!-- Arrow -->
          <svg
            class="w-4 h-4 text-slate-300 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </div>
      </div>
    </div>

    <!-- Create API Key dialog -->
    <div
      v-if="showCreateDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
    >
      <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm mx-4">
        <h3 class="text-lg font-bold text-dp-title mb-4">{{ $t('service.apikey.create_title') }}</h3>
        <input
          v-model="newKeyName"
          type="text"
          :placeholder="$t('service.apikey.name_placeholder')"
          class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          @keydown.enter="handleCreate"
        />
        <!-- RPM/TPM settings -->
        <div class="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">RPM (0=∞)</label>
            <input
              v-model.number="newKeyRPM"
              type="number"
              min="0"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
          <div>
            <label class="text-[10px] font-medium text-dp-muted block mb-1">TPM (0=∞)</label>
            <input
              v-model.number="newKeyTPM"
              type="number"
              min="0"
              step="100000"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            />
          </div>
        </div>
        <p class="text-[10px] text-dp-placeholder mt-1.5">{{ $t('service.apikey.detail_rate_limit_hint') }}</p>
        <div class="flex gap-3 mt-4">
          <button
            @click="
              showCreateDialog = false
              newKeyName = ''
            "
            class="flex-1 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-muted hover:bg-slate-50 transition-colors"
          >
            {{ $t('service.apikey.cancel') }}
          </button>
          <button
            @click="handleCreate"
            :disabled="!newKeyName.trim() || creating"
            class="flex-1 py-2.5 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {{ creating ? '...' : $t('service.apikey.confirm') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createAPIKey,
  updateAPIKey,
  listAPIKeys,
  deleteAPIKey,
  fetchKeySecret,
  type APIKey,
  type CreateAPIKeyParams,
} from '@/api/apikey'
import { getConsumption } from '@/api/usage'
import {
  listGuardrailTemplates,
  createGuardrail,
  listGuardrails,
  updateGuardrail,
  deleteGuardrail,
  listGuardrailResults,
  type GuardrailTemplate,
  type Guardrail,
  type GuardrailResult,
  type CreateGuardrailParams,
  type UpdateGuardrailParams,
} from '@/api/guardrail'
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const { t, locale } = useI18n()

// ── Props: parent passes available models and API keys for guardrail form selectors ──
interface ModelOption {
  id: string
  vendor_type?: string
}

const props = defineProps<{
  availableModels: ModelOption[]
}>()

// ── Events emitted to parent ──
const emit = defineEmits<{
  (e: 'toast', message: string, type?: 'success' | 'info'): void
  (e: 'keysChanged', keys: APIKey[]): void
}>()

// ── API Key Management ──

const apiKeys = ref<APIKey[]>([])
const keysLoading = ref(false)
const showCreateDialog = ref(false)
const newKeyName = ref('')
const newKeyRPM = ref(60)
const newKeyTPM = ref(1000000)
const creating = ref(false)
const newlyCreatedKey = ref<string | null>(null)
const newlyCreatedKeyId = ref<number | null>(null)

// Detail view state
const detailKey = ref<APIKey | null>(null)
const detailTab = ref<'settings' | 'data' | 'guardrails'>('settings')
const detailEditName = ref('')
const detailEditRPM = ref(0)
const detailEditTPM = ref(0)

// In-memory cache for full keys fetched from server
const keySecretCache = ref<Record<string, string>>({})

// ── Data tab: chart state ──
const requestsChartRef = ref<HTMLElement>()
const tokensChartRef = ref<HTMLElement>()
const usersChartRef = ref<HTMLElement>()
let requestsChart: echarts.ECharts | null = null
let tokensChart: echarts.ECharts | null = null
let usersChart: echarts.ECharts | null = null
const chartStartDate = ref('')
const chartEndDate = ref('')
const chartLoading = ref(false)

interface ChartDataPoint {
  date: string
  requests: number
  tokens: number
  promptTokens: number
  completionTokens: number
  users: number
}
const chartData = ref<ChartDataPoint[]>([])
const chartSummary = ref({ totalRequests: 0, totalTokens: 0, promptTokens: 0, completionTokens: 0, totalUsers: 0 })

// ── Guardrail Management ──

const grInnerTab = ref<'rules' | 'results'>('rules')
const guardrailList = ref<Guardrail[]>([])
const grTemplates = ref<GuardrailTemplate[]>([])

// Results state: scroll-based loading with time range filter
const grResultsList = ref<GuardrailResult[]>([])
const grResultsHasMore = ref(false)
const grResultsLoading = ref(false)
const grResultsLoadingMore = ref(false)
const grResultsPage = ref(1)
const grResultsPageSize = 30
const grResultsStartTime = ref('')
const grResultsEndTime = ref('')
const grResultsScrollRef = ref<HTMLElement>()

// Form state
const grFormVisible = ref(false)
const grFormSubmitting = ref(false)
const grEditingId = ref<number | null>(null)
const grFormTemplate = ref('')
const grFormName = ref('')
const grFormPhase = ref<'input' | 'output'>('input')
const grFormAction = ref<'block' | 'log'>('block')
const grFormPrompt = ref('')
const grFormEvalModel = ref('')
const grFormEvalAPIKeyId = ref(0)
const grFormStorageType = ref<'builtin' | 'external'>('builtin')
const grFormDBType = ref('mysql')
const grFormDBHost = ref('')
const grFormDBPort = ref(3306)
const grFormDBUser = ref('')
const grFormDBPassword = ref('')
const grFormDBName = ref('')

// ── Exposed methods for parent to call ──

/** Fetch the full API Key from server (with in-memory cache). */
async function getFullKey(id: number): Promise<string | null> {
  const cached = keySecretCache.value[String(id)]
  if (cached) return cached

  try {
    const res = await fetchKeySecret(id)
    const fullKey = res.data?.data?.full_key
    if (fullKey) {
      keySecretCache.value[String(id)] = fullKey
      return fullKey
    }
  } catch (err) {
    console.error('[ApiKeyManager] fetch key secret failed', err)
  }
  return null
}

/** Fetch API Key list and notify parent. */
async function fetchKeys() {
  keysLoading.value = true
  try {
    const res = await listAPIKeys()
    apiKeys.value = res.data?.data || []
    emit('keysChanged', apiKeys.value)
  } catch (err) {
    console.error('[ApiKeyManager] fetch keys failed', err)
  } finally {
    keysLoading.value = false
  }
}

async function handleCreate() {
  if (!newKeyName.value.trim() || creating.value) return

  creating.value = true
  try {
    const params: CreateAPIKeyParams = { name: newKeyName.value.trim() }
    if (newKeyRPM.value !== 60) params.rate_limit_rpm = newKeyRPM.value
    if (newKeyTPM.value !== 1000000) params.rate_limit_tpm = newKeyTPM.value
    const res = await createAPIKey(params)
    const data = res.data?.data
    if (data?.full_key) {
      newlyCreatedKey.value = data.full_key
      newlyCreatedKeyId.value = data.id
      keySecretCache.value[String(data.id)] = data.full_key
    }

    showCreateDialog.value = false
    newKeyName.value = ''
    newKeyRPM.value = 60
    newKeyTPM.value = 1000000
    await fetchKeys()
  } catch (err) {
    console.error('[ApiKeyManager] create key failed', err)
  } finally {
    creating.value = false
  }
}

function openKeyDetail(key: APIKey) {
  detailKey.value = key
  detailTab.value = 'settings'
  detailEditName.value = key.name
  detailEditRPM.value = key.rate_limit_rpm
  detailEditTPM.value = key.rate_limit_tpm
}

async function handleUpdateName() {
  if (!detailKey.value || !detailEditName.value.trim()) return
  try {
    await updateAPIKey(detailKey.value.id, { name: detailEditName.value.trim() })
    await fetchKeys()
    detailKey.value = apiKeys.value.find((k) => k.id === detailKey.value!.id) || null
    emit('toast', t('service.apikey.name_updated'), 'success')
  } catch (err) {
    console.error('[ApiKeyManager] update name failed', err)
  }
}

async function handleUpdateRateLimit() {
  if (!detailKey.value) return
  try {
    await updateAPIKey(detailKey.value.id, {
      rate_limit_rpm: detailEditRPM.value,
      rate_limit_tpm: detailEditTPM.value,
    })
    await fetchKeys()
    detailKey.value = apiKeys.value.find((k) => k.id === detailKey.value!.id) || null
    emit('toast', t('service.apikey.limit_updated'), 'success')
  } catch (err) {
    console.error('[ApiKeyManager] update rate limit failed', err)
  }
}

function switchDetailTab(tab: 'settings' | 'data' | 'guardrails') {
  detailTab.value = tab
  if (tab === 'data' && chartData.value.length === 0) {
    initChartDateRange()
    fetchKeyUsageData()
  }
  if (tab === 'guardrails' && guardrailList.value.length === 0) {
    fetchGuardrailList()
    if (grTemplates.value.length === 0) fetchGrTemplates()
  }
}

async function handleDelete(id: number) {
  if (!confirm(t('service.apikey.delete_confirm'))) return

  try {
    await deleteAPIKey(id)
    delete keySecretCache.value[String(id)]

    if (newlyCreatedKeyId.value === id) {
      newlyCreatedKey.value = null
      newlyCreatedKeyId.value = null
    }

    await fetchKeys()
  } catch (err) {
    console.error('[ApiKeyManager] delete key failed', err)
  }
}

async function handleCopyStoredKey(id: number) {
  const secret = await getFullKey(id)
  if (secret) {
    await copyKey(secret)
    return
  }

  const keyRecord = apiKeys.value.find((k) => k.id === id)
  if (keyRecord?.key_prefix) {
    try {
      await copyText(keyRecord.key_prefix)
      emit('toast', t('service.apikey.copy_prefix_tip'), 'info')
    } catch {
      emit('toast', t('service.apikey.copy_failed'), 'info')
    }
  } else {
    emit('toast', t('service.apikey.copy_no_cache'), 'info')
  }
}

// ── Clipboard helpers ──

async function copyText(text: string) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  document.body.appendChild(textarea)
  textarea.select()

  try {
    const copied = document.execCommand('copy')
    if (!copied) throw new Error('execCommand copy failed')
  } finally {
    document.body.removeChild(textarea)
  }
}

async function copyKey(key: string) {
  try {
    await copyText(key)
    emit('toast', t('service.apikey.copy') + ' ✓', 'success')
  } catch (error) {
    console.error('[ApiKeyManager] copy key failed', error)
    emit('toast', t('service.apikey.copy_failed'), 'info')
  }
}

// ── Utility formatters ──

function formatTime(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString()
}

function quotaPercent(key: APIKey): number {
  if (key.quota_total <= 0) return 0
  return Math.min(100, Math.round((key.quota_used / key.quota_total) * 100))
}

function formatTokens(n: number): string {
  if (n < 0) return '∞'
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

// ── Chart rendering ──

function initChartDateRange() {
  const now = new Date()
  const end = now.toISOString().slice(0, 10)
  const start = new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10)
  if (!chartStartDate.value) chartStartDate.value = start
  if (!chartEndDate.value) chartEndDate.value = end
}

async function fetchKeyUsageData() {
  if (!detailKey.value) return
  chartLoading.value = true

  try {
    const params: Record<string, string> = {
      api_key_id: String(detailKey.value.id),
      page: '1',
      page_size: '1000',
    }
    if (chartStartDate.value) params.start_date = chartStartDate.value
    if (chartEndDate.value) params.end_date = chartEndDate.value

    const res = await getConsumption(params)
    const items = res.data?.data?.items || []

    // Aggregate by date
    const dateMap = new Map<
      string,
      { requests: number; tokens: number; prompt: number; completion: number; userIds: Set<number> }
    >()
    for (const item of items) {
      const d = String((item as any).usage_date || '')
      if (!d) continue
      const existing = dateMap.get(d) || { requests: 0, tokens: 0, prompt: 0, completion: 0, userIds: new Set() }
      existing.requests += Number((item as any).request_count || 0)
      existing.tokens += Number((item as any).total_tokens || 0)
      existing.prompt += Number((item as any).prompt_tokens || 0)
      existing.completion += Number((item as any).completion_tokens || 0)
      const uid = Number((item as any).user_id || 0)
      if (uid > 0) existing.userIds.add(uid)
      dateMap.set(d, existing)
    }

    const sorted = [...dateMap.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, val]) => ({
        date,
        requests: val.requests,
        tokens: val.tokens,
        promptTokens: val.prompt,
        completionTokens: val.completion,
        users: val.userIds.size,
      }))

    const allUserIds = new Set<number>()
    for (const val of dateMap.values()) {
      for (const uid of val.userIds) allUserIds.add(uid)
    }

    chartData.value = sorted
    chartSummary.value = {
      totalRequests: sorted.reduce((sum, d) => sum + d.requests, 0),
      totalTokens: sorted.reduce((sum, d) => sum + d.tokens, 0),
      promptTokens: sorted.reduce((sum, d) => sum + d.promptTokens, 0),
      completionTokens: sorted.reduce((sum, d) => sum + d.completionTokens, 0),
      totalUsers: allUserIds.size,
    }

    await nextTick()
    requestAnimationFrame(() => renderCharts())
  } catch (err) {
    console.error('[ApiKeyManager] fetch usage data failed', err)
    chartData.value = []
    chartSummary.value = { totalRequests: 0, totalTokens: 0, promptTokens: 0, completionTokens: 0, totalUsers: 0 }
  } finally {
    chartLoading.value = false
  }
}

function renderCharts() {
  const dates = chartData.value.map((d) => d.date)
  const isSinglePoint = dates.length === 1
  const chartType = isSinglePoint ? 'bar' : 'line'

  const commonOptions = {
    grid: { left: 50, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: 'axis' as const },
    xAxis: { type: 'category' as const, data: dates, axisLabel: { fontSize: 10 } },
  }

  if (requestsChartRef.value) {
    if (requestsChart) requestsChart.dispose()
    requestsChart = echarts.init(requestsChartRef.value)
    requestsChart.setOption({
      ...commonOptions,
      yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10 } },
      series: [
        {
          type: chartType,
          data: chartData.value.map((d) => d.requests),
          smooth: !isSinglePoint,
          symbol: 'circle',
          symbolSize: isSinglePoint ? 10 : 5,
          barMaxWidth: 40,
          lineStyle: { color: '#4F7BF7', width: 2 },
          itemStyle: { color: '#4F7BF7' },
          areaStyle: isSinglePoint
            ? undefined
            : {
                color: {
                  type: 'linear',
                  x: 0,
                  y: 0,
                  x2: 0,
                  y2: 1,
                  colorStops: [
                    { offset: 0, color: 'rgba(79,123,247,0.25)' },
                    { offset: 1, color: 'rgba(79,123,247,0.02)' },
                  ],
                },
              },
        },
      ],
    })
  }

  if (tokensChartRef.value) {
    if (tokensChart) tokensChart.dispose()
    tokensChart = echarts.init(tokensChartRef.value)
    const tokenFormatter = (v: number) => {
      if (v >= 1e6) return (v / 1e6).toFixed(1) + 'M'
      if (v >= 1e3) return (v / 1e3).toFixed(0) + 'K'
      return String(v)
    }
    tokensChart.setOption({
      ...commonOptions,
      legend: { data: ['Prompt Tokens', 'Completion Tokens'], top: 0, textStyle: { fontSize: 10 } },
      grid: { left: 50, right: 20, top: 35, bottom: 30 },
      yAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: tokenFormatter } },
      series: [
        {
          name: 'Prompt Tokens',
          type: chartType,
          stack: 'tokens',
          data: chartData.value.map((d) => d.promptTokens),
          smooth: !isSinglePoint,
          symbol: 'circle',
          symbolSize: isSinglePoint ? 10 : 4,
          barMaxWidth: 40,
          lineStyle: { color: '#4F7BF7', width: 1.5 },
          itemStyle: { color: '#4F7BF7' },
          areaStyle: isSinglePoint ? undefined : { color: 'rgba(79,123,247,0.15)' },
        },
        {
          name: 'Completion Tokens',
          type: chartType,
          stack: 'tokens',
          data: chartData.value.map((d) => d.completionTokens),
          smooth: !isSinglePoint,
          symbol: 'circle',
          symbolSize: isSinglePoint ? 10 : 4,
          barMaxWidth: 40,
          lineStyle: { color: '#10B981', width: 1.5 },
          itemStyle: { color: '#10B981' },
          areaStyle: isSinglePoint ? undefined : { color: 'rgba(16,185,129,0.15)' },
        },
      ],
    })
  }

  if (usersChartRef.value) {
    if (usersChart) usersChart.dispose()
    usersChart = echarts.init(usersChartRef.value)
    usersChart.setOption({
      ...commonOptions,
      yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10 } },
      series: [
        {
          type: chartType,
          data: chartData.value.map((d) => d.users),
          smooth: !isSinglePoint,
          symbol: 'circle',
          symbolSize: isSinglePoint ? 10 : 5,
          barMaxWidth: 40,
          lineStyle: { color: '#F59E0B', width: 2 },
          itemStyle: { color: '#F59E0B' },
          areaStyle: isSinglePoint
            ? undefined
            : {
                color: {
                  type: 'linear',
                  x: 0,
                  y: 0,
                  x2: 0,
                  y2: 1,
                  colorStops: [
                    { offset: 0, color: 'rgba(245,158,11,0.25)' },
                    { offset: 1, color: 'rgba(245,158,11,0.02)' },
                  ],
                },
              },
        },
      ],
    })
  }
}

function disposeCharts() {
  if (requestsChart) {
    requestsChart.dispose()
    requestsChart = null
  }
  if (tokensChart) {
    tokensChart.dispose()
    tokensChart = null
  }
  if (usersChart) {
    usersChart.dispose()
    usersChart = null
  }
}

function handleChartResize() {
  requestsChart?.resize()
  tokensChart?.resize()
  usersChart?.resize()
}

// Watch detailKey changes — reset chart data when navigating away
watch(detailKey, (newVal) => {
  if (!newVal) {
    chartData.value = []
    chartSummary.value = { totalRequests: 0, totalTokens: 0, promptTokens: 0, completionTokens: 0, totalUsers: 0 }
    chartStartDate.value = ''
    chartEndDate.value = ''
    disposeCharts()
  }
})

// ── Guardrail helpers ──

async function fetchGrTemplates() {
  try {
    const res = await listGuardrailTemplates(locale.value)
    grTemplates.value = res.data.data || []
  } catch (err) {
    console.error('[ApiKeyManager] fetch guardrail templates failed', err)
  }
}

async function fetchGuardrailList() {
  if (!detailKey.value) return
  try {
    const res = await listGuardrails(detailKey.value.id)
    guardrailList.value = res.data.data || []
  } catch (err) {
    console.error('[ApiKeyManager] fetch guardrails failed', err)
  }
}

function switchGrInnerTab(tab: 'rules' | 'results') {
  grInnerTab.value = tab
  if (tab === 'results' && grResultsList.value.length === 0) {
    resetAndFetchGrResults()
  }
}

/** Reset results list and fetch first page (used on tab switch and filter change). */
function resetAndFetchGrResults() {
  grResultsList.value = []
  grResultsPage.value = 1
  grResultsHasMore.value = false
  fetchGrResults()
}

/** Fetch guardrail results for the current page and append to list. */
async function fetchGrResults() {
  if (!detailKey.value) return
  const isFirstPage = grResultsPage.value === 1
  if (isFirstPage) {
    grResultsLoading.value = true
  } else {
    grResultsLoadingMore.value = true
  }
  try {
    const params: Record<string, any> = {
      page: grResultsPage.value,
      page_size: grResultsPageSize,
    }
    if (grResultsStartTime.value) {
      params.start_time = grResultsStartTime.value + 'T00:00:00Z'
    }
    if (grResultsEndTime.value) {
      params.end_time = grResultsEndTime.value + 'T23:59:59Z'
    }
    const res = await listGuardrailResults(detailKey.value.id, params)
    const data = res.data.data
    const newResults = data?.results || []
    if (isFirstPage) {
      grResultsList.value = newResults
    } else {
      grResultsList.value.push(...newResults)
    }
    grResultsHasMore.value = data?.has_more ?? false
  } catch (err) {
    console.error('[ApiKeyManager] fetch guardrail results failed', err)
  } finally {
    grResultsLoading.value = false
    grResultsLoadingMore.value = false
  }
}

/** Scroll handler: load next page when user scrolls near bottom. */
function onGrResultsScroll() {
  if (!grResultsHasMore.value || grResultsLoadingMore.value) return
  const el = grResultsScrollRef.value
  if (!el) return
  // Trigger when scrolled within 80px of bottom
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
    grResultsPage.value++
    fetchGrResults()
  }
}

/** Parse the reason field from evaluator_response JSON string. */
function parseEvalReason(raw: string): string {
  if (!raw) return ''
  try {
    const obj = JSON.parse(raw)
    return obj.reason || ''
  } catch {
    return ''
  }
}

/** Copy request ID to clipboard with toast feedback. */
async function copyRequestId(requestId: string) {
  try {
    await copyText(requestId)
    emit('toast', 'Request ID copied', 'success')
  } catch {
    emit('toast', 'Copy failed', 'info')
  }
}

function resetGrForm() {
  grEditingId.value = null
  grFormTemplate.value = ''
  grFormName.value = ''
  grFormPhase.value = 'input'
  grFormAction.value = 'block'
  grFormPrompt.value = ''
  grFormEvalModel.value = ''
  grFormEvalAPIKeyId.value = 0
  grFormStorageType.value = 'builtin'
  grFormDBType.value = 'mysql'
  grFormDBHost.value = ''
  grFormDBPort.value = 3306
  grFormDBUser.value = ''
  grFormDBPassword.value = ''
  grFormDBName.value = ''
}

function openGrCreateForm() {
  resetGrForm()
  grFormVisible.value = true
}

function openGrEditForm(gr: Guardrail) {
  grEditingId.value = gr.id
  grFormName.value = gr.name
  grFormPhase.value = gr.phase as 'input' | 'output'
  grFormAction.value = gr.action as 'block' | 'log'
  grFormPrompt.value = gr.prompt
  grFormEvalModel.value = gr.evaluator_model
  grFormEvalAPIKeyId.value = gr.evaluator_api_key_id
  grFormStorageType.value = gr.storage_type as 'builtin' | 'external'
  grFormDBType.value = gr.db_type || 'mysql'
  grFormDBHost.value = gr.db_host || ''
  grFormDBPort.value = gr.db_port || 3306
  grFormDBUser.value = gr.db_user || ''
  grFormDBPassword.value = ''
  grFormDBName.value = gr.db_name || ''
  grFormTemplate.value = ''
  grFormVisible.value = true
}

function onGrTemplateChange() {
  const tpl = grTemplates.value.find((t) => t.name === grFormTemplate.value)
  if (tpl) {
    grFormName.value = tpl.display_name
    grFormPrompt.value = tpl.prompt_template
    if (tpl.phase === 'input' || tpl.phase === 'output') {
      grFormPhase.value = tpl.phase
    } else {
      grFormPhase.value = 'input'
    }
  }
}

async function handleGrSubmit() {
  if (!detailKey.value) return
  grFormSubmitting.value = true
  try {
    if (grEditingId.value) {
      const params: UpdateGuardrailParams = {
        name: grFormName.value.trim(),
        phase: grFormPhase.value,
        action: grFormAction.value,
        prompt: grFormPrompt.value.trim(),
        evaluator_model: grFormEvalModel.value,
        evaluator_api_key_id: grFormEvalAPIKeyId.value,
        storage_type: grFormStorageType.value,
      }
      if (grFormStorageType.value === 'external') {
        params.db_type = grFormDBType.value
        params.db_host = grFormDBHost.value
        params.db_port = grFormDBPort.value
        params.db_user = grFormDBUser.value
        if (grFormDBPassword.value) params.db_password = grFormDBPassword.value
        params.db_name = grFormDBName.value
      }
      await updateGuardrail(detailKey.value.id, grEditingId.value, params)
      emit('toast', t('service.apikey.guardrails_updated'), 'success')
    } else {
      const params: CreateGuardrailParams = {
        name: grFormName.value.trim(),
        phase: grFormPhase.value,
        action: grFormAction.value,
        prompt: grFormPrompt.value.trim(),
        evaluator_model: grFormEvalModel.value,
        evaluator_api_key_id: grFormEvalAPIKeyId.value,
        storage_type: grFormStorageType.value,
      }
      if (grFormStorageType.value === 'external') {
        params.db_type = grFormDBType.value
        params.db_host = grFormDBHost.value
        params.db_port = grFormDBPort.value
        params.db_user = grFormDBUser.value
        params.db_password = grFormDBPassword.value
        params.db_name = grFormDBName.value
      }
      await createGuardrail(detailKey.value.id, params)
      emit('toast', t('service.apikey.guardrails_created'), 'success')
    }
    grFormVisible.value = false
    await fetchGuardrailList()
  } catch (err) {
    console.error('[ApiKeyManager] guardrail submit failed', err)
  } finally {
    grFormSubmitting.value = false
  }
}

async function handleToggleGuardrail(gr: Guardrail) {
  if (!detailKey.value) return
  try {
    await updateGuardrail(detailKey.value.id, gr.id, { enabled: !gr.enabled })
    await fetchGuardrailList()
    emit(
      'toast',
      gr.enabled ? t('service.apikey.guardrails_disabled') : t('service.apikey.guardrails_enabled'),
      'success',
    )
  } catch (err) {
    console.error('[ApiKeyManager] toggle guardrail failed', err)
  }
}

async function handleDeleteGuardrail(gr: Guardrail) {
  if (!confirm(t('service.apikey.guardrails_confirm_delete'))) return
  if (!detailKey.value) return
  try {
    await deleteGuardrail(detailKey.value.id, gr.id)
    await fetchGuardrailList()
    emit('toast', t('service.apikey.guardrails_deleted'), 'success')
  } catch (err) {
    console.error('[ApiKeyManager] delete guardrail failed', err)
  }
}

// ── Lifecycle ──

onMounted(() => {
  window.addEventListener('resize', handleChartResize)
  fetchKeys()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleChartResize)
  disposeCharts()
})

// ── Expose for parent access ──
defineExpose({
  apiKeys,
  getFullKey,
  fetchKeys,
})
</script>
