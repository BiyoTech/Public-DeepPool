<template>
  <div class="min-h-screen bg-slate-50">
    <div class="max-w-2xl mx-auto px-6 py-8">
      <h1 class="text-2xl font-bold text-dp-title mb-6">{{ $t('wallet.recharge') }}</h1>

      <!-- Current balance -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm text-dp-muted mb-1">{{ $t('wallet.balance') }}</div>
        <div class="text-3xl font-bold text-dp-title">¥{{ formatMoney(wallet.balance) }}</div>
      </div>

      <!-- Amount selection -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm font-medium text-dp-body mb-4">{{ $t('wallet.selectAmount') || '选择充值金额' }}</div>
        <div class="grid grid-cols-4 gap-3 mb-4">
          <button
            v-for="preset in presetAmounts"
            :key="preset"
            class="py-3 rounded-xl border-2 text-sm font-medium transition-all"
            :class="amountYuan === preset && !customYuan
              ? 'border-dp-blue bg-blue-50 text-dp-blue shadow-sm'
              : 'border-slate-200 text-dp-body hover:border-slate-300 hover:bg-slate-50'"
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
            max="50000"
            step="0.01"
            placeholder="输入金额（0.01 ~ 50000）"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                   transition-all"
            @input="amountYuan = customYuan || 0"
          />
        </div>
      </div>

      <!-- Payment method selection -->
      <div class="bg-white rounded-2xl border border-slate-100 shadow-sm p-6 mb-6">
        <div class="text-sm font-medium text-dp-body mb-4">选择支付方式</div>
        <div class="grid grid-cols-2 gap-4">
          <button
            class="flex items-center justify-center gap-3 py-4 rounded-xl border-2 transition-all"
            :class="selectedChannel === 'wechat'
              ? 'border-green-500 bg-green-50 shadow-sm'
              : 'border-slate-200 hover:border-green-300 hover:bg-green-50/30'"
            @click="selectedChannel = 'wechat'"
          >
            <svg class="w-6 h-6" viewBox="0 0 24 24" fill="#07C160">
              <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05a5.79 5.79 0 0 1-.271-1.737c0-3.684 3.382-6.67 7.556-6.67.376 0 .747.03 1.112.073C17.355 4.788 13.453 2.188 8.691 2.188zm-2.5 4.05c.56 0 1.015.453 1.015 1.012s-.456 1.012-1.015 1.012c-.56 0-1.015-.453-1.015-1.012s.456-1.012 1.015-1.012zm5.012 0c.56 0 1.015.453 1.015 1.012s-.456 1.012-1.015 1.012c-.56 0-1.015-.453-1.015-1.012s.456-1.012 1.015-1.012z"/>
              <path d="M23.414 14.556c0-3.212-3.09-5.815-6.9-5.815-3.81 0-6.9 2.603-6.9 5.815 0 3.212 3.09 5.815 6.9 5.815.748 0 1.47-.1 2.148-.285a.7.7 0 0 1 .577.079l1.457.852a.248.248 0 0 0 .127.041c.122 0 .221-.1.221-.224 0-.054-.022-.108-.037-.162l-.299-1.13a.449.449 0 0 1 .162-.507c1.428-1.065 2.344-2.643 2.344-4.479zm-9.098-1.089c-.425 0-.77-.344-.77-.769s.345-.769.77-.769c.425 0 .77.344.77.769s-.345.769-.77.769zm4.396 0c-.425 0-.77-.344-.77-.769s.345-.769.77-.769c.425 0 .77.344.77.769s-.345.769-.77.769z"/>
            </svg>
            <span class="text-sm font-medium" :class="selectedChannel === 'wechat' ? 'text-green-700' : 'text-dp-body'">微信支付</span>
          </button>
          <button
            class="flex items-center justify-center gap-3 py-4 rounded-xl border-2 transition-all"
            :class="selectedChannel === 'alipay'
              ? 'border-blue-500 bg-blue-50 shadow-sm'
              : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/30'"
            @click="selectedChannel = 'alipay'"
          >
            <svg class="w-6 h-6" viewBox="0 0 24 24" fill="#1677FF">
              <path d="M21.422 14.753c-1.676-.745-4.287-1.908-6.324-2.793.96-1.584 1.755-3.452 2.252-5.467h-4.87V4.864h6.072V3.6H12.48V.882h-2.34s-.06.003-.06.06V3.6H3.817v1.264h6.264v1.629H4.735v1.264h10.4c-.402 1.479-1.002 2.862-1.757 4.065-2.372-.9-5.18-1.698-7.063-1.234-2.726.67-4.188 2.697-4.188 4.66 0 3.084 3.03 4.822 5.965 4.822 2.55 0 4.94-1.198 6.706-3.212.735.443 3.552 1.95 5.114 2.875l1.51-1.98zm-14.16 3.527c-2.12 0-3.684-1.07-3.684-2.894 0-1.82 1.4-3.108 3.282-3.372 1.86-.264 3.954.456 5.672 1.266-1.404 2.99-3.48 5-5.27 5z"/>
            </svg>
            <span class="text-sm font-medium" :class="selectedChannel === 'alipay' ? 'text-blue-700' : 'text-dp-body'">支付宝</span>
          </button>
        </div>
      </div>

      <!-- Confirm button -->
      <button
        :disabled="!canSubmit || loading"
        class="w-full py-3.5 rounded-xl bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
               shadow-sm hover:shadow-md transition-all disabled:opacity-60 disabled:cursor-not-allowed
               active:scale-[0.98]"
        @click="handleRecharge"
      >
        {{ loading ? '创建订单中...' : `确认充值 ¥${amountYuan}` }}
      </button>

      <div v-if="errorMsg" class="mt-4 p-3 rounded-lg bg-red-50 text-red-600 text-sm text-center">
        {{ errorMsg }}
      </div>
    </div>

    <!-- QR Code Payment Modal -->
    <Teleport to="body">
      <div
        v-if="showQRModal"
        class="fixed inset-0 z-50 flex items-center justify-center"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="closeModal" />

        <!-- Modal -->
        <div class="relative bg-white rounded-2xl shadow-2xl w-[400px] max-w-[90vw] p-8 animate-fadeIn">
          <!-- Close button -->
          <button
            class="absolute top-4 right-4 text-slate-400 hover:text-slate-600 transition-colors"
            @click="closeModal"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          <!-- Payment status: pending -->
          <template v-if="orderStatus === 'pending'">
            <div class="text-center mb-6">
              <div class="text-lg font-bold text-dp-title">
                {{ selectedChannel === 'wechat' ? '微信支付' : '支付宝' }}
              </div>
              <div class="text-2xl font-bold mt-2" :class="selectedChannel === 'wechat' ? 'text-green-600' : 'text-blue-600'">
                ¥{{ amountYuan }}
              </div>
            </div>

            <!-- QR Code -->
            <div class="flex justify-center mb-6">
              <div class="p-3 bg-white rounded-xl border border-slate-100 shadow-sm">
                <canvas ref="qrCanvas" />
              </div>
            </div>

            <div class="text-center text-sm text-dp-muted mb-4">
              请使用{{ selectedChannel === 'wechat' ? '微信' : '支付宝' }}扫描二维码完成支付
            </div>

            <!-- Countdown timer -->
            <div class="text-center text-xs text-dp-placeholder">
              剩余支付时间 <span class="font-mono font-medium text-dp-body">{{ countdownDisplay }}</span>
            </div>
          </template>

          <!-- Payment status: success -->
          <template v-if="orderStatus === 'paid'">
            <div class="text-center py-6">
              <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 flex items-center justify-center">
                <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div class="text-lg font-bold text-green-600 mb-2">支付成功</div>
              <div class="text-sm text-dp-muted">¥{{ amountYuan }} 已充值到您的账户</div>
            </div>
          </template>

          <!-- Payment status: expired -->
          <template v-if="orderStatus === 'expired'">
            <div class="text-center py-6">
              <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-orange-100 flex items-center justify-center">
                <svg class="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div class="text-lg font-bold text-orange-600 mb-2">支付超时</div>
              <div class="text-sm text-dp-muted">订单已过期，请重新发起充值</div>
            </div>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { getWallet } from '@/api/wallet'
import { createPaymentOrder, getPaymentOrder } from '@/api/payment'
import QRCode from 'qrcode'

const { t } = useI18n()

// --- State ---
const wallet = ref({ balance: 0 })
const presetAmounts = [10, 50, 100, 500]
const amountYuan = ref(10)
const customYuan = ref<number | null>(null)
const selectedChannel = ref<string>('')
const loading = ref(false)
const errorMsg = ref('')

// QR modal state
const showQRModal = ref(false)
const qrCanvas = ref<HTMLCanvasElement | null>(null)
const currentOrderNo = ref('')
const orderStatus = ref<string>('pending')
const countdownSeconds = ref(0)
let pollTimer: ReturnType<typeof setInterval> | null = null
let countdownTimer: ReturnType<typeof setInterval> | null = null

const canSubmit = computed(() => amountYuan.value > 0 && selectedChannel.value !== '')

const countdownDisplay = computed(() => {
  const m = Math.floor(countdownSeconds.value / 60)
  const s = countdownSeconds.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

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
  if (!canSubmit.value) return
  loading.value = true
  errorMsg.value = ''

  try {
    const res = await createPaymentOrder(amountYuan.value, selectedChannel.value)
    const order = res.data?.data
    if (!order?.qr_url) {
      errorMsg.value = '创建订单失败：未返回支付二维码'
      return
    }

    currentOrderNo.value = order.order_no
    orderStatus.value = 'pending'

    // Calculate countdown from expires_at
    const expiresAt = new Date(order.expires_at).getTime()
    countdownSeconds.value = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000))

    showQRModal.value = true

    // Render QR code after modal is visible
    await nextTick()
    if (qrCanvas.value) {
      await QRCode.toCanvas(qrCanvas.value, order.qr_url, {
        width: 200,
        margin: 1,
        color: { dark: '#1E293B', light: '#FFFFFF' },
      })
    }

    // Start polling order status
    startPolling()
    startCountdown()
  } catch (e: any) {
    errorMsg.value = e?.response?.data?.message || '创建订单失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    if (!currentOrderNo.value) return
    try {
      const res = await getPaymentOrder(currentOrderNo.value)
      const status = res.data?.data?.status
      if (status && status !== 'pending') {
        orderStatus.value = status
        stopPolling()
        stopCountdown()
        if (status === 'paid') {
          await fetchWallet()
        }
      }
    } catch { /* ignore poll errors */ }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startCountdown() {
  stopCountdown()
  countdownTimer = setInterval(() => {
    if (countdownSeconds.value <= 0) {
      stopCountdown()
      if (orderStatus.value === 'pending') {
        orderStatus.value = 'expired'
        stopPolling()
      }
      return
    }
    countdownSeconds.value--
  }, 1000)
}

function stopCountdown() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

function closeModal() {
  showQRModal.value = false
  stopPolling()
  stopCountdown()
  currentOrderNo.value = ''
  orderStatus.value = 'pending'
}

// Cleanup on unmount
onUnmounted(() => {
  stopPolling()
  stopCountdown()
})

onMounted(fetchWallet)
</script>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}
.animate-fadeIn {
  animation: fadeIn 0.2s ease-out;
}
</style>
