<template>
  <div class="devices-view space-y-4">
    <!-- 搜索栏 + 批量操作 -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-4">
        <t-input
          v-model="keyword"
          placeholder="搜索 SIMEI、设备 IP"
          clearable
          class="w-80"
          @enter="fetchDevices"
          @clear="fetchDevices"
        >
          <template #prefix-icon><SearchIcon /></template>
        </t-input>
        <t-button theme="primary" @click="fetchDevices">搜索</t-button>
      </div>
      <t-button v-if="selectedRows.length > 0" theme="primary" @click="openBatchAssignDialog">
        批量分配模型 (已选 {{ selectedRows.length }} 台)
      </t-button>
    </div>

    <!-- 设备表格 -->
    <div class="bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <t-table
        :data="devices"
        :columns="columns"
        :loading="loading"
        row-key="deviceID"
        :hover="true"
        :stripe="true"
        size="medium"
        :pagination="pagination"
        :selected-row-keys="selectedRowKeys"
        @page-change="onPageChange"
        @select-change="onSelectChange"
      >
        <!-- 在线状态列：基于 NodeManager 实时连接 -->
        <template #online="{ row }">
          <div class="flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full" :class="row._isOnline ? 'bg-dp-green' : 'bg-dp-text-3'" />
            <span class="text-sm" :class="row._isOnline ? 'text-dp-green' : 'text-dp-text-3'">
              {{ row._isOnline ? '在线' : '离线' }}
            </span>
          </div>
        </template>
        <!-- 合法性状态列：来自数据库 user_devices.status -->
        <template #device_status="{ row }">
          <t-tag
            size="small"
            :theme="row.status === 'active' ? 'success' : row.status === 'blocked' ? 'danger' : 'warning'"
            variant="light"
          >
            {{ deviceStatusLabel(row.status) }}
          </t-tag>
        </template>
        <!-- 已分配模型列 -->
        <template #assigned_models="{ row }">
          <div v-if="row._assignedModels && row._assignedModels.length > 0" class="flex flex-wrap gap-1">
            <t-tag
              v-for="(m, idx) in row._assignedModels.slice(0, 3)"
              :key="idx"
              size="small"
              variant="light"
              :theme="m.source === 'manual' ? 'primary' : 'default'"
            >
              {{ m.model_name }}
            </t-tag>
            <t-popup
              v-if="row._assignedModels.length > 3"
              placement="top"
              :content="row._assignedModels.map((m: any) => m.model_name).join(', ')"
            >
              <t-tag size="small" variant="light">+{{ row._assignedModels.length - 3 }}</t-tag>
            </t-popup>
          </div>
          <span v-else class="text-dp-text-3 text-sm">未分配</span>
        </template>
        <!-- 配置列 -->
        <template #device_config="{ row }">
          <t-popup :content="row.device_config" placement="top" :show-arrow="true">
            <span class="text-dp-text-2 text-sm truncate block max-w-xs cursor-pointer">
              {{ truncateConfig(row.device_config) }}
            </span>
          </t-popup>
        </template>
        <!-- 注册时间 -->
        <template #created_at="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatTime(row.created_at) }}</span>
        </template>
        <!-- 操作列 -->
        <template #op="{ row }">
          <t-button variant="text" theme="primary" size="small" @click="openAssignDialog(row)"> 分配模型 </t-button>
        </template>
      </t-table>
    </div>

    <!-- 模型分配弹窗 -->
    <t-dialog
      v-model:visible="assignDialogVisible"
      :header="assignDialogTitle"
      :confirm-btn="{ loading: assigning }"
      width="640px"
      @confirm="handleAssign"
    >
      <div class="py-2">
        <p class="text-dp-text-2 text-sm mb-4">从平台已启用的模型中选择要分配给设备的模型列表：</p>
        <!-- 模型多选 -->
        <t-checkbox-group v-model="selectedModelIds" class="flex flex-col gap-2">
          <div
            v-for="model in enabledModels"
            :key="model.id"
            class="flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-150 cursor-pointer"
            :class="
              selectedModelIds.includes(model.id)
                ? 'bg-dp-blue/5 border-dp-blue/30'
                : 'bg-dp-bg-4 border-white/5 hover:border-white/10'
            "
            @click="toggleModelSelection(model.id)"
          >
            <t-checkbox :value="model.id" @click.stop />
            <div class="flex-1 min-w-0">
              <div class="text-sm text-dp-text-1 font-medium">{{ model.model_name }}</div>
              <div class="text-xs text-dp-text-3 truncate">{{ model.repo_id }}</div>
            </div>
            <div class="text-xs text-dp-text-3 shrink-0">
              内存≥{{ model.min_memory_gb || 0 }}G / 显存≥{{ model.min_gpu_memory_gb || 0 }}G
            </div>
          </div>
        </t-checkbox-group>
        <div v-if="enabledModels.length === 0" class="text-dp-text-3 text-sm py-8 text-center">
          暂无可分配模型（仅 DeepNode 类型的模型可分配给设备）
        </div>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { SearchIcon } from 'tdesign-icons-vue-next'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  getDevices,
  getNodeSessions,
  getEnabledModels,
  getDeviceAssignments,
  assignModelsToDevice,
  batchAssignModels,
} from '@/api/admin'

// ─── 列表数据 ───

const loading = ref(true)
const keyword = ref('')
const devices = ref<any[]>([])
const selectedRowKeys = ref<number[]>([])
const selectedRows = ref<any[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
})

const columns = [
  { colKey: 'row-select', type: 'multiple', width: 50 },
  { colKey: 'deviceID', title: 'ID', width: 70 },
  { colKey: 'simei', title: 'SIMEI', width: 180 },
  { colKey: 'online', title: '在线', width: 80, cell: 'online' },
  { colKey: 'device_status', title: '合法性', width: 90, cell: 'device_status' },
  { colKey: 'assigned_models', title: '已分配模型', cell: 'assigned_models', width: 280 },
  { colKey: 'user_id', title: 'UserID', width: 80 },
  { colKey: 'device_ip', title: '设备 IP', width: 130 },
  { colKey: 'device_config', title: '配置', cell: 'device_config', ellipsis: true },
  { colKey: 'created_at', title: '注册时间', width: 170, cell: 'created_at' },
  { colKey: 'op', title: '操作', width: 100, cell: 'op', fixed: 'right' },
]

async function fetchDevices() {
  loading.value = true

  // 并行拉取设备列表 & NodeManager 在线 session 列表
  const [devRes, sessRes] = await Promise.all([
    getDevices({
      keyword: keyword.value,
      page: pagination.current,
      page_size: pagination.pageSize,
    }).catch(() => null),
    getNodeSessions().catch(() => null),
  ])

  if (devRes?.data?.data) {
    const items = devRes.data.data.items || []

    // 构建在线 simei 集合（来自 NodeManager 实时连接表，O(1) 查找）
    const onlineSimeis = new Set<string>((sessRes?.data?.data || []).map((s: any) => s.simei))

    // 为每个设备附加分配模型信息（并行请求）+ 在线状态
    const enriched = await Promise.all(
      items.map(async (device: any) => {
        const aRes = await getDeviceAssignments(device.deviceID).catch(() => null)
        const aData = aRes?.data?.data
        // 后端返回的 data 可能是数组或 { items: [...] }
        device._assignedModels = Array.isArray(aData) ? aData : aData?.items || []
        // 在线状态以 NodeManager 实时连接为准，覆盖数据库 status
        device._isOnline = onlineSimeis.has(device.simei)
        return device
      }),
    )
    devices.value = enriched
    pagination.total = devRes.data.data.total || 0
  }
  loading.value = false
}

// ─── 自动刷新（30 秒间隔，保持在线状态较为实时） ───

let refreshTimer: ReturnType<typeof setInterval> | null = null

function onPageChange(pageInfo: any) {
  pagination.current = pageInfo.current
  pagination.pageSize = pageInfo.pageSize
  fetchDevices()
}

function onSelectChange(keys: number[], context: any) {
  selectedRowKeys.value = keys
  selectedRows.value = context.selectedRowData || []
}

// ─── 模型分配弹窗 ───

const assignDialogVisible = ref(false)
const assigning = ref(false)
const enabledModels = ref<any[]>([])
const selectedModelIds = ref<number[]>([])

// 当前操作模式：single 单台 / batch 批量
const assignMode = ref<'single' | 'batch'>('single')
const assignDeviceId = ref(0)
const assignDeviceSimei = ref('')

const assignDialogTitle = computed(() => {
  if (assignMode.value === 'batch') {
    return `批量分配模型 (已选 ${selectedRows.value.length} 台设备)`
  }
  return `分配模型 — ${assignDeviceSimei.value}`
})

async function loadEnabledModels() {
  const res = await getEnabledModels().catch(() => null)
  const data = res?.data?.data
  const all = Array.isArray(data) ? data : data?.items || []
  // Only deepnode models can be assigned to physical devices
  enabledModels.value = all.filter((m: any) => m.vendor_type === 'deepnode')
}

async function openAssignDialog(row: any) {
  assignMode.value = 'single'
  assignDeviceId.value = row.deviceID
  assignDeviceSimei.value = row.simei
  await loadEnabledModels()
  // 预选当前已分配的模型
  selectedModelIds.value = (row._assignedModels || []).map((m: any) => m.model_id)
  assignDialogVisible.value = true
}

async function openBatchAssignDialog() {
  assignMode.value = 'batch'
  assignDeviceId.value = 0
  assignDeviceSimei.value = ''
  await loadEnabledModels()
  selectedModelIds.value = []
  assignDialogVisible.value = true
}

function toggleModelSelection(modelId: number) {
  const idx = selectedModelIds.value.indexOf(modelId)
  if (idx >= 0) {
    selectedModelIds.value.splice(idx, 1)
  } else {
    selectedModelIds.value.push(modelId)
  }
}

async function handleAssign() {
  assigning.value = true

  const res =
    assignMode.value === 'single'
      ? await assignModelsToDevice({
          device_id: assignDeviceId.value,
          model_ids: selectedModelIds.value,
        }).catch(() => null)
      : await batchAssignModels({
          device_ids: selectedRows.value.map((r: any) => r.deviceID),
          model_ids: selectedModelIds.value,
        }).catch(() => null)

  assigning.value = false

  if (res?.data?.code === 0) {
    MessagePlugin.success('分配成功')
    assignDialogVisible.value = false
    selectedRowKeys.value = []
    selectedRows.value = []
    fetchDevices()
  } else {
    MessagePlugin.error(res?.data?.message || '分配失败')
  }
}

// ─── 辅助函数 ───

const DEVICE_STATUS_LABELS: Record<string, string> = {
  active: '正常',
  blocked: '已屏蔽',
  cheating: '作弊',
}

function deviceStatusLabel(status: string): string {
  return DEVICE_STATUS_LABELS[status] || status || '未知'
}

function truncateConfig(config: string) {
  if (!config) return '-'
  return config.length > 60 ? config.slice(0, 60) + '...' : config
}

function formatTime(t: string) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchDevices()
  refreshTimer = setInterval(fetchDevices, 30_000) // 30秒自动刷新在线状态
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
