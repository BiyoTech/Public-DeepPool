<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-2xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">{{ $t('wallet.withdraw') }}</h1>

      <!-- Available balance -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm text-dp-muted mb-1">可提现余额</div>
        <div class="text-3xl font-bold text-dp-title">¥{{ formatMoney(wallet.balance - wallet.frozen) }}</div>
        <div v-if="wallet.frozen > 0" class="text-xs text-dp-muted mt-1">冻结中: ¥{{ formatMoney(wallet.frozen) }}</div>
      </div>

      <!-- Withdraw form -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6 space-y-4">
        <div>
          <label class="text-sm font-medium text-dp-body mb-1.5 block">提现金额（元）</label>
          <input
            v-model.number="amountYuan"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="输入提现金额"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          />
        </div>

        <!-- Bank card selector -->
        <div>
          <label class="text-sm font-medium text-dp-body mb-1.5 block">提现到</label>
          <select
            v-model="selectedCard"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100"
          >
            <option value="" disabled>选择银行卡</option>
            <option v-for="card in cards" :key="card.id" :value="card.id">
              {{ card.bank_name }} **** {{ card.card_number }}（{{ card.card_holder }}）
            </option>
          </select>
          <router-link to="/wallet/bank-cards" class="text-xs text-dp-blue hover:text-dp-blue-dark mt-1 inline-block">
            + 管理银行卡
          </router-link>
        </div>
      </div>

      <!-- Confirm button -->
      <button
        :disabled="!canSubmit || loading"
        class="w-full py-3 rounded-xl bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium shadow-sm hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed"
        @click="handleWithdraw"
      >
        {{ loading ? '...' : '确认提现' }}
      </button>

      <div
        v-if="msg"
        class="mt-4 p-3 rounded-lg text-sm text-center"
        :class="msgOk ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'"
      >
        {{ msg }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWallet, withdraw } from '@/api/wallet'
import { listBankCards } from '@/api/bankcard'

const { t } = useI18n()

const wallet = ref({ balance: 0, frozen: 0 })
const cards = ref<any[]>([])
const amountYuan = ref<number | null>(null)
const selectedCard = ref<number | ''>('')
const loading = ref(false)
const msg = ref('')
const msgOk = ref(false)

const canSubmit = computed(() => (amountYuan.value || 0) > 0 && selectedCard.value)

/** Format yuan with up to 10 decimal places, trimming trailing zeros */
function formatMoney(yuan: number): string {
  if (!yuan) return '0'
  return yuan.toFixed(10).replace(/0+$/, '').replace(/\.$/, '')
}

async function fetchData() {
  try {
    const [wRes, cRes] = await Promise.all([getWallet(), listBankCards()])
    wallet.value = wRes.data?.data || { balance: 0, frozen: 0 }
    cards.value = cRes.data?.data || []
  } catch {
    /* ignore */
  }
}

async function handleWithdraw() {
  if (!canSubmit.value) return
  loading.value = true
  msg.value = ''
  try {
    // Amount is already in yuan, send directly
    await withdraw(amountYuan.value || 0, selectedCard.value as number)
    msg.value = '提现申请已提交'
    msgOk.value = true
    await fetchData()
  } catch (e: any) {
    msg.value = e?.response?.data?.message || '提现失败'
    msgOk.value = false
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>
