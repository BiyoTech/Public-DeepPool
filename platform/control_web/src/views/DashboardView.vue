<template>
  <div class="dashboard-view space-y-6">
    <!-- 统计卡片 -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="bg-dp-bg-3 rounded-xl p-6 border border-white/5 hover:border-white/10 transition-all duration-200"
      >
        <div class="flex items-center justify-between mb-4">
          <div
            class="w-12 h-12 rounded-xl flex items-center justify-center"
            :class="card.bgClass"
          >
            <component :is="card.icon" class="w-6 h-6" :class="card.iconClass" />
          </div>
          <t-tag v-if="!loading" variant="light" theme="success" size="small">实时</t-tag>
        </div>
        <div class="text-3xl font-bold text-dp-text-1 mb-1">
          <t-skeleton v-if="loading" :row-col="[{ width: '60px', height: '36px' }]" />
          <span v-else>{{ card.value }}</span>
        </div>
        <div class="text-sm text-dp-text-3">{{ card.label }}</div>
      </div>
    </div>

    <!-- 下方预留区域 -->
    <div class="bg-dp-bg-3 rounded-xl p-6 border border-white/5">
      <h3 class="text-dp-text-1 font-medium mb-4">模型分布统计</h3>
      <div v-if="Object.keys(stats.by_model || {}).length === 0" class="text-dp-text-3 text-sm py-8 text-center">
        暂无在线设备数据
      </div>
      <div v-else class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div
          v-for="(count, model) in stats.by_model"
          :key="model"
          class="bg-dp-bg-4 rounded-lg p-4 border border-white/5"
        >
          <div class="text-dp-text-2 text-sm mb-1 truncate" :title="String(model)">{{ model }}</div>
          <div class="text-xl font-bold text-dp-blue">{{ count }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { CpuIcon, UserIcon, DeviceIcon } from 'tdesign-icons-vue-next'
import { getDashboard, getNodeStats } from '@/api/admin'

const loading = ref(true)
const dashboard = ref({ online_devices: 0, total_users: 0, total_devices: 0 })
const stats = ref<{ total?: number; by_model?: Record<string, number> }>({})

const statCards = computed(() => [
  {
    key: 'online',
    label: '在线设备数',
    value: dashboard.value.online_devices,
    icon: CpuIcon,
    bgClass: 'bg-dp-blue/10',
    iconClass: 'text-dp-blue',
  },
  {
    key: 'users',
    label: '注册用户数',
    value: dashboard.value.total_users,
    icon: UserIcon,
    bgClass: 'bg-dp-green/10',
    iconClass: 'text-dp-green',
  },
  {
    key: 'devices',
    label: '注册设备数',
    value: dashboard.value.total_devices,
    icon: DeviceIcon,
    bgClass: 'bg-purple-500/10',
    iconClass: 'text-purple-400',
  },
])

let timer: ReturnType<typeof setInterval> | null = null

async function fetchData() {
  const [dashRes, statsRes] = await Promise.all([
    getDashboard().catch(() => null),
    getNodeStats().catch(() => null),
  ])
  if (dashRes?.data?.data) dashboard.value = dashRes.data.data
  if (statsRes?.data?.data) stats.value = statsRes.data.data
  loading.value = false
}

onMounted(() => {
  fetchData()
  timer = setInterval(fetchData, 15000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
