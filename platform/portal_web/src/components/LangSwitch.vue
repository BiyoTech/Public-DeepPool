<template>
  <button
    class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-full
           border border-dp-border text-dp-muted hover:text-dp-blue hover:border-dp-blue
           transition-colors duration-200"
    @click="langStore.toggleLocale()"
  >
    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9" />
    </svg>
    <span>{{ langStore.locale === 'zh-CN' ? 'EN' : '中文' }}</span>
  </button>
</template>

<script setup lang="ts">
import { useLangStore } from '@/stores/lang'

const langStore = useLangStore()
</script>
