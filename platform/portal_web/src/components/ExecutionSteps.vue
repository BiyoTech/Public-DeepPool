<template>
  <div v-if="steps.length" class="mb-3">
    <!-- Toggle button -->
    <button
      class="flex items-center gap-1.5 text-xs font-medium text-dp-muted hover:text-dp-title transition-colors mb-1.5"
      @click="expanded = !expanded"
    >
      <svg
        class="w-3 h-3 transition-transform"
        :class="expanded ? 'rotate-90' : ''"
        fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
      </svg>
      {{ isActive ? $t('misszhao.processing') : $t('misszhao.process_complete') }}
    </button>

    <!-- Step list -->
    <div v-if="expanded" class="space-y-1 pl-1 border-l-2 border-slate-200 ml-1">
      <div
        v-for="(step, i) in steps"
        :key="i"
        class="flex items-start gap-2 pl-3 py-1"
      >
        <!-- Status: done -->
        <span
          v-if="step.status === 'done'"
          class="flex-shrink-0 w-4 h-4 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mt-0.5"
        >
          <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </span>
        <!-- Status: running -->
        <span v-else class="flex-shrink-0 w-4 h-4 rounded-full bg-blue-100 flex items-center justify-center mt-0.5">
          <span class="w-2 h-2 rounded-full bg-dp-blue animate-pulse" />
        </span>

        <!-- Label + detail -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2">
            <span class="text-xs font-medium text-dp-title truncate">{{ step.label }}</span>
            <span v-if="step.duration" class="text-[10px] text-dp-muted/70 whitespace-nowrap">{{ step.duration }}</span>
          </div>
          <p v-if="step.detail" class="text-[11px] text-dp-muted mt-0.5 break-all line-clamp-2">{{ step.detail }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

export interface ExecutionStep {
  type: 'tool_called' | 'tool_output' | 'reasoning' | 'handoff' | 'agent_updated'
  label: string
  detail: string
  status: 'running' | 'done'
  startTime: number
  duration: string
}

defineProps<{
  steps: ExecutionStep[]
  isActive?: boolean
}>()

const expanded = ref(true)
</script>
