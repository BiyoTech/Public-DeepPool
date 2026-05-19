<template>
  <div class="space-y-6">
    <!-- Tab navigation -->
    <t-tabs v-model="activeTab">
      <t-tab-panel value="new-user" label="新用户运营">
        <!-- Signup bonus config -->
        <div class="mt-4 space-y-4">
          <div class="bg-dp-bg-2 rounded-lg p-6 border border-white/5">
            <h3 class="text-base font-medium text-dp-text-1 mb-4">注册赠送 Token 设置</h3>
            <p class="text-sm text-dp-text-3 mb-4">新用户注册时自动赠送的免费 Token 数量。设置为 0 表示关闭赠送。</p>
            <div class="flex items-end gap-4">
              <div class="w-80">
                <t-input-number
                  v-model="signupBonusTokens"
                  :min="0"
                  :max="100000000"
                  :step="100000"
                  theme="normal"
                  placeholder="Token 数量"
                  class="w-full"
                />
              </div>
              <t-button theme="primary" :loading="savingConfig" @click="saveSignupBonus"> 保存设置 </t-button>
            </div>
            <p class="text-xs text-dp-text-3 mt-2">当前设置: {{ formatTokens(signupBonusTokens) }} tokens</p>
          </div>
        </div>
      </t-tab-panel>

      <t-tab-panel value="existing-user" label="存量用户运营">
        <div class="mt-4 space-y-6">
          <!-- User selector -->
          <div class="bg-dp-bg-2 rounded-lg p-6 border border-white/5">
            <h3 class="text-base font-medium text-dp-text-1 mb-4">选择用户</h3>
            <div class="flex items-center gap-4">
              <t-input
                v-model="userKeyword"
                placeholder="输入用户名/邮箱搜索"
                clearable
                class="w-80"
                @enter="searchUsers"
              />
              <t-button @click="searchUsers">搜索</t-button>
            </div>
            <div v-if="userList.length" class="mt-3">
              <t-select v-model="selectedUserId" placeholder="选择用户" class="w-80" @change="onUserSelected">
                <t-option
                  v-for="u in userList"
                  :key="u.id"
                  :value="u.id"
                  :label="`${u.username} (${u.email}) #${u.id}`"
                />
              </t-select>
            </div>
          </div>

          <!-- Token grant section -->
          <div v-if="selectedUserId" class="bg-dp-bg-2 rounded-lg p-6 border border-white/5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-base font-medium text-dp-text-1">
                Token 包管理
                <span class="text-sm text-dp-blue ml-2"> 剩余: {{ formatTokens(remainingTokens) }} </span>
              </h3>
              <t-button theme="primary" size="small" @click="showGrantDialog = true"> 赠送 Token </t-button>
            </div>

            <t-table
              :data="grants"
              :columns="grantColumns"
              :loading="loadingGrants"
              row-key="id"
              size="small"
              stripe
              :max-height="300"
            >
              <template #grant_type="{ row }">
                <t-tag :theme="row.grant_type === 'signup_bonus' ? 'primary' : 'success'" variant="light" size="small">
                  {{ row.grant_type === 'signup_bonus' ? '注册赠送' : '手动赠送' }}
                </t-tag>
              </template>
              <template #remaining_tokens="{ row }">
                <span :class="row.remaining_tokens > 0 ? 'text-dp-green' : 'text-dp-text-3'">
                  {{ formatTokens(row.remaining_tokens) }}
                </span>
              </template>
              <template #expires_at="{ row }">
                {{ row.expires_at ? formatDate(row.expires_at) : '永不过期' }}
              </template>
              <template #op="{ row }">
                <t-popconfirm content="确认删除此 Token 包？" @confirm="deleteGrant(row.id)">
                  <t-button theme="danger" variant="text" size="small">删除</t-button>
                </t-popconfirm>
              </template>
            </t-table>
          </div>

          <!-- Discount section -->
          <div v-if="selectedUserId" class="bg-dp-bg-2 rounded-lg p-6 border border-white/5">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-base font-medium text-dp-text-1">折扣管理</h3>
              <t-button theme="primary" size="small" @click="showDiscountDialog = true"> 设置折扣 </t-button>
            </div>

            <t-table
              :data="discounts"
              :columns="discountColumns"
              :loading="loadingDiscounts"
              row-key="id"
              size="small"
              stripe
              :max-height="300"
            >
              <template #discount_rate="{ row }">
                <t-tag theme="warning" variant="light" size="small">
                  {{ (row.discount_rate * 10).toFixed(1) }} 折
                </t-tag>
              </template>
              <template #status="{ row }">
                <t-tag :theme="isDiscountActive(row) ? 'success' : 'default'" variant="light" size="small">
                  {{ isDiscountActive(row) ? '生效中' : isDiscountExpired(row) ? '已过期' : '未生效' }}
                </t-tag>
              </template>
              <template #effective_from="{ row }">
                {{ formatDate(row.effective_from) }}
              </template>
              <template #effective_to="{ row }">
                {{ formatDate(row.effective_to) }}
              </template>
              <template #op="{ row }">
                <t-popconfirm content="确认删除此折扣？" @confirm="deleteDiscountItem(row.id)">
                  <t-button theme="danger" variant="text" size="small">删除</t-button>
                </t-popconfirm>
              </template>
            </t-table>
          </div>
        </div>
      </t-tab-panel>
    </t-tabs>

    <!-- Grant Token Dialog -->
    <t-dialog
      v-model:visible="showGrantDialog"
      header="赠送 Token"
      :confirm-on-enter="true"
      :on-confirm="submitGrant"
      :confirm-btn="{ loading: submittingGrant }"
    >
      <t-form :data="grantForm" layout="vertical">
        <t-form-item label="Token 数量">
          <t-input-number
            v-model="grantForm.tokens"
            :min="1"
            :max="100000000"
            :step="100000"
            theme="normal"
            class="w-full"
          />
        </t-form-item>
        <t-form-item label="过期时间（可选）">
          <t-date-picker
            v-model="grantForm.expires_at"
            enable-time-picker
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="不设置则永不过期"
            clearable
            class="w-full"
          />
        </t-form-item>
        <t-form-item label="备注">
          <t-input v-model="grantForm.remark" placeholder="赠送备注" />
        </t-form-item>
      </t-form>
    </t-dialog>

    <!-- Discount Dialog -->
    <t-dialog
      v-model:visible="showDiscountDialog"
      header="设置折扣"
      :confirm-on-enter="true"
      :on-confirm="submitDiscount"
      :confirm-btn="{ loading: submittingDiscount }"
    >
      <t-form :data="discountForm" layout="vertical">
        <t-form-item label="折扣率">
          <div class="flex items-center gap-3">
            <t-input-number
              v-model="discountForm.discount_display"
              :min="0.1"
              :max="9.9"
              :step="0.5"
              :decimal-places="1"
              theme="normal"
              class="w-40"
            />
            <span class="text-sm text-dp-text-2"
              >折（即支付原价的 {{ ((discountForm.discount_display || 0) * 10).toFixed(0) }}%）</span
            >
          </div>
        </t-form-item>
        <t-form-item label="生效时间">
          <t-date-picker
            v-model="discountForm.effective_from"
            enable-time-picker
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择生效开始时间"
            class="w-full"
          />
        </t-form-item>
        <t-form-item label="失效时间">
          <t-date-picker
            v-model="discountForm.effective_to"
            enable-time-picker
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择失效时间"
            class="w-full"
          />
        </t-form-item>
        <t-form-item label="备注">
          <t-input v-model="discountForm.remark" placeholder="折扣备注" />
        </t-form-item>
      </t-form>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { MessagePlugin } from 'tdesign-vue-next'
import {
  getUsers,
  getTokenGrants,
  createTokenGrant,
  deleteTokenGrant,
  getDiscounts,
  createDiscount,
  deleteDiscount,
  getPlatformConfigs,
  updatePlatformConfig,
} from '@/api/admin'

// ─── Tab state ───

const activeTab = ref('new-user')

// ─── New User Tab: signup bonus config ───

const signupBonusTokens = ref(0)
const savingConfig = ref(false)

async function loadPlatformConfig() {
  try {
    const res = await getPlatformConfigs()
    const configs = res.data.data || []
    const item = configs.find((c: any) => c.config_key === 'signup_bonus_tokens')
    if (item) {
      signupBonusTokens.value = parseInt(item.config_value) || 0
    }
  } catch {
    // ignore
  }
}

async function saveSignupBonus() {
  savingConfig.value = true
  try {
    await updatePlatformConfig({
      config_key: 'signup_bonus_tokens',
      config_value: String(signupBonusTokens.value),
    })
    MessagePlugin.success('设置已保存')
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.message || '保存失败')
  } finally {
    savingConfig.value = false
  }
}

// ─── Existing User Tab: user search ───

const userKeyword = ref('')
const userList = ref<any[]>([])
const selectedUserId = ref<number | null>(null)

async function searchUsers() {
  if (!userKeyword.value.trim()) return
  try {
    const res = await getUsers({ keyword: userKeyword.value, page: 1, page_size: 20 })
    userList.value = res.data.data?.items || []
  } catch {
    userList.value = []
  }
}

function onUserSelected() {
  if (selectedUserId.value) {
    loadGrants()
    loadDiscounts()
  }
}

// ─── Token Grants ───

const grants = ref<any[]>([])
const remainingTokens = ref(0)
const loadingGrants = ref(false)
const showGrantDialog = ref(false)
const submittingGrant = ref(false)
const grantForm = ref({ tokens: 1000000, expires_at: '', remark: '' })

const grantColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'grant_type', title: '类型', width: 100 },
  {
    colKey: 'total_tokens',
    title: '总量',
    cell: (_h: any, { row }: any) => formatTokens(row.total_tokens),
    width: 120,
  },
  { colKey: 'remaining_tokens', title: '剩余', width: 120 },
  { colKey: 'expires_at', title: '过期时间', width: 160 },
  { colKey: 'remark', title: '备注', ellipsis: true },
  { colKey: 'op', title: '操作', width: 80 },
]

async function loadGrants() {
  if (!selectedUserId.value) return
  loadingGrants.value = true
  try {
    const res = await getTokenGrants(selectedUserId.value)
    grants.value = res.data.data?.grants || []
    remainingTokens.value = res.data.data?.remaining_tokens || 0
  } catch {
    grants.value = []
  } finally {
    loadingGrants.value = false
  }
}

async function submitGrant() {
  if (!selectedUserId.value || !grantForm.value.tokens) return
  submittingGrant.value = true
  try {
    await createTokenGrant({
      user_id: selectedUserId.value,
      tokens: grantForm.value.tokens,
      expires_at: grantForm.value.expires_at || undefined,
      remark: grantForm.value.remark || undefined,
    })
    MessagePlugin.success('Token 赠送成功')
    showGrantDialog.value = false
    grantForm.value = { tokens: 1000000, expires_at: '', remark: '' }
    loadGrants()
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.message || '赠送失败')
  } finally {
    submittingGrant.value = false
  }
}

async function deleteGrant(id: number) {
  try {
    await deleteTokenGrant(id)
    MessagePlugin.success('已删除')
    loadGrants()
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.message || '删除失败')
  }
}

// ─── Discounts ───

const discounts = ref<any[]>([])
const loadingDiscounts = ref(false)
const showDiscountDialog = ref(false)
const submittingDiscount = ref(false)
const discountForm = ref({ discount_display: 8.0, effective_from: '', effective_to: '', remark: '' })

const discountColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'discount_rate', title: '折扣', width: 100 },
  { colKey: 'status', title: '状态', width: 80 },
  { colKey: 'effective_from', title: '生效时间', width: 160 },
  { colKey: 'effective_to', title: '失效时间', width: 160 },
  { colKey: 'remark', title: '备注', ellipsis: true },
  { colKey: 'op', title: '操作', width: 80 },
]

async function loadDiscounts() {
  if (!selectedUserId.value) return
  loadingDiscounts.value = true
  try {
    const res = await getDiscounts(selectedUserId.value)
    discounts.value = res.data.data || []
  } catch {
    discounts.value = []
  } finally {
    loadingDiscounts.value = false
  }
}

async function submitDiscount() {
  if (!selectedUserId.value) return
  submittingDiscount.value = true
  try {
    // Convert display value (e.g. 8.0 for "8折") to rate (0.8)
    const rate = discountForm.value.discount_display / 10
    await createDiscount({
      user_id: selectedUserId.value,
      discount_rate: rate,
      effective_from: discountForm.value.effective_from,
      effective_to: discountForm.value.effective_to,
      remark: discountForm.value.remark || undefined,
    })
    MessagePlugin.success('折扣设置成功')
    showDiscountDialog.value = false
    discountForm.value = { discount_display: 8.0, effective_from: '', effective_to: '', remark: '' }
    loadDiscounts()
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.message || '设置失败')
  } finally {
    submittingDiscount.value = false
  }
}

async function deleteDiscountItem(id: number) {
  try {
    await deleteDiscount(id)
    MessagePlugin.success('已删除')
    loadDiscounts()
  } catch (e: any) {
    MessagePlugin.error(e?.response?.data?.message || '删除失败')
  }
}

function isDiscountActive(row: any): boolean {
  const now = new Date()
  return new Date(row.effective_from) <= now && new Date(row.effective_to) > now
}

function isDiscountExpired(row: any): boolean {
  return new Date(row.effective_to) <= new Date()
}

// ─── Helpers ───

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatDate(s: string): string {
  if (!s) return '-'
  return new Date(s).toLocaleString('zh-CN', { hour12: false })
}

// ─── Init ───

onMounted(() => {
  loadPlatformConfig()
})
</script>
