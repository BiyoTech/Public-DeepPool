<template>
  <div>
    <!-- ========== Hero ========== -->
    <section class="relative overflow-hidden bg-gradient-to-b from-blue-50/80 via-white to-white">
      <div class="absolute inset-0 pointer-events-none">
        <div class="absolute inset-0 opacity-[0.03]"
             style="background-image: linear-gradient(#3B82F6 1px, transparent 1px), linear-gradient(90deg, #3B82F6 1px, transparent 1px); background-size: 60px 60px;" />
        <div class="absolute -top-24 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-blue-200/30 rounded-full blur-3xl" />
        <div class="absolute top-40 -right-20 w-[300px] h-[300px] bg-purple-200/20 rounded-full blur-3xl" />
      </div>

      <div class="relative max-w-5xl mx-auto px-6 pt-24 pb-20 text-center">
        <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold text-dp-title leading-tight tracking-tight">
          {{ $t('home.hero.title') }}
        </h1>
        <div class="mt-5 flex items-center justify-center gap-3 flex-wrap">
          <span class="inline-flex items-center px-4 py-1.5 rounded-full text-sm font-semibold bg-emerald-100 text-emerald-700 border border-emerald-200 shadow-sm">
            {{ $t('home.hero.tag_cost') }}
          </span>
          <span class="inline-flex items-center px-4 py-1.5 rounded-full text-sm font-semibold bg-blue-100 text-blue-700 border border-blue-200 shadow-sm">
            {{ $t('home.hero.tag_reliable') }}
          </span>
          <span class="inline-flex items-center px-4 py-1.5 rounded-full text-sm font-semibold bg-violet-100 text-violet-700 border border-violet-200 shadow-sm">
            {{ $t('home.hero.tag_api') }}
          </span>
        </div>
        <p class="mt-6 text-lg md:text-xl text-dp-muted max-w-2xl mx-auto leading-relaxed">
          {{ $t('home.hero.subtitle') }}
        </p>
        <p v-if="authStore.isLoggedIn && authStore.user?.username" class="mt-4 text-base text-dp-blue font-medium">
          {{ $t('home.hero.welcome', { name: authStore.user.username }) }}
        </p>
        <div class="mt-10 flex items-center justify-center gap-4 flex-wrap">
          <a
            href="https://deeppool.tech/service"
            class="px-8 py-3 rounded-full bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
                   shadow-lg shadow-blue-500/25 hover:shadow-xl hover:shadow-blue-500/30
                   hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all duration-300 transform hover:-translate-y-0.5"
          >
            {{ $t('home.hero.cta_consumer') }}
          </a>
          <router-link
            to="/docs/getting-started/quickstart-provider"
            class="px-8 py-3 rounded-full border border-slate-300 text-dp-muted font-medium
                   hover:border-dp-blue hover:text-dp-blue transition-all duration-300 transform hover:-translate-y-0.5"
          >
            {{ $t('home.hero.cta_provider') }}
          </router-link>
          <router-link
            to="/docs/getting-started/custom-hybrid-model"
            class="px-8 py-3 rounded-full border border-slate-300 text-dp-muted font-medium
                   hover:border-dp-blue hover:text-dp-blue transition-all duration-300 transform hover:-translate-y-0.5"
          >
            {{ $t('home.hero.cta_custom_hybrid') }}
          </router-link>
        </div>
      </div>
    </section>

    <!-- ========== Core Advantages (6 cards, 2×3 grid) ========== -->
    <section class="bg-dp-bg-section py-20">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-3xl font-bold text-dp-title text-center mb-4">{{ $t('home.features.title') }}</h2>
        <p class="text-center text-dp-muted mb-12 max-w-2xl mx-auto">{{ $t('home.features.subtitle') }}</p>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="(feature, idx) in features"
            :key="idx"
            class="group bg-white rounded-2xl p-8 shadow-sm hover:shadow-md border border-transparent
                   hover:border-blue-100 transition-all duration-300 transform hover:-translate-y-1"
          >
            <div class="h-0.5 w-12 rounded-full mb-6" :class="feature.accentClass" />
            <div class="w-12 h-12 rounded-xl flex items-center justify-center mb-5 transition-colors"
                 :class="feature.iconBgClass">
              <component :is="feature.icon" :class="feature.iconColorClass" />
            </div>
            <h3 class="text-lg font-semibold text-dp-title mb-3">{{ feature.title }}</h3>
            <p class="text-sm text-dp-muted leading-relaxed">{{ feature.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ========== Architecture Flow ========== -->
    <section class="py-20 bg-white">
      <div class="max-w-5xl mx-auto px-6">
        <h2 class="text-3xl font-bold text-dp-title text-center mb-4">{{ $t('home.arch.title') }}</h2>
        <p class="text-center text-dp-muted mb-14 max-w-2xl mx-auto">{{ $t('home.arch.subtitle') }}</p>

        <!-- Horizontal flow -->
        <div class="flex flex-col md:flex-row items-stretch gap-0 justify-center">
          <div v-for="(step, idx) in archSteps" :key="idx"
               class="flex items-center"
          >
            <!-- Step card -->
            <div class="flex flex-col items-center text-center w-40 md:w-44">
              <div class="w-16 h-16 rounded-2xl flex items-center justify-center mb-3 shadow-sm"
                   :class="step.bgClass">
                <component :is="step.icon" :class="step.iconClass" />
              </div>
              <span class="text-xs font-bold text-dp-blue mb-1">{{ step.label }}</span>
              <span class="text-[11px] text-dp-muted leading-snug">{{ step.desc }}</span>
            </div>
            <!-- Arrow between cards -->
            <svg v-if="idx < archSteps.length - 1"
                 class="hidden md:block w-8 h-8 text-slate-300 shrink-0 mx-1"
                 fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
            <svg v-if="idx < archSteps.length - 1"
                 class="md:hidden w-6 h-6 text-slate-300 my-2 rotate-90"
                 fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
            </svg>
          </div>
        </div>

        <!-- Three vendor types -->
        <div class="mt-14 grid grid-cols-1 md:grid-cols-3 gap-4 max-w-3xl mx-auto">
          <div v-for="(vt, idx) in vendorTypes" :key="idx"
               class="rounded-xl border p-4 text-center" :class="vt.borderClass">
            <span class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-bold mb-2" :class="vt.badgeClass">
              {{ vt.badge }}
            </span>
            <p class="text-sm font-medium text-dp-title">{{ vt.title }}</p>
            <p class="text-xs text-dp-muted mt-1">{{ vt.desc }}</p>
          </div>
        </div>
      </div>
    </section>

    <!-- ========== Platform Stats ========== -->
    <section class="py-20 bg-dp-bg-section">
      <div class="max-w-5xl mx-auto px-6">
        <h2 class="text-3xl font-bold text-dp-title text-center mb-12">{{ $t('home.stats.title') }}</h2>
        <div class="flex flex-wrap justify-center gap-0">
          <div
            v-for="(stat, idx) in stats"
            :key="idx"
            class="flex-1 min-w-[200px] text-center px-8 py-4"
            :class="idx < stats.length - 1 ? 'border-r border-slate-200' : ''"
          >
            <div class="text-4xl md:text-5xl font-bold bg-gradient-to-r from-dp-blue to-dp-blue-dark bg-clip-text text-transparent tabular-nums">
              {{ animatedStats[idx] }}
            </div>
            <div class="mt-2 text-sm text-dp-muted">{{ stat.label }}</div>
          </div>
        </div>
      </div>
    </section>

    <!-- ========== Quick Start ========== -->
    <section class="py-20 bg-white">
      <div class="max-w-6xl mx-auto px-6">
        <h2 class="text-3xl font-bold text-dp-title text-center mb-12">{{ $t('home.quickstart.title') }}</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
          <!-- Provider -->
          <div class="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-all duration-300 border border-transparent hover:border-blue-100">
            <div class="w-14 h-14 rounded-2xl bg-blue-50 flex items-center justify-center mb-6">
              <svg class="w-7 h-7 text-dp-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-dp-title mb-2">{{ $t('home.quickstart.provider.title') }}</h3>
            <p class="text-sm text-dp-muted mb-6">{{ $t('home.quickstart.provider.desc') }}</p>
            <ol class="space-y-3 mb-8">
              <li v-for="i in 3" :key="i" class="flex items-start gap-3">
                <span class="flex-shrink-0 w-6 h-6 rounded-full bg-blue-50 text-dp-blue text-xs font-bold flex items-center justify-center">{{ i }}</span>
                <span class="text-sm text-dp-body">{{ $t(`home.quickstart.provider.step${i}`) }}</span>
              </li>
            </ol>
            <router-link
              to="/docs/getting-started/quickstart-provider"
              class="inline-flex items-center px-6 py-2.5 rounded-full bg-gradient-to-r from-dp-blue to-dp-blue-dark
                     text-white text-sm font-medium shadow-sm hover:shadow-md transition-all duration-200"
            >
              {{ $t('home.quickstart.provider.cta') }}
            </router-link>
          </div>

          <!-- Consumer -->
          <div class="bg-white rounded-2xl p-8 shadow-sm hover:shadow-md transition-all duration-300 border border-transparent hover:border-purple-100">
            <div class="w-14 h-14 rounded-2xl bg-purple-50 flex items-center justify-center mb-6">
              <svg class="w-7 h-7 text-dp-purple" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
              </svg>
            </div>
            <h3 class="text-xl font-bold text-dp-title mb-2">{{ $t('home.quickstart.consumer.title') }}</h3>
            <p class="text-sm text-dp-muted mb-6">{{ $t('home.quickstart.consumer.desc') }}</p>
            <ol class="space-y-3 mb-8">
              <li v-for="i in 3" :key="i" class="flex items-start gap-3">
                <span class="flex-shrink-0 w-6 h-6 rounded-full bg-purple-50 text-dp-purple text-xs font-bold flex items-center justify-center">{{ i }}</span>
                <span class="text-sm text-dp-body">{{ $t(`home.quickstart.consumer.step${i}`) }}</span>
              </li>
            </ol>
            <router-link
              to="/register"
              class="inline-flex items-center px-6 py-2.5 rounded-full bg-gradient-to-r from-dp-purple to-dp-purple-dark
                     text-white text-sm font-medium shadow-sm hover:shadow-md transition-all duration-200"
            >
              {{ $t('home.quickstart.consumer.cta') }}
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getPublicStats } from '@/api/public'

const { t } = useI18n()
const authStore = useAuthStore()

// ---- SVG Icon Components ----

function svgIcon(d: string) {
  return {
    render: () => h('svg', { class: 'w-6 h-6', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d }),
    ]),
  }
}

// Cost-effective: currency/dollar
const IconCost = svgIcon('M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z')
// Smart routing: route/arrows
const IconSmart = svgIcon('M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5')
// Reliability: shield
const IconReliable = svgIcon('M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z')
// API compatible: code bracket
const IconApi = svgIcon('M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5')
// Custom routing: adjustments/sliders
const IconCustomRouting = svgIcon('M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75')
// Global leading models: globe
const IconGlobalModels = svgIcon('M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418')

// ---- Feature Cards (6) ----

const features = computed(() => [
  {
    icon: IconCost,
    title: t('home.features.cost.title'),
    desc: t('home.features.cost.desc'),
    accentClass: 'bg-gradient-to-r from-emerald-400 to-emerald-600',
    iconBgClass: 'bg-emerald-50 group-hover:bg-emerald-100',
    iconColorClass: 'w-6 h-6 text-emerald-600',
  },
  {
    icon: IconSmart,
    title: t('home.features.smart.title'),
    desc: t('home.features.smart.desc'),
    accentClass: 'bg-gradient-to-r from-dp-blue to-dp-blue-dark',
    iconBgClass: 'bg-blue-50 group-hover:bg-blue-100',
    iconColorClass: 'w-6 h-6 text-dp-blue',
  },
  {
    icon: IconReliable,
    title: t('home.features.reliable.title'),
    desc: t('home.features.reliable.desc'),
    accentClass: 'bg-gradient-to-r from-amber-400 to-amber-600',
    iconBgClass: 'bg-amber-50 group-hover:bg-amber-100',
    iconColorClass: 'w-6 h-6 text-amber-600',
  },
  {
    icon: IconApi,
    title: t('home.features.api.title'),
    desc: t('home.features.api.desc'),
    accentClass: 'bg-gradient-to-r from-violet-400 to-violet-600',
    iconBgClass: 'bg-violet-50 group-hover:bg-violet-100',
    iconColorClass: 'w-6 h-6 text-violet-600',
  },
  {
    icon: IconCustomRouting,
    title: t('home.features.custom_routing.title'),
    desc: t('home.features.custom_routing.desc'),
    accentClass: 'bg-gradient-to-r from-rose-400 to-rose-600',
    iconBgClass: 'bg-rose-50 group-hover:bg-rose-100',
    iconColorClass: 'w-6 h-6 text-rose-600',
  },
  {
    icon: IconGlobalModels,
    title: t('home.features.global_models.title'),
    desc: t('home.features.global_models.desc'),
    accentClass: 'bg-gradient-to-r from-cyan-400 to-cyan-600',
    iconBgClass: 'bg-cyan-50 group-hover:bg-cyan-100',
    iconColorClass: 'w-6 h-6 text-cyan-600',
  },
])

// ---- Architecture Flow Steps ----

// Larger icons for arch flow
function archIcon(d: string) {
  return {
    render: () => h('svg', { class: 'w-8 h-8', fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d }),
    ]),
  }
}

const ArchUser = archIcon('M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z')
const ArchGateway = archIcon('M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418')
const ArchRoute = archIcon('M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5')
const ArchInfer = archIcon('M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z')

const archSteps = computed(() => [
  {
    icon: ArchUser,
    label: t('home.arch.step1_label'),
    desc: t('home.arch.step1_desc'),
    bgClass: 'bg-blue-50',
    iconClass: 'w-8 h-8 text-dp-blue',
  },
  {
    icon: ArchGateway,
    label: t('home.arch.step2_label'),
    desc: t('home.arch.step2_desc'),
    bgClass: 'bg-violet-50',
    iconClass: 'w-8 h-8 text-violet-600',
  },
  {
    icon: ArchRoute,
    label: t('home.arch.step3_label'),
    desc: t('home.arch.step3_desc'),
    bgClass: 'bg-amber-50',
    iconClass: 'w-8 h-8 text-amber-600',
  },
  {
    icon: ArchInfer,
    label: t('home.arch.step4_label'),
    desc: t('home.arch.step4_desc'),
    bgClass: 'bg-emerald-50',
    iconClass: 'w-8 h-8 text-emerald-600',
  },
])

// ---- Vendor Type Cards ----

const vendorTypes = computed(() => [
  {
    badge: 'DeepNode',
    title: t('home.arch.vt_deepnode_title'),
    desc: t('home.arch.vt_deepnode_desc'),
    badgeClass: 'bg-blue-100 text-dp-blue',
    borderClass: 'border-blue-200',
  },
  {
    badge: 'Provider',
    title: t('home.arch.vt_provider_title'),
    desc: t('home.arch.vt_provider_desc'),
    badgeClass: 'bg-emerald-100 text-emerald-700',
    borderClass: 'border-emerald-200',
  },
  {
    badge: 'Hybrid',
    title: t('home.arch.vt_hybrid_title'),
    desc: t('home.arch.vt_hybrid_desc'),
    badgeClass: 'bg-amber-100 text-amber-700',
    borderClass: 'border-amber-200',
  },
])

// ---- Platform Stats ----

const statsData = ref({ online_devices: 0, total_users: 0, total_devices: 0 })
const animatedStats = ref(['0', '0', '0'])

const stats = computed(() => [
  { label: t('home.stats.online_devices'), value: statsData.value.online_devices },
  { label: t('home.stats.total_users'), value: statsData.value.total_users },
  { label: t('home.stats.total_devices'), value: statsData.value.total_devices },
])

function animateCount(target: number, index: number) {
  const duration = 1500
  const start = performance.now()
  function step(now: number) {
    const progress = Math.min((now - start) / duration, 1)
    const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress)
    animatedStats.value[index] = Math.floor(eased * target).toLocaleString()
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

onMounted(async () => {
  try {
    const res = await getPublicStats()
    const data = res.data?.data || res.data
    statsData.value = {
      online_devices: data.online_devices || 0,
      total_users: data.total_users || 0,
      total_devices: data.total_devices || 0,
    }
  } catch {
    statsData.value = { online_devices: 0, total_users: 0, total_devices: 0 }
  }
  stats.value.forEach((s, i) => animateCount(s.value, i))
})
</script>
