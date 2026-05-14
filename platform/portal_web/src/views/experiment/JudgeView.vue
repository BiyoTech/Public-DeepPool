<template>
  <div class="bg-white rounded-xl border border-slate-200 p-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-lg font-semibold text-dp-title">{{ $t('experiment.judge_title') }}</h2>
        <p class="text-sm text-dp-muted mt-1">{{ $t('experiment.judge_desc') }}</p>
      </div>
      <button @click="openCreate" class="px-4 py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition">
        + {{ $t('experiment.judge.create') }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-16">
      <div class="w-8 h-8 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
    </div>

    <!-- Empty -->
    <div v-else-if="judges.length === 0" class="text-center py-16 text-dp-muted text-sm">
      {{ $t('experiment.judge.empty') }}
    </div>

    <!-- Judge List -->
    <div v-else class="space-y-3">
      <div v-for="judge in judges" :key="judge.id"
        class="border border-slate-200 rounded-lg p-4 hover:border-slate-300 transition">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-3">
            <h3 class="font-medium text-dp-title">{{ judge.name }}</h3>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-medium" :class="statusClass(judge.status)">
              {{ $t(`experiment.judge.status_${judge.status}`) }}
            </span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">
              {{ targetLabel(judge) }}
            </span>
            <span class="px-2 py-0.5 rounded-full text-[10px] font-medium"
              :class="judge.scorer_type === 'builtin' ? 'bg-blue-50 text-blue-600' : 'bg-violet-50 text-violet-600'">
              {{ judge.scorer_type === 'builtin' ? judge.scorer_name : 'Custom' }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <button v-if="judge.status !== 'running'" @click="handleRun(judge)"
              class="px-3 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-600 hover:bg-emerald-100 transition">
              {{ $t('experiment.judge.run') }}
            </button>
            <button @click="openEdit(judge)"
              class="px-3 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-600 hover:bg-amber-100 transition">
              {{ $t('experiment.judge.edit') }}
            </button>
            <button @click="viewRuns(judge)"
              class="px-3 py-1 rounded-md text-xs font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 transition">
              {{ $t('experiment.judge.view_runs') }}
            </button>
            <button @click="handleDelete(judge)"
              class="px-3 py-1 rounded-md text-xs font-medium bg-red-50 text-red-500 hover:bg-red-100 transition">
              {{ $t('experiment.judge.delete') }}
            </button>
          </div>
        </div>
        <div class="flex items-center gap-4 text-xs text-dp-muted">
          <span>Model: {{ judge.judge_model }}</span>
          <span v-if="judge.status === 'running' || judge.status === 'completed'">
            {{ judge.completed_count + judge.failed_count }}/{{ judge.total_count }}
            <span v-if="judge.failed_count > 0" class="text-red-500">({{ judge.failed_count }} failed)</span>
          </span>
          <span>{{ formatTime(judge.created_at) }}</span>
        </div>
      </div>
    </div>

    <!-- ===== Create Judge Drawer ===== -->
    <Transition
      enter-active-class="transition duration-200 ease-out" enter-from-class="translate-x-full" enter-to-class="translate-x-0"
      leave-active-class="transition duration-150 ease-in" leave-from-class="translate-x-0" leave-to-class="translate-x-full">
      <div v-if="showCreate" class="fixed inset-y-0 right-0 z-50 w-[560px] max-w-full bg-white shadow-2xl flex flex-col">
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <h3 class="text-lg font-bold text-dp-title">{{ editJudgeId ? $t('experiment.judge.edit_title') : $t('experiment.judge.create_title') }}</h3>
          <button class="p-1.5 rounded-lg hover:bg-slate-100 transition" @click="showCreate = false">
            <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>

        <div class="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          <!-- Name -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">{{ $t('experiment.judge.name_label') }}</label>
            <input v-model="form.name" type="text" :placeholder="$t('experiment.judge.name_placeholder')"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" />
          </div>

          <!-- ===== Target Selection ===== -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-2 block">{{ $t('experiment.judge.target_label') }}</label>
            <p class="text-[11px] text-slate-400 mb-3">{{ $t('experiment.judge.target_hint') }}</p>

            <!-- Step 1: Trace selection (optional) -->
            <div class="mb-3">
              <label class="text-[11px] font-medium text-slate-400 mb-1 block uppercase tracking-wide">{{ $t('experiment.judge.step_trace') }}</label>
              <select v-model="form.traceId" @change="onTraceChange"
                class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100">
                <option :value="0">{{ $t('experiment.judge.all_traces') }}</option>
                <option v-for="tr in traces" :key="tr.id" :value="tr.id">{{ tr.name }}</option>
              </select>
            </div>

            <!-- Step 2: Model/APIKey filter (only when trace is selected) -->
            <div v-if="form.traceId" class="mb-3 space-y-2">
              <label class="text-[11px] font-medium text-slate-400 mb-1 block uppercase tracking-wide">{{ $t('experiment.judge.step_filter') }}</label>

              <!-- Model filter chips -->
              <div v-if="selectedTraceModels.length > 0">
                <p class="text-[11px] text-slate-400 mb-1">{{ $t('experiment.judge.filter_models') }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <button v-for="m in selectedTraceModels" :key="m" type="button"
                    class="px-2.5 py-1 rounded-full text-xs border transition"
                    :class="form.filterModels.includes(m) ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'"
                    @click="toggleModel(m)">
                    {{ m }}
                  </button>
                </div>
              </div>

              <!-- APIKey filter chips -->
              <div v-if="selectedTraceApiKeys.length > 0">
                <p class="text-[11px] text-slate-400 mb-1">{{ $t('experiment.judge.filter_apikeys') }}</p>
                <div class="flex flex-wrap gap-1.5">
                  <button v-for="k in selectedTraceApiKeys" :key="k.id" type="button"
                    class="px-2.5 py-1 rounded-full text-xs border transition"
                    :class="form.filterApiKeyIds.includes(k.id) ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'"
                    @click="toggleApiKey(k.id)">
                    {{ k.name }} ({{ k.key_prefix }}...)
                  </button>
                </div>
              </div>
            </div>

            <!-- Step 3: Pick specific logs (optional, only when trace selected) -->
            <div v-if="form.traceId" class="mb-1">
              <label class="text-[11px] font-medium text-slate-400 uppercase tracking-wide mb-1 block">{{ $t('experiment.judge.step_logs') }}</label>
              <div class="flex items-center gap-2">
                <button type="button" @click="openLogPicker"
                  class="px-3 py-1.5 rounded-lg border border-dashed border-slate-300 text-xs text-slate-500 hover:border-blue-400 hover:text-blue-500 transition">
                  {{ $t('experiment.judge.pick_logs') }}
                </button>
                <span v-if="form.selectedLogIds.length > 0"
                  class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[11px] font-medium bg-blue-50 text-blue-600">
                  {{ $t('experiment.judge.selected_count', { count: form.selectedLogIds.length, total: pickerLogs.length || '?' }) }}
                  <button type="button" @click="form.selectedLogIds = []" class="ml-0.5 hover:text-blue-800">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                  </button>
                </span>
              </div>
            </div>

            <!-- Target summary -->
            <div class="px-3 py-2 rounded-lg bg-slate-50 text-xs text-slate-500 mt-2">
              {{ targetSummary }}
            </div>
          </div>

          <!-- Judge Model (searchable dropdown, same style as ServiceView) -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">{{ $t('experiment.judge.judge_model_label') }}</label>
            <div class="relative" ref="judgeModelDropdownRef">
              <button type="button" @click="judgeModelDropdownOpen = !judgeModelDropdownOpen"
                class="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-sm text-left focus:outline-none"
                :class="judgeModelDropdownOpen ? 'border-blue-400 ring-2 ring-blue-100 bg-white' : 'border-slate-200 bg-white'">
                <template v-if="selectedJudgeModelOption">
                  <span class="truncate text-dp-title">{{ selectedJudgeModelOption.id }}</span>
                  <span :class="vendorTagClass(selectedJudgeModelOption.vendor_type)"
                    class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none">
                    {{ vendorLabel(selectedJudgeModelOption.vendor_type) }}
                  </span>
                </template>
                <span v-else class="text-slate-400 truncate">{{ $t('experiment.judge.judge_model_placeholder') }}</span>
                <svg class="w-4 h-4 shrink-0 text-slate-400 transition-transform" :class="{ 'rotate-180': judgeModelDropdownOpen }"
                  fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
              </button>
              <Transition
                enter-active-class="transition duration-100 ease-out" enter-from-class="opacity-0 -translate-y-1" enter-to-class="opacity-100 translate-y-0"
                leave-active-class="transition duration-75 ease-in" leave-from-class="opacity-100 translate-y-0" leave-to-class="opacity-0 -translate-y-1">
                <ul v-if="judgeModelDropdownOpen"
                  class="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
                  <!-- Search input -->
                  <li class="sticky top-0 bg-white px-2 py-1.5 border-b border-slate-100">
                    <input v-model="judgeModelSearch" type="text" :placeholder="$t('experiment.judge.model_search_placeholder')"
                      class="w-full px-3 py-1.5 rounded-md border border-slate-200 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:border-blue-400"
                      @click.stop />
                  </li>
                  <li v-if="filteredJudgeModels.length === 0" class="px-3 py-4 text-center text-xs text-slate-400">
                    {{ $t('experiment.judge.no_models_found') }}
                  </li>
                  <li v-for="m in filteredJudgeModels" :key="m.id"
                    class="flex items-center justify-between gap-2 px-3 py-2 cursor-pointer text-sm hover:bg-blue-50"
                    :class="m.id === form.judgeModel ? 'bg-blue-50 text-dp-blue font-medium' : 'text-dp-title'"
                    @click="selectJudgeModel(m.id)">
                    <div class="flex-1 min-w-0">
                      <div class="truncate">{{ m.id }}</div>
                      <div v-if="m.tags?.length" class="flex flex-wrap items-center gap-1 mt-0.5">
                        <span v-for="tag in m.tags" :key="tag"
                          class="inline-flex items-center rounded-full bg-slate-100 px-1.5 py-0 text-[10px] text-slate-500">{{ tag }}</span>
                      </div>
                    </div>
                    <span :class="vendorTagClass(m.vendor_type)"
                      class="inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[10px] font-medium leading-none">
                      {{ vendorLabel(m.vendor_type) }}
                    </span>
                  </li>
                </ul>
              </Transition>
            </div>
          </div>

          <!-- Judge API Key -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">{{ $t('experiment.judge.judge_apikey_label') }}</label>
            <select v-model="form.judgeApiKeyId"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100">
              <option :value="0" disabled>{{ $t('experiment.judge.judge_apikey_placeholder') }}</option>
              <option v-for="key in apiKeys" :key="key.id" :value="key.id">{{ key.name }} ({{ key.key_prefix }}...)</option>
            </select>
          </div>

          <!-- Scorer Type -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1.5 block">{{ $t('experiment.judge.scorer_type_label') }}</label>
            <div class="flex gap-2">
              <button @click="form.scorerType = 'builtin'" type="button"
                class="px-3 py-1.5 rounded-lg border text-xs font-medium transition"
                :class="form.scorerType === 'builtin' ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'">
                {{ $t('experiment.judge.scorer_builtin') }}
              </button>
              <button @click="form.scorerType = 'custom'" type="button"
                class="px-3 py-1.5 rounded-lg border text-xs font-medium transition"
                :class="form.scorerType === 'custom' ? 'border-violet-500 bg-violet-50 text-violet-600' : 'border-slate-200 text-slate-500 hover:bg-slate-50'">
                {{ $t('experiment.judge.scorer_custom') }}
              </button>
            </div>
          </div>

          <!-- Builtin Scorer Select -->
          <div v-if="form.scorerType === 'builtin'">
            <label class="text-xs font-medium text-slate-500 mb-1 block">{{ $t('experiment.judge.scorer_name_label') }}</label>
            <select v-model="form.scorerName" @change="onScorerChange"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm bg-white focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100">
              <option value="" disabled>{{ $t('experiment.judge.scorer_select_placeholder') }}</option>
              <option v-for="sc in builtinScorers" :key="sc.name" :value="sc.name">{{ sc.display_name }} — {{ sc.description }}</option>
            </select>
          </div>

          <!-- Prompt Template -->
          <div>
            <label class="text-xs font-medium text-slate-500 mb-1 block">{{ $t('experiment.judge.prompt_label') }}</label>
            <textarea v-model="form.promptTemplate" rows="8" :placeholder="$t('experiment.judge.prompt_placeholder')"
              class="w-full px-3 py-2 rounded-lg border border-slate-200 text-xs font-mono resize-y focus:outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100" style="min-height: 120px;" />
            <p class="text-[10px] text-slate-400 mt-1">{{ $t('experiment.judge.variables_hint') }}</p>
          </div>

          <!-- Error -->
          <div v-if="createError" class="px-3 py-2 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-600">{{ createError }}</div>
        </div>

        <div class="px-6 py-4 border-t border-slate-100 flex justify-end gap-3 shrink-0">
          <button @click="showCreate = false" class="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-500 hover:bg-slate-50 transition">
            {{ $t('experiment.judge.cancel') }}
          </button>
          <button @click="handleCreate" :disabled="creating" class="px-4 py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition disabled:opacity-50">
            {{ creating ? '...' : (editJudgeId ? $t('experiment.judge.save') : $t('experiment.judge.confirm')) }}
          </button>
        </div>
      </div>
    </Transition>
    <Transition enter-active-class="transition duration-200" enter-from-class="opacity-0" enter-to-class="opacity-100"
      leave-active-class="transition duration-150" leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-if="showCreate" class="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" @click="showCreate = false" />
    </Transition>

    <!-- ===== Runs & Results Drawer ===== -->
    <Transition enter-active-class="transition duration-200 ease-out" enter-from-class="translate-x-full" enter-to-class="translate-x-0"
      leave-active-class="transition duration-150 ease-in" leave-from-class="translate-x-0" leave-to-class="translate-x-full">
      <div v-if="runsJudge" class="fixed inset-y-0 right-0 z-50 w-[700px] max-w-full bg-white shadow-2xl flex flex-col">
        <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
          <div>
            <h3 class="text-lg font-bold text-dp-title">{{ runsJudge.name }}</h3>
            <p class="text-xs text-dp-muted mt-0.5">
              {{ activeRunView ? $t('experiment.judge.run_results_title') : $t('experiment.judge.runs_title') }}
            </p>
          </div>
          <div class="flex items-center gap-2">
            <button v-if="activeRunView" @click="activeRunView = null"
              class="px-3 py-1 rounded-md text-xs font-medium bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
              {{ $t('experiment.judge.back_to_runs') }}
            </button>
            <button class="p-1.5 rounded-lg hover:bg-slate-100 transition" @click="runsJudge = null; activeRunView = null">
              <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto px-6 py-4">
          <!-- Runs List View -->
          <div v-if="!activeRunView">
            <div v-if="runsLoading" class="flex justify-center py-12">
              <div class="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else-if="runs.length === 0" class="text-center py-12 text-dp-muted text-sm">{{ $t('experiment.judge.no_runs') }}</div>
            <div v-else class="space-y-2">
              <div v-for="run in runs" :key="run.id"
                class="border border-slate-200 rounded-lg p-4 hover:border-blue-300 cursor-pointer transition"
                @click="viewRunResults(run)">
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-dp-title">Run #{{ run.id }}</span>
                    <span class="px-2 py-0.5 rounded-full text-[10px] font-medium" :class="statusClass(run.status)">
                      {{ $t(`experiment.judge.status_${run.status}`) }}
                    </span>
                  </div>
                  <span v-if="run.status === 'completed'" class="text-sm font-bold"
                    :class="run.pass_rate >= 80 ? 'text-emerald-600' : run.pass_rate >= 50 ? 'text-amber-600' : 'text-red-500'">
                    {{ run.pass_rate.toFixed(1) }}%
                  </span>
                </div>
                <div class="flex items-center gap-4 text-xs text-dp-muted">
                  <span>{{ run.completed_count + run.failed_count }}/{{ run.total_count }}</span>
                  <span v-if="run.failed_count > 0" class="text-red-500">({{ run.failed_count }} failed)</span>
                  <span class="ml-auto">{{ formatTime(run.created_at) }}</span>
                </div>
                <!-- Progress bar -->
                <div v-if="run.total_count > 0" class="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div class="h-full rounded-full transition-all duration-300"
                    :class="run.status === 'failed' ? 'bg-red-400' : 'bg-emerald-400'"
                    :style="{ width: `${Math.min(100, ((run.completed_count + run.failed_count) / run.total_count) * 100)}%` }">
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Run Results View -->
          <div v-else>
            <div v-if="resultsLoading" class="flex justify-center py-12">
              <div class="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else-if="results.length === 0" class="text-center py-12 text-dp-muted text-sm">{{ $t('experiment.judge.no_results') }}</div>
            <table v-else class="w-full text-sm">
              <thead>
                <tr class="border-b border-slate-200">
                  <th class="py-2 px-2 text-left text-xs font-medium text-slate-500">{{ $t('experiment.judge.col_log_id') }}</th>
                  <th class="py-2 px-2 text-left text-xs font-medium text-slate-500">{{ $t('experiment.judge.col_passed') }}</th>
                  <th class="py-2 px-2 text-left text-xs font-medium text-slate-500">{{ $t('experiment.judge.col_reason') }}</th>
                  <th class="py-2 px-2 text-left text-xs font-medium text-slate-500">{{ $t('experiment.judge.col_duration') }}</th>
                  <th class="py-2 px-2 text-left text-xs font-medium text-slate-500">{{ $t('experiment.judge.col_status') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in results" :key="r.id" class="border-b border-slate-100 hover:bg-slate-50">
                  <td class="py-2 px-2 font-mono text-xs">{{ r.trace_log_id }}</td>
                  <td class="py-2 px-2">
                    <span v-if="r.success" class="px-2 py-0.5 rounded-full text-[10px] font-medium" :class="r.passed ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-500'">
                      {{ r.passed ? $t('experiment.judge.passed_yes') : $t('experiment.judge.passed_no') }}
                    </span>
                    <span v-else class="text-xs text-red-500">—</span>
                  </td>
                  <td class="py-2 px-2 text-xs max-w-[280px]" :class="r.success ? 'text-slate-600' : 'text-red-600'">
                    <div v-if="expandedResultId === r.id" class="whitespace-pre-wrap break-all cursor-pointer" @click="expandedResultId = null">
                      {{ r.success ? r.reason : r.error_message }}
                    </div>
                    <div v-else class="truncate cursor-pointer hover:text-blue-600" @click="expandedResultId = r.id"
                      :title="$t('experiment.judge.click_to_expand')">
                      {{ r.success ? r.reason : r.error_message }}
                    </div>
                  </td>
                  <td class="py-2 px-2 text-xs text-slate-500">{{ r.duration_ms }}ms</td>
                  <td class="py-2 px-2">
                    <span class="text-[10px] font-medium" :class="r.success ? 'text-emerald-600' : 'text-red-500'">
                      {{ r.success ? $t('experiment.judge.result_success') : $t('experiment.judge.result_failed') }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
            <!-- Infinite scroll sentinel for results -->
            <div v-if="results.length > 0 && resultsHasMore" ref="resultsSentinel" class="flex justify-center py-4">
              <div v-if="resultsLoadingMore" class="w-5 h-5 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
              <span v-else class="text-xs text-dp-muted">Scroll to load more</span>
            </div>
            <div v-if="results.length > 0 && !resultsHasMore" class="text-center py-3 text-xs text-dp-muted">
              — End —
            </div>
          </div>
        </div>
      </div>
    </Transition>
    <Transition enter-active-class="transition duration-200" enter-from-class="opacity-0" enter-to-class="opacity-100"
      leave-active-class="transition duration-150" leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-if="runsJudge" class="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm" @click="runsJudge = null; activeRunView = null" />
    </Transition>

    <!-- ===== Log Picker Modal ===== -->
    <Transition enter-active-class="transition duration-200 ease-out" enter-from-class="opacity-0 scale-95" enter-to-class="opacity-100 scale-100"
      leave-active-class="transition duration-150 ease-in" leave-from-class="opacity-100 scale-100" leave-to-class="opacity-0 scale-95">
      <div v-if="showLogPicker" class="fixed inset-0 z-[60] flex items-center justify-center p-6">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[80vh] flex flex-col overflow-hidden">
          <!-- Modal header -->
          <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100 shrink-0">
            <div>
              <h3 class="text-base font-bold text-dp-title">{{ $t('experiment.judge.pick_logs_title') }}</h3>
              <p class="text-xs text-slate-400 mt-0.5">
                {{ $t('experiment.judge.selected_count', { count: pickerSelectedIds.length, total: pickerLogs.length }) }}
              </p>
            </div>
            <button class="p-1.5 rounded-lg hover:bg-slate-100 transition" @click="cancelLogPicker">
              <svg class="w-5 h-5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
          </div>

          <!-- Table -->
          <div class="flex-1 overflow-y-auto">
            <div v-if="logsLoading" class="flex justify-center py-16">
              <div class="w-6 h-6 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin"></div>
            </div>
            <div v-else-if="pickerLogs.length === 0" class="text-center py-16 text-dp-muted text-sm">
              {{ $t('experiment.judge.no_logs') }}
            </div>
            <table v-else class="w-full text-sm">
              <thead class="bg-slate-50 text-dp-muted text-xs uppercase tracking-wider sticky top-0 z-10">
                <tr>
                  <th class="px-4 py-3 text-left font-medium w-10">
                    <input type="checkbox" :checked="pickerAllSelected" :indeterminate="pickerSomeSelected" @change="toggleAllPickerLogs"
                      class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600" />
                  </th>
                  <th class="px-4 py-3 text-left font-medium">Request ID</th>
                  <th class="px-4 py-3 text-left font-medium">User Query</th>
                  <th class="px-4 py-3 text-left font-medium">Model</th>
                  <th class="px-4 py-3 text-right font-medium">Tokens</th>
                  <th class="px-4 py-3 text-right font-medium">Duration</th>
                  <th class="px-4 py-3 text-center font-medium">Status</th>
                  <th class="px-4 py-3 text-left font-medium">Time</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-for="log in pickerLogs" :key="log.id"
                  class="hover:bg-blue-50/50 cursor-pointer transition-colors"
                  :class="pickerSelectedIds.includes(log.id) ? 'bg-blue-50/30' : ''"
                  @click="togglePickerLog(log.id)">
                  <td class="px-4 py-3" @click.stop>
                    <input type="checkbox" :value="log.id" v-model="pickerSelectedIds"
                      class="w-3.5 h-3.5 rounded border-slate-300 text-blue-600" />
                  </td>
                  <td class="px-4 py-3 font-mono text-xs text-dp-title" :title="log.request_id">
                    {{ truncateId(log.request_id) }}
                  </td>
                  <td class="px-4 py-3 text-dp-muted max-w-[220px]">
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
                    <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                      :class="log.success ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'">
                      {{ log.success ? 'OK' : 'Fail' }}
                    </span>
                  </td>
                  <td class="px-4 py-3 text-xs text-dp-muted whitespace-nowrap">{{ formatTime(log.created_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Modal footer -->
          <div class="flex items-center justify-between px-6 py-3 border-t border-slate-100 bg-slate-50/50 shrink-0">
            <span class="text-xs text-dp-muted">
              {{ pickerSelectedIds.length > 0
                ? $t('experiment.judge.selected_count', { count: pickerSelectedIds.length, total: pickerLogs.length })
                : $t('experiment.judge.pick_logs_hint') }}
            </span>
            <div class="flex gap-2">
              <button @click="cancelLogPicker" class="px-4 py-1.5 rounded-lg border border-slate-200 text-xs text-slate-500 hover:bg-white transition">
                {{ $t('experiment.judge.cancel') }}
              </button>
              <button @click="confirmLogPicker" :disabled="pickerSelectedIds.length === 0"
                class="px-4 py-1.5 rounded-lg bg-dp-blue text-white text-xs font-medium hover:bg-dp-blue-dark transition disabled:opacity-40">
                {{ $t('experiment.judge.confirm_selection') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
    <Transition enter-active-class="transition duration-200" enter-from-class="opacity-0" enter-to-class="opacity-100"
      leave-active-class="transition duration-150" leave-from-class="opacity-100" leave-to-class="opacity-0">
      <div v-if="showLogPicker" class="fixed inset-0 z-[55] bg-black/30 backdrop-blur-sm" @click="cancelLogPicker" />
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listJudges, createJudge, updateJudge, runJudge, deleteJudge,
  listJudgeRuns, getJudgeRunResults,
  listBuiltinScorers, listTraces, getTraceLogs,
  type JudgeDTO, type JudgeResultDTO, type JudgeRunDTO, type BuiltinScorer, type TraceConfig, type TraceLogItem,
} from '@/api/experiment'
import { listAPIKeys, type APIKey } from '@/api/apikey'

const { t, locale } = useI18n()

// --- Model option type (same as ServiceView GatewayModelOption) ---
interface ModelOption {
  id: string
  vendor_type?: string
  tags?: string[]
}

// --- State ---
const loading = ref(true)
const judges = ref<JudgeDTO[]>([])
const traces = ref<TraceConfig[]>([])
const apiKeys = ref<APIKey[]>([])
const builtinScorers = ref<BuiltinScorer[]>([])
const availableModels = ref<ModelOption[]>([])

// Judge model dropdown
const judgeModelDropdownOpen = ref(false)
const judgeModelDropdownRef = ref<HTMLElement>()
const judgeModelSearch = ref('')

const selectedJudgeModelOption = computed(() => availableModels.value.find(m => m.id === form.value.judgeModel) || null)
const filteredJudgeModels = computed(() => {
  const q = judgeModelSearch.value.trim().toLowerCase()
  if (!q) return availableModels.value
  return availableModels.value.filter(m => m.id.toLowerCase().includes(q))
})

function selectJudgeModel(id: string) {
  form.value.judgeModel = id
  judgeModelDropdownOpen.value = false
  judgeModelSearch.value = ''
}

function vendorTagClass(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider': return 'bg-emerald-100 text-emerald-700'
    case 'hybrid': return 'bg-amber-100 text-amber-700'
    default: return 'bg-blue-100 text-dp-blue'
  }
}

function vendorLabel(vendorType?: string): string {
  switch ((vendorType || '').trim()) {
    case 'provider': return 'Provider'
    case 'hybrid': return 'Hybrid'
    default: return 'DeepNode'
  }
}

// Close dropdown on outside click
function handleModelDropdownOutsideClick(e: MouseEvent) {
  if (judgeModelDropdownRef.value && !judgeModelDropdownRef.value.contains(e.target as Node)) {
    judgeModelDropdownOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleModelDropdownOutsideClick))
onBeforeUnmount(() => document.removeEventListener('click', handleModelDropdownOutsideClick))

// Create drawer
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')

// Log picker modal
const showLogPicker = ref(false)
const logsLoading = ref(false)
const pickerLogs = ref<TraceLogItem[]>([])
const pickerSelectedIds = ref<number[]>([]) // temp selection inside modal

const pickerAllSelected = computed(() => pickerLogs.value.length > 0 && pickerSelectedIds.value.length === pickerLogs.value.length)
const pickerSomeSelected = computed(() => pickerSelectedIds.value.length > 0 && !pickerAllSelected.value)

const form = ref({
  name: '',
  traceId: 0,
  filterModels: [] as string[],
  filterApiKeyIds: [] as number[],
  selectedLogIds: [] as number[],
  judgeModel: '',
  judgeApiKeyId: 0,
  scorerType: 'builtin' as 'builtin' | 'custom',
  scorerName: '',
  promptTemplate: '',
})

// Results drawer → now runs-based
const runsJudge = ref<JudgeDTO | null>(null)
const runs = ref<JudgeRunDTO[]>([])
const runsLoading = ref(false)
const activeRunView = ref<JudgeRunDTO | null>(null) // when set, show results for this run
const results = ref<JudgeResultDTO[]>([])
const resultsLoading = ref(false)
const resultsLoadingMore = ref(false)
const resultsHasMore = ref(false)
const resultsPage = ref(1)
const expandedResultId = ref<number | null>(null)

// Edit mode (reuses the create drawer with pre-filled form)
const editJudgeId = ref<number | null>(null)

// Infinite scroll observer for results
const resultsSentinel = ref<HTMLElement | null>(null)
let resultsObserver: IntersectionObserver | null = null

watch(resultsSentinel, () => {
  resultsObserver?.disconnect()
  if (!resultsSentinel.value) return
  resultsObserver = new IntersectionObserver((entries) => {
    if (entries[0]?.isIntersecting && resultsHasMore.value && !resultsLoadingMore.value) {
      loadMoreResults()
    }
  }, { threshold: 0.1 })
  resultsObserver.observe(resultsSentinel.value)
})

// --- Computed: trace-specific data ---

const selectedTrace = computed(() => traces.value.find(t => t.id === form.value.traceId))
const selectedTraceModels = computed(() => selectedTrace.value?.model_names || [])
const selectedTraceApiKeys = computed(() => {
  const ids = selectedTrace.value?.api_key_ids || []
  return apiKeys.value.filter(k => ids.includes(k.id))
})

// Target summary text
const targetSummary = computed(() => {
  const f = form.value
  if (!f.traceId) return t('experiment.judge.summary_all')

  const traceName = selectedTrace.value?.name || `#${f.traceId}`
  const parts: string[] = [traceName]

  if (f.selectedLogIds.length > 0) {
    parts.push(t('experiment.judge.summary_logs', { count: f.selectedLogIds.length }))
  } else {
    if (f.filterModels.length > 0) parts.push(t('experiment.judge.summary_models', { names: f.filterModels.join(', ') }))
    if (f.filterApiKeyIds.length > 0) {
      const names = f.filterApiKeyIds.map(id => apiKeys.value.find(k => k.id === id)?.name || `#${id}`).join(', ')
      parts.push(t('experiment.judge.summary_apikeys', { names }))
    }
    if (f.filterModels.length === 0 && f.filterApiKeyIds.length === 0) {
      parts.push(t('experiment.judge.summary_all_logs'))
    }
  }
  return parts.join(' → ')
})

// --- Data loading ---

async function fetchData() {
  loading.value = true
  try {
    const [judgesRes, tracesRes, keysRes, scorersRes] = await Promise.allSettled([
      listJudges(), listTraces(), listAPIKeys(), listBuiltinScorers(locale.value),
    ])
    if (judgesRes.status === 'fulfilled') judges.value = judgesRes.value.data?.data || []
    if (tracesRes.status === 'fulfilled') traces.value = tracesRes.value.data?.data || []
    if (keysRes.status === 'fulfilled') apiKeys.value = keysRes.value.data?.data || []
    if (scorersRes.status === 'fulfilled') builtinScorers.value = scorersRes.value.data?.data || []

    // Fetch available models from gateway (same as ServiceView)
    await fetchModels()
  } finally {
    loading.value = false
  }
}

/** Fetch model list from gateway /v1/models endpoint */
async function fetchModels() {
  const gatewayBaseUrl = import.meta.env.VITE_GATEWAY_BASE_URL || (window.location.origin + '/v1')
  try {
    const res = await fetch(`${gatewayBaseUrl}/models`)
    if (!res.ok) return
    const json = await res.json()
    const items = Array.isArray(json?.data) ? json.data : []
    const seen = new Set<string>()
    availableModels.value = items
      .map((item: any): ModelOption => ({
        id: String(item?.id || '').trim(),
        vendor_type: String(item?.vendor_type || '').trim(),
        tags: Array.isArray(item?.tags) ? item.tags : [],
      }))
      .filter((m: ModelOption) => {
        if (!m.id || seen.has(m.id)) return false
        seen.add(m.id)
        return true
      })
      .sort((a: ModelOption, b: ModelOption) => a.id.localeCompare(b.id))
  } catch (e) {
    console.error('[JudgeView] fetch models failed:', e)
    availableModels.value = []
  }
}

// --- Target selection handlers ---

function onTraceChange() {
  form.value.filterModels = []
  form.value.filterApiKeyIds = []
  form.value.selectedLogIds = []
  showLogPicker.value = false
  pickerLogs.value = []
}

function toggleModel(name: string) {
  const arr = form.value.filterModels
  const idx = arr.indexOf(name)
  idx >= 0 ? arr.splice(idx, 1) : arr.push(name)
  // Clear log selection since filter changed
  form.value.selectedLogIds = []
  if (showLogPicker.value) loadLogs()
}

function toggleApiKey(id: number) {
  const arr = form.value.filterApiKeyIds
  const idx = arr.indexOf(id)
  idx >= 0 ? arr.splice(idx, 1) : arr.push(id)
  form.value.selectedLogIds = []
  if (showLogPicker.value) loadLogs()
}

async function loadLogs() {
  logsLoading.value = true
  pickerSelectedIds.value = [...form.value.selectedLogIds] // restore previous selection
  try {
    const params: Record<string, any> = { page: 1, page_size: 100 }
    if (form.value.filterModels.length === 1) params.model_name = form.value.filterModels[0]
    if (form.value.filterApiKeyIds.length === 1) params.api_key_id = form.value.filterApiKeyIds[0]
    const res = await getTraceLogs(form.value.traceId, params)
    let logs = res.data?.data?.logs || []
    // Client-side filter for multi-model / multi-apikey
    if (form.value.filterModels.length > 1) {
      logs = logs.filter(l => form.value.filterModels.includes(l.model_name))
    }
    if (form.value.filterApiKeyIds.length > 1) {
      logs = logs.filter(l => form.value.filterApiKeyIds.includes(l.api_key_id))
    }
    pickerLogs.value = logs
  } catch (e) {
    console.error('[JudgeView] load logs failed:', e)
    pickerLogs.value = []
  } finally {
    logsLoading.value = false
  }
}

function openLogPicker() {
  showLogPicker.value = true
  loadLogs()
}

function confirmLogPicker() {
  form.value.selectedLogIds = [...pickerSelectedIds.value]
  showLogPicker.value = false
}

function cancelLogPicker() {
  showLogPicker.value = false
}

function togglePickerLog(id: number) {
  const idx = pickerSelectedIds.value.indexOf(id)
  idx >= 0 ? pickerSelectedIds.value.splice(idx, 1) : pickerSelectedIds.value.push(id)
}

function toggleAllPickerLogs() {
  if (pickerAllSelected.value) {
    pickerSelectedIds.value = []
  } else {
    pickerSelectedIds.value = pickerLogs.value.map(l => l.id)
  }
}

function truncateId(id: string): string {
  return id && id.length > 12 ? id.slice(0, 12) + '...' : (id || '')
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// --- Scorer ---

function onScorerChange() {
  const scorer = builtinScorers.value.find(s => s.name === form.value.scorerName)
  if (scorer) form.value.promptTemplate = scorer.prompt_template
}

// --- Create ---

function openCreate() {
  editJudgeId.value = null
  resetForm()
  showCreate.value = true
}

/**
 * Map the unified target selection to backend scope/scope_value/trace_id fields.
 * Priority: selectedLogIds > filterModels/filterApiKeyIds > trace > all
 */
function resolveScope(): { scope: string; scope_value: string; trace_id: number } {
  const f = form.value

  // Case 1: Specific logs selected
  if (f.selectedLogIds.length > 0) {
    return { scope: 'trace_log', scope_value: f.selectedLogIds.join(','), trace_id: f.traceId }
  }

  // Case 2: Model filter active
  if (f.filterModels.length > 0) {
    return { scope: 'model', scope_value: f.filterModels.join(','), trace_id: f.traceId }
  }

  // Case 3: APIKey filter active
  if (f.filterApiKeyIds.length > 0) {
    return { scope: 'apikey', scope_value: f.filterApiKeyIds.join(','), trace_id: f.traceId }
  }

  // Case 4: Only trace selected — all logs under this trace
  if (f.traceId) {
    return { scope: 'trace', scope_value: '', trace_id: f.traceId }
  }

  // Case 5: Nothing selected — all traces (use scope=trace with trace_id=0 to mean "all")
  return { scope: 'trace', scope_value: '', trace_id: 0 }
}

async function handleCreate() {
  createError.value = ''
  const f = form.value
  if (!f.name.trim()) { createError.value = 'Name is required'; return }
  if (!f.judgeModel.trim()) { createError.value = 'Judge model is required'; return }
  if (!f.judgeApiKeyId) { createError.value = 'Judge API Key is required'; return }
  if (!f.promptTemplate.trim()) { createError.value = 'Prompt is required'; return }
  if (f.scorerType === 'builtin' && !f.scorerName) { createError.value = 'Select a builtin scorer'; return }

  const { scope, scope_value, trace_id } = resolveScope()

  creating.value = true
  try {
    if (editJudgeId.value) {
      // Update existing judge
      await updateJudge(editJudgeId.value, {
        name: f.name.trim(),
        scope,
        scope_value,
        trace_id,
        judge_model: f.judgeModel.trim(),
        judge_apikey_id: f.judgeApiKeyId,
        scorer_type: f.scorerType,
        scorer_name: f.scorerType === 'builtin' ? f.scorerName : '',
        prompt_template: f.promptTemplate,
      })
    } else {
      // Create new judge
      await createJudge({
        name: f.name.trim(),
        scope,
        scope_value,
        trace_id,
        judge_model: f.judgeModel.trim(),
        judge_apikey_id: f.judgeApiKeyId,
        scorer_type: f.scorerType,
        scorer_name: f.scorerType === 'builtin' ? f.scorerName : '',
        prompt_template: f.promptTemplate,
      })
    }
    showCreate.value = false
    editJudgeId.value = null
    resetForm()
    await refreshJudges()
  } catch (err: any) {
    createError.value = err?.response?.data?.message || err?.message || 'Save failed'
  } finally {
    creating.value = false
  }
}

async function handleRun(judge: JudgeDTO) {
  if (!confirm(t('experiment.judge.run_confirm', { name: judge.name }))) return
  try { await runJudge(judge.id); await refreshJudges() }
  catch (err: any) { alert(err?.response?.data?.message || err?.message || 'Run failed') }
}

async function handleDelete(judge: JudgeDTO) {
  if (!confirm(t('experiment.judge.delete_confirm', { name: judge.name }))) return
  try { await deleteJudge(judge.id); await refreshJudges() }
  catch (err: any) { alert(err?.response?.data?.message || err?.message || 'Delete failed') }
}

/** Open the runs drawer for a judge */
async function viewRuns(judge: JudgeDTO) {
  runsJudge.value = judge
  activeRunView.value = null
  runsLoading.value = true
  runs.value = []
  try {
    const res = await listJudgeRuns(judge.id)
    runs.value = res.data?.data || []
  } finally { runsLoading.value = false }
}

/** View results for a specific run */
async function viewRunResults(run: JudgeRunDTO) {
  activeRunView.value = run
  resultsLoading.value = true
  results.value = []
  resultsPage.value = 1
  resultsHasMore.value = false
  expandedResultId.value = null
  try {
    const res = await getJudgeRunResults(runsJudge.value!.id, run.id, 1, 30)
    results.value = res.data?.data?.items || []
    resultsHasMore.value = res.data?.data?.has_more ?? false
  } finally { resultsLoading.value = false }
}

/** Load next page of results and append */
async function loadMoreResults() {
  if (!activeRunView.value || resultsLoadingMore.value || !resultsHasMore.value) return
  resultsLoadingMore.value = true
  try {
    const nextPage = resultsPage.value + 1
    const res = await getJudgeRunResults(runsJudge.value!.id, activeRunView.value.id, nextPage, 30)
    const items = res.data?.data?.items || []
    if (items.length > 0) {
      resultsPage.value = nextPage
      results.value.push(...items)
      resultsHasMore.value = res.data?.data?.has_more ?? false
    } else {
      resultsHasMore.value = false
    }
  } finally { resultsLoadingMore.value = false }
}

/** Open edit drawer with pre-filled form */
function openEdit(judge: JudgeDTO) {
  editJudgeId.value = judge.id
  form.value = {
    name: judge.name,
    traceId: judge.trace_id,
    filterModels: [],
    filterApiKeyIds: [],
    selectedLogIds: [],
    judgeModel: judge.judge_model,
    judgeApiKeyId: judge.judge_apikey_id,
    scorerType: (judge.scorer_type as 'builtin' | 'custom') || 'custom',
    scorerName: judge.scorer_name,
    promptTemplate: judge.prompt_template,
  }
  // Restore scope into filter state
  if (judge.scope === 'model' && judge.scope_value) {
    form.value.filterModels = judge.scope_value.split(',')
  } else if (judge.scope === 'apikey' && judge.scope_value) {
    form.value.filterApiKeyIds = judge.scope_value.split(',').map(Number)
  } else if (judge.scope === 'trace_log' && judge.scope_value) {
    form.value.selectedLogIds = judge.scope_value.split(',').map(Number)
  }
  showCreate.value = true
}

async function refreshJudges() {
  try { const res = await listJudges(); judges.value = res.data?.data || [] } catch { /* silent */ }
}

function resetForm() {
  form.value = {
    name: '', traceId: 0, filterModels: [], filterApiKeyIds: [], selectedLogIds: [],
    judgeModel: '', judgeApiKeyId: 0, scorerType: 'builtin', scorerName: '', promptTemplate: '',
  }
  showLogPicker.value = false
  pickerLogs.value = []
  createError.value = ''
}

// --- Helpers ---

function targetLabel(judge: JudgeDTO): string {
  if (judge.scope === 'trace_log') return `Logs: ${judge.scope_value}`
  if (judge.scope === 'model') return `Model: ${judge.scope_value}`
  if (judge.scope === 'apikey') return `Key: ${judge.scope_value}`
  if (judge.trace_id) return `Trace #${judge.trace_id}`
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

function formatTime(ts: string): string {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}

onMounted(() => fetchData())
</script>
