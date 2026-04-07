<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-2xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">{{ $t('wallet.recharge') }}</h1>

      <!-- Current balance -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm text-dp-muted mb-1">{{ $t('wallet.balance') }}</div>
        <div class="text-3xl font-bold text-dp-title">¥{{ formatMoney(wallet.balance) }}</div>
      </div>

      <!-- Preset amounts (in yuan) -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm font-medium text-dp-body mb-4">选择充值金额</div>
        <div class="grid grid-cols-4 gap-3 mb-4">
          <button
            v-for="preset in [10, 50, 100, 500]"
            :key="preset"
            class="py-3 rounded-xl border-2 text-sm font-medium transition-all"
            :class="amountYuan === preset
              ? 'border-dp-blue bg-blue-50 text-dp-blue'
              : 'border-slate-200 text-dp-body hover:border-slate-300'"
            @click="amountYuan = preset; customYuan = null"
          >
            ¥{{ preset }}
          </button>
        </div>
        <div>
          <label class="text-xs text-dp-muted mb-1 block">自定义金额（元）</label>
          <input
            v-model.number="customYuan"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="输入金额"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
            @input="amountYuan = customYuan || 0"
          />
        </div>
      </div>

      <!-- Confirm button -->
      <button
        :disabled="amountYuan <= 0 || loading"
        class="w-full py-3 rounded-xl bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
               shadow-sm hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        @click="handleRecharge"
      >
        {{ loading ? '...' : `确认充值 ¥${amountYuan}` }}
      </button>

      <div v-if="successMsg" class="mt-4 p-3 rounded-lg bg-green-50 text-green-700 text-sm text-center">
        {{ successMsg }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWallet, recharge } from '@/api/wallet'

const { t } = useI18n()

const wallet = ref({ balance: 0 })
const amountYuan = ref(10)
const customYuan = ref<number | null>(null)
const loading = ref(false)
const successMsg = ref('')

/** Format yuan with up to 10 decimal places, trimming trailing zeros */
function formatMoney(yuan: number): string {
  if (!yuan) return '0'
  return yuan.toFixed(10).replace(/0+$/, '').replace(/\.$/, '')
}

async function fetchWallet() {
  try {
    const res = await getWallet()
    wallet.value = res.data?.data || { balance: 0 }
  } catch { /* ignore */ }
}

async function handleRecharge() {
  if (amountYuan.value <= 0) return
  loading.value = true
  successMsg.value = ''
  try {
    await recharge(amountYuan.value)
    successMsg.value = `充值成功 ¥${amountYuan.value}`
    await fetchWallet()
  } catch {
    successMsg.value = '充值失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(fetchWallet)
</script>
