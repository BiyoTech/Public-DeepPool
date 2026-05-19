<template>
  <div class="nodes-view space-y-4">
    <!-- 筛选区 -->
    <div class="flex items-center gap-4 flex-wrap">
      <t-select
        v-model="modelFilter"
        placeholder="按模型筛选"
        clearable
        :options="modelOptions"
        class="w-64"
        @change="fetchSessions"
      />
      <t-button theme="default" variant="outline" @click="fetchSessions">
        <template #icon><RefreshIcon /></template>
        刷新
      </t-button>
      <t-tag theme="primary" variant="light" size="large"> 在线设备: {{ sessions.length }} </t-tag>
    </div>

    <!-- 设备表格 -->
    <div class="bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <t-table
        :data="sessions"
        :columns="columns"
        :loading="loading"
        row-key="session_id"
        :hover="true"
        :stripe="true"
        size="medium"
        :empty="'暂无在线设备'"
      >
        <template #status>
          <span class="inline-flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-dp-green animate-pulse"></span>
            <span class="text-dp-green text-sm">在线</span>
          </span>
        </template>
        <template #last_heartbeat="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatTimestamp(row.last_heartbeat) }}</span>
        </template>
      </t-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { RefreshIcon } from 'tdesign-icons-vue-next'
import { getNodeSessions, getNodeStats } from '@/api/admin'

const loading = ref(true)
const sessions = ref<any[]>([])
const modelFilter = ref('')
const stats = ref<{ by_model?: Record<string, number> }>({})

const modelOptions = computed(() => {
  return Object.keys(stats.value.by_model || {}).map((m) => ({ label: m, value: m }))
})

const columns = [
  { colKey: 'simei', title: 'SIMEI', width: 180 },
  { colKey: 'model_name', title: '模型', width: 200 },
  { colKey: 'engine', title: '引擎', width: 100 },
  { colKey: 'user_id', title: 'UserID', width: 100 },
  { colKey: 'session_id', title: 'SessionID', ellipsis: true },
  { colKey: 'last_heartbeat', title: '最后心跳', width: 180, cell: 'last_heartbeat' },
  { colKey: 'status', title: '状态', width: 80, cell: 'status' },
]

let timer: ReturnType<typeof setInterval> | null = null

async function fetchSessions() {
  loading.value = true
  const params: any = {}
  if (modelFilter.value) params.model = modelFilter.value

  const [sessRes, statsRes] = await Promise.all([
    getNodeSessions(params).catch(() => null),
    getNodeStats().catch(() => null),
  ])

  if (sessRes?.data?.data) sessions.value = sessRes.data.data || []
  if (statsRes?.data?.data) stats.value = statsRes.data.data
  loading.value = false
}

function formatTimestamp(ts: number) {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchSessions()
  timer = setInterval(fetchSessions, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>
