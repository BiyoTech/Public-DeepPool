<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Top bar with title -->
    <div class="bg-white border-b border-slate-200">
      <div class="max-w-7xl mx-auto px-6 py-4">
        <h1 class="text-xl font-bold text-dp-title">{{ $t('experiment.title') }}</h1>
        <p class="text-sm text-dp-muted mt-1">{{ $t('experiment.subtitle') }}</p>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-6 flex gap-6">
      <!-- Left sidebar navigation -->
      <aside class="w-48 flex-shrink-0">
        <nav class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="flex items-center gap-3 px-4 py-3 text-sm font-medium transition-colors border-b border-slate-100 last:border-0"
            :class="isActive(item.path)
              ? 'text-dp-blue bg-blue-50/60'
              : 'text-dp-muted hover:text-dp-title hover:bg-slate-50'"
          >
            <component :is="item.icon" class="w-4 h-4" />
            {{ item.label }}
            <span
              v-if="item.badge"
              class="ml-auto text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-400 font-normal"
            >{{ item.badge }}</span>
          </router-link>
        </nav>
      </aside>

      <!-- Main content area -->
      <main class="flex-1 min-w-0">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, h } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const route = useRoute()

// SVG icon components as render functions
const OverviewIcon = { render: () => h('svg', { class: 'w-4 h-4', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z' })
])}
const TraceIcon = { render: () => h('svg', { class: 'w-4 h-4', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.808-3.808-9.98 0-13.788m13.788 0c3.808 3.808 3.808 9.98 0 13.788M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z' })
])}
const JudgeIcon = { render: () => h('svg', { class: 'w-4 h-4', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.97zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.97z' })
])}
const EvaluateIcon = { render: () => h('svg', { class: 'w-4 h-4', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z' })
])}

const navItems = computed(() => [
  { path: '/experiment/overview', label: t('experiment.nav.overview'), icon: OverviewIcon },
  { path: '/experiment/trace', label: t('experiment.nav.trace'), icon: TraceIcon },
  { path: '/experiment/judge', label: t('experiment.nav.judge'), icon: JudgeIcon },
  { path: '/experiment/evaluate', label: t('experiment.nav.evaluate'), icon: EvaluateIcon, badge: t('experiment.coming_soon') },
])

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>
