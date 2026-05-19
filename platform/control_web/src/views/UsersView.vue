<template>
  <div class="users-view space-y-4">
    <!-- Search bar -->
    <div class="flex items-center gap-4">
      <t-input
        v-model="keyword"
        placeholder="搜索用户名、手机号、邮箱"
        clearable
        class="w-80"
        @enter="fetchUsers"
        @clear="fetchUsers"
      >
        <template #prefix-icon><SearchIcon /></template>
      </t-input>
      <t-button theme="primary" @click="fetchUsers">搜索</t-button>
    </div>

    <!-- User table -->
    <div class="bg-dp-bg-3 rounded-xl border border-white/5 overflow-hidden">
      <t-table
        :data="users"
        :columns="columns"
        :loading="loading"
        row-key="id"
        :hover="true"
        :stripe="true"
        size="medium"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #role="{ row }">
          <t-tag :theme="row.role === 'admin' ? 'primary' : 'default'" variant="light" size="small">
            {{ row.role === 'admin' ? '管理员' : '普通用户' }}
          </t-tag>
        </template>
        <template #balance="{ row }">
          <span class="text-sm" :class="row.balance < 0 ? 'text-red-500 font-medium' : 'text-dp-text-1'">
            {{ row.balance.toFixed(4) }}
          </span>
        </template>
        <template #tokens="{ row }">
          <span class="text-sm text-dp-text-2">{{ formatTokenCount(row.total_tokens_used) }}</span>
        </template>
        <template #overdraft="{ row }">
          <div class="text-sm">
            <t-tag v-if="row.allow_overdraft" theme="warning" variant="light" size="small">
              允许欠费 ({{ row.max_overdraft_yuan }}元)
            </t-tag>
            <t-tag v-else theme="default" variant="light" size="small">不允许欠费</t-tag>
          </div>
        </template>
        <template #created_at="{ row }">
          <span class="text-dp-text-2 text-sm">{{ formatTime(row.created_at) }}</span>
        </template>
        <template #op="{ row }">
          <t-button variant="text" theme="primary" size="small" @click="openBillingDialog(row)"> 欠费设置 </t-button>
        </template>
      </t-table>
    </div>

    <!-- Billing settings dialog -->
    <t-dialog
      v-model:visible="dialogVisible"
      header="欠费策略设置"
      :confirm-btn="{ loading: saving }"
      width="480px"
      @confirm="handleSaveBilling"
    >
      <div class="py-2 space-y-1 mb-4">
        <div class="text-sm text-dp-text-2">
          用户：<span class="text-dp-text-1 font-medium">{{ editingUser?.username }}</span>
        </div>
        <div class="text-sm text-dp-text-2">ID：{{ editingUser?.id }}</div>
      </div>
      <t-form label-width="140px">
        <t-form-item label="允许欠费">
          <t-switch v-model="billingForm.allow_overdraft" />
        </t-form-item>
        <t-form-item v-if="billingForm.allow_overdraft" label="最大欠费额度 (元)">
          <t-input-number
            v-model="billingForm.max_overdraft_yuan"
            :min="0"
            :max="1000000"
            :step="10"
            :decimal-places="2"
            suffix="元"
          />
        </t-form-item>
        <div v-if="billingForm.allow_overdraft" class="text-xs text-dp-text-3 ml-[140px]">
          用户钱包余额可透支至 -{{ billingForm.max_overdraft_yuan }} 元。
        </div>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { SearchIcon } from 'tdesign-icons-vue-next'
import { MessagePlugin } from 'tdesign-vue-next'
import { getUsers, updateUserBilling } from '@/api/admin'

interface UserRow {
  id: number
  username: string
  phone: string
  email: string
  role: string
  identity: string
  user_type: string
  allow_overdraft: boolean
  max_overdraft_yuan: number
  balance: number
  total_tokens_used: number
  created_at: string
}

const loading = ref(true)
const keyword = ref('')
const users = ref<UserRow[]>([])

const pagination = reactive({
  current: 1,
  pageSize: 20,
  total: 0,
  showJumper: true,
  showPageSize: true,
  pageSizeOptions: [10, 20, 50],
})

const columns = [
  { colKey: 'id', title: 'ID', width: 80 },
  { colKey: 'username', title: '用户名', width: 150 },
  { colKey: 'phone', title: '手机号', width: 150 },
  { colKey: 'email', title: '邮箱', ellipsis: true },
  { colKey: 'role', title: '角色', width: 100, cell: 'role' },
  { colKey: 'balance', title: '余额(元)', width: 120, cell: 'balance' },
  { colKey: 'total_tokens_used', title: '消耗Token', width: 130, cell: 'tokens' },
  { colKey: 'overdraft', title: '欠费策略', width: 180, cell: 'overdraft' },
  { colKey: 'created_at', title: '注册时间', width: 180, cell: 'created_at' },
  { colKey: 'op', title: '操作', width: 120, cell: 'op', fixed: 'right' },
]

async function fetchUsers() {
  loading.value = true
  const res = await getUsers({
    keyword: keyword.value,
    page: pagination.current,
    page_size: pagination.pageSize,
  }).catch(() => null)
  if (res?.data?.data) {
    users.value = res.data.data.items || []
    pagination.total = res.data.data.total || 0
  }
  loading.value = false
}

function onPageChange(pageInfo: any) {
  pagination.current = pageInfo.current
  pagination.pageSize = pageInfo.pageSize
  fetchUsers()
}

// Billing dialog
const dialogVisible = ref(false)
const saving = ref(false)
const editingUser = ref<UserRow | null>(null)
const billingForm = reactive({
  allow_overdraft: false,
  max_overdraft_yuan: 0,
})

function openBillingDialog(row: UserRow) {
  editingUser.value = row
  billingForm.allow_overdraft = row.allow_overdraft || false
  billingForm.max_overdraft_yuan = row.max_overdraft_yuan || 0
  dialogVisible.value = true
}

async function handleSaveBilling() {
  if (!editingUser.value) return
  saving.value = true
  try {
    await updateUserBilling(editingUser.value.id, {
      allow_overdraft: billingForm.allow_overdraft,
      max_overdraft_yuan: billingForm.allow_overdraft ? billingForm.max_overdraft_yuan : 0,
    })
    MessagePlugin.success('欠费策略已更新')
    dialogVisible.value = false
    fetchUsers()
  } catch (error: any) {
    MessagePlugin.error(error?.response?.data?.message || '更新失败')
  } finally {
    saving.value = false
  }
}

function formatTime(t: string) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function formatTokenCount(tokens: number) {
  if (!tokens || tokens === 0) return '0'
  if (tokens >= 1_000_000_000) return (tokens / 1_000_000_000).toFixed(1) + 'B'
  if (tokens >= 1_000_000) return (tokens / 1_000_000).toFixed(1) + 'M'
  if (tokens >= 1_000) return (tokens / 1_000).toFixed(1) + 'K'
  return String(tokens)
}

onMounted(() => fetchUsers())
</script>
