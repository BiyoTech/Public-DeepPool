<template>
  <!-- 顶部导航栏：白色半透明 + 玻璃质感 -->
  <header
    class="fixed top-0 left-0 right-0 z-50 h-16 transition-all duration-300"
    :class="scrolled ? 'bg-white/90 backdrop-blur-lg border-b border-slate-200 shadow-sm' : 'bg-white/80 backdrop-blur-lg'"
  >
    <div class="max-w-7xl mx-auto h-full px-6 flex items-center justify-between">
      <!-- Logo -->
      <router-link to="/" class="flex items-center gap-2.5 group">
        <DeepPoolLogo :size="32" />
        <span class="text-xl font-bold text-dp-title group-hover:text-dp-blue transition-colors">DeepPool</span>
      </router-link>

      <!-- 导航链接 -->
      <nav class="hidden md:flex items-center gap-8">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="relative text-sm font-medium text-dp-muted hover:text-dp-title transition-colors py-1"
          active-class="!text-dp-blue"
        >
          {{ item.label }}
          <span
            v-if="item.beta"
            class="ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold leading-none
                   bg-amber-100 text-amber-700 border border-amber-200 align-top"
          >BETA</span>
          <!-- 活跃指示条 -->
          <span
            v-if="isActive(item.path)"
            class="absolute bottom-0 left-0 right-0 h-0.5 bg-dp-blue rounded-full"
          />
        </router-link>
      </nav>

      <!-- 右侧操作区 -->
      <div class="flex items-center gap-3">
        <a href="https://github.com/BiyoTech/Public-DeepPool" target="_blank" rel="noopener noreferrer"
          class="hidden sm:flex items-center gap-1.5 text-sm font-medium text-dp-muted hover:text-dp-title transition-colors py-1">
          <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.268 2.75 1.026A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.026 2.747-1.026.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.161 22 16.416 22 12c0-5.523-4.477-10-10-10z"/></svg>
          {{ $t('nav.star_github') }}
        </a>
        <LangSwitch />
        <template v-if="!authStore.isLoggedIn">
          <router-link
            to="/login"
            class="text-sm font-medium text-dp-muted hover:text-dp-title transition-colors"
          >
            {{ $t('nav.login') }}
          </router-link>
          <router-link
            to="/register"
            class="text-sm font-medium px-4 py-2 rounded-full bg-gradient-to-r from-dp-blue to-dp-blue-dark
                   text-white hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all duration-200
                   shadow-sm hover:shadow-md"
          >
            {{ $t('nav.register') }}
          </router-link>
        </template>
        <template v-else>
          <div class="relative group">
            <!-- 触发区：用户名 -->
            <button class="flex items-center gap-1.5 text-sm font-medium text-dp-muted hover:text-dp-title transition-colors py-1">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M17.982 18.725A7.488 7.488 0 0012 15.75a7.488 7.488 0 00-5.982 2.975m11.963 0a9 9 0 10-11.963 0m11.963 0A8.966 8.966 0 0112 21a8.966 8.966 0 01-5.982-2.275M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              {{ authStore.user?.username }}
              <svg class="w-3.5 h-3.5 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            <!-- Hover 浮层 -->
            <div class="invisible group-hover:visible opacity-0 group-hover:opacity-100
                        absolute right-0 top-full mt-1 w-80 bg-white rounded-2xl shadow-xl
                        border border-slate-100 p-5 transition-all duration-200 z-50">

              <!-- 余额卡片 -->
              <div class="bg-gradient-to-r from-dp-blue to-dp-blue-dark rounded-xl p-4 text-white mb-4">
                <div class="text-xs opacity-80">{{ $t('wallet.balance') }}</div>
                <div class="text-2xl font-bold mt-1">¥{{ formatMoney(walletData.balance) }}</div>
                <div class="flex gap-4 mt-3 text-xs opacity-80">
                  <span>{{ $t('wallet.total_earned') }}: ¥{{ formatMoney(walletData.total_earned) }}</span>
                  <span>{{ $t('wallet.total_spent') }}: ¥{{ formatMoney(walletData.total_spent) }}</span>
                </div>
              </div>

              <!-- Token 统计 -->
              <div class="grid grid-cols-2 gap-3 mb-4">
                <div class="text-center p-3 bg-slate-50 rounded-lg">
                  <div class="text-lg font-bold text-dp-title">{{ formatTokens(usageData.contributed_tokens) }}</div>
                  <div class="text-[11px] text-dp-muted">{{ $t('wallet.contributed_tokens') }}</div>
                </div>
                <div class="text-center p-3 bg-slate-50 rounded-lg">
                  <div class="text-lg font-bold text-dp-title">{{ formatTokens(usageData.consumed_tokens) }}</div>
                  <div class="text-[11px] text-dp-muted">{{ $t('wallet.consumed_tokens') }}</div>
                </div>
              </div>

              <!-- Recharge & Withdraw buttons -->
              <div class="flex gap-2 mb-3">
                <router-link
                  to="/wallet/recharge"
                  class="flex-1 py-2 text-center rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white text-sm font-medium
                         hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all shadow-sm hover:shadow-md"
                >
                  {{ $t('wallet.recharge') }}
                </router-link>
                <div
                  class="flex-1 py-2 text-center rounded-lg border border-slate-200 text-slate-400 text-sm font-medium cursor-not-allowed"
                  :title="$t('wallet.free_trial_tip')"
                >
                  {{ $t('wallet.withdraw') }}
                </div>
              </div>

              <!-- Footer links -->
              <div class="pt-3 border-t border-slate-100 flex items-center justify-between">
                <router-link to="/data" class="text-xs text-dp-blue hover:text-dp-blue-dark transition-colors">
                  {{ $t('wallet.view_data') }}
                </router-link>
                <div class="flex items-center gap-3">
                  <button class="text-xs text-dp-muted hover:text-dp-title transition-colors" @click="openProfileDialog">
                    {{ $t('nav.settings') }}
                  </button>
                  <button class="text-xs text-dp-muted hover:text-dp-title transition-colors" @click="authStore.logout()">
                    {{ $t('nav.logout') }}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </header>

  <!-- Profile Edit Dialog -->
  <div v-if="showProfileDialog" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md mx-4 max-h-[90vh] overflow-y-auto">
      <div class="flex items-center justify-between mb-5">
        <h3 class="text-lg font-bold text-dp-title">{{ $t('profile.title') }}</h3>
        <button @click="closeProfileDialog" class="p-1 rounded-lg hover:bg-slate-100">
          <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>

      <!-- Success toast inside dialog -->
      <div v-if="profileSuccess" class="mb-4 px-4 py-2.5 rounded-lg bg-green-50 text-green-700 text-sm">{{ profileSuccess }}</div>
      <!-- Error message -->
      <div v-if="profileError" class="mb-4 px-4 py-2.5 rounded-lg bg-red-50 text-red-600 text-sm">{{ profileError }}</div>

      <div class="space-y-5">
        <!-- ── Section: Username ── -->
        <div class="p-4 rounded-xl border border-slate-100 space-y-3">
          <label class="text-xs font-medium text-dp-muted block">{{ $t('profile.username') }}</label>
          <input v-model="pf.username" type="text"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
          <button @click="handleSaveUsername" :disabled="profileSaving || !pf.username.trim() || pf.username === authStore.user?.username"
            class="w-full py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            {{ $t('profile.save') }}
          </button>
        </div>

        <!-- ── Section: Change Email (requires verification code) ── -->
        <div class="p-4 rounded-xl border border-slate-100 space-y-3">
          <label class="text-xs font-medium text-dp-muted block">{{ $t('profile.change_email') }}</label>
          <p class="text-[10px] text-dp-placeholder">{{ $t('profile.current_email') }}: {{ authStore.user?.email }}</p>
          <input v-model="pf.newEmail" type="email" :placeholder="$t('profile.new_email_placeholder')"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
          <div class="flex gap-2">
            <input v-model="pf.emailCode" type="text" maxlength="6" :placeholder="$t('profile.code_placeholder')"
              class="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
            <button type="button" :disabled="emailCooldown > 0 || sendingEmailCode || !pf.newEmail.trim()" @click="handleSendEmailCode"
              class="shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              :class="emailCooldown > 0 ? 'bg-slate-100 text-dp-muted' : 'bg-blue-50 text-dp-blue hover:bg-blue-100'">
              {{ emailCooldown > 0 ? `${emailCooldown}s` : $t('profile.send_code') }}
            </button>
          </div>
          <button @click="handleSaveEmail" :disabled="profileSaving || !pf.newEmail.trim() || !pf.emailCode.trim()"
            class="w-full py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            {{ $t('profile.save') }}
          </button>
        </div>

        <!-- ── Section: Change Password (requires verification code to current email) ── -->
        <div class="p-4 rounded-xl border border-slate-100 space-y-3">
          <label class="text-xs font-medium text-dp-muted block">{{ $t('profile.change_password') }}</label>
          <p class="text-[10px] text-dp-placeholder">{{ $t('profile.password_verify_hint') }}</p>
          <div class="flex gap-2">
            <input v-model="pf.pwdCode" type="text" maxlength="6" :placeholder="$t('profile.code_placeholder')"
              class="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
            <button type="button" :disabled="pwdCooldown > 0 || sendingPwdCode" @click="handleSendPwdCode"
              class="shrink-0 px-3 py-2 rounded-lg text-xs font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              :class="pwdCooldown > 0 ? 'bg-slate-100 text-dp-muted' : 'bg-blue-50 text-dp-blue hover:bg-blue-100'">
              {{ pwdCooldown > 0 ? `${pwdCooldown}s` : $t('profile.send_code') }}
            </button>
          </div>
          <input v-model="pf.newPassword" type="password" :placeholder="$t('profile.new_password_placeholder')"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
          <input v-model="pf.confirmPassword" type="password" :placeholder="$t('profile.confirm_password_placeholder')"
            class="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100" />
          <button @click="handleSavePassword" :disabled="profileSaving || !pf.pwdCode.trim() || !pf.newPassword.trim()"
            class="w-full py-2 rounded-lg bg-dp-blue text-white text-sm font-medium hover:bg-dp-blue-dark transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
            {{ $t('profile.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Main content area -->
  <main class="pt-16 min-h-screen">
    <router-view />
  </main>

  <!-- 底部页脚 -->
  <footer class="bg-dp-footer text-slate-400">
    <div class="max-w-7xl mx-auto px-6 py-12">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-8">
        <!-- Logo & brief -->
        <div>
          <div class="flex items-center gap-2.5 mb-4">
            <DeepPoolLogo :size="32" />
            <span class="text-lg font-bold text-white">DeepPool</span>
          </div>
          <p class="text-sm text-slate-500 leading-relaxed">{{ $t('footer.desc') }}</p>
        </div>

        <!-- 导航链接 -->
        <div>
          <h3 class="text-sm font-semibold text-white mb-4">{{ $t('footer.nav_title') }}</h3>
          <ul class="space-y-2">
            <li v-for="item in navItems" :key="item.path">
              <router-link :to="item.path" class="text-sm text-slate-500 hover:text-white transition-colors">
                {{ item.label }}
              </router-link>
            </li>
          </ul>
        </div>

        <!-- 联系方式 -->
        <div>
          <h3 class="text-sm font-semibold text-white mb-4">{{ $t('footer.contact_title') }}</h3>
          <a href="mailto:contact@deeppool.tech" class="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-white transition-colors">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
            </svg>
            contact@deeppool.tech
          </a>
        </div>
      </div>

      <!-- 版权 -->
      <div class="mt-8 pt-8 border-t border-slate-700/50 text-center text-xs text-slate-600 space-y-1">
        <div>{{ $t('footer.copyright') }}</div>
        <div>深圳市必耀科技有限公司</div>
        <div>
          <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer" class="hover:text-slate-400 transition-colors">
            粤ICP备2026038232号-1
          </a>
        </div>
      </div>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getWallet } from '@/api/wallet'
import { getUsageSummary } from '@/api/usage'
import { updateProfileApi, sendEmailCodeApi, changeEmailApi, resetPasswordApi } from '@/api/auth'
import LangSwitch from '@/components/LangSwitch.vue'
import DeepPoolLogo from '@/components/DeepPoolLogo.vue'

const { t } = useI18n()
const route = useRoute()
const authStore = useAuthStore()

// 滚动状态，控制导航栏样式
const scrolled = ref(false)
function onScroll() {
  scrolled.value = window.scrollY > 10
}
onMounted(() => window.addEventListener('scroll', onScroll))
onUnmounted(() => window.removeEventListener('scroll', onScroll))

// 导航项（响应语言变化）
const navItems = computed(() => [
  { path: '/', label: t('nav.home') },
  { path: '/models', label: t('nav.models') },
  { path: '/service', label: t('nav.service') },
  { path: '/experiment', label: t('nav.experiment') },
  { path: '/data', label: t('nav.data') },
  // 隐藏,未来再考虑
  // { path: '/misszhao', label: t('nav.misszhao'), beta: true },
  { path: '/docs', label: t('nav.docs') },
])

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

// ── 用户浮层数据 ──

const walletData = reactive({ balance: 0, total_earned: 0, total_spent: 0, frozen: 0 })
const usageData = reactive({ contributed_tokens: 0, consumed_tokens: 0 })

/** 获取钱包和用量数据（登录状态下） */
async function fetchUserData() {
  if (!authStore.isLoggedIn) return
  try {
    const [walletRes, usageRes] = await Promise.allSettled([getWallet(), getUsageSummary()])
    if (walletRes.status === 'fulfilled') {
      const w = walletRes.value.data?.data
      if (w) Object.assign(walletData, w)
    }
    if (usageRes.status === 'fulfilled') {
      const u = usageRes.value.data?.data
      if (u) Object.assign(usageData, u)
    }
  } catch {
    // 静默
  }
}

onMounted(fetchUserData)

/** Format yuan value with up to 10 decimal places, trimming trailing zeros */
function formatMoney(yuan: number): string {
  if (!yuan) return '0'
  return yuan.toFixed(10).replace(/0+$/, '').replace(/\.$/, '')
}

/** 格式化 token 数（K/M/B） */
function formatTokens(n: number): string {
  if (!n) return '0'
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

// ── Profile edit dialog ──

const showProfileDialog = ref(false)
const profileSaving = ref(false)
const profileError = ref('')
const profileSuccess = ref('')

const pf = reactive({
  username: '',
  // Email change
  newEmail: '',
  emailCode: '',
  // Password change
  pwdCode: '',
  newPassword: '',
  confirmPassword: '',
})

// Cooldown timers for verification codes
const emailCooldown = ref(0)
const pwdCooldown = ref(0)
const sendingEmailCode = ref(false)
const sendingPwdCode = ref(false)
const emailCdTimer: { value: ReturnType<typeof setInterval> | null } = { value: null }
const pwdCdTimer: { value: ReturnType<typeof setInterval> | null } = { value: null }

function startCooldown(ref: typeof emailCooldown, timerRef: { value: ReturnType<typeof setInterval> | null }) {
  ref.value = 60
  if (timerRef.value) clearInterval(timerRef.value)
  timerRef.value = setInterval(() => {
    ref.value--
    if (ref.value <= 0 && timerRef.value) {
      clearInterval(timerRef.value)
      timerRef.value = null
    }
  }, 1000)
}

function openProfileDialog() {
  const u = authStore.user
  pf.username = u?.username || ''
  pf.newEmail = ''
  pf.emailCode = ''
  pf.pwdCode = ''
  pf.newPassword = ''
  pf.confirmPassword = ''
  profileError.value = ''
  profileSuccess.value = ''
  showProfileDialog.value = true
}

function closeProfileDialog() {
  showProfileDialog.value = false
  profileError.value = ''
  profileSuccess.value = ''
}

function clearMessages() {
  profileError.value = ''
  profileSuccess.value = ''
}

/** Save username via PUT /users/profile. */
async function handleSaveUsername() {
  clearMessages()
  if (!pf.username.trim() || pf.username === authStore.user?.username) return
  profileSaving.value = true
  try {
    const res = await updateProfileApi({ username: pf.username.trim() })
    const updated = res.data?.data
    if (updated) authStore.updateUser({ username: updated.username })
    profileSuccess.value = t('profile.username_updated')
  } catch (err: any) {
    profileError.value = err?.response?.data?.message || err?.message || 'Update failed'
  } finally {
    profileSaving.value = false
  }
}

/** Send verification code to the new email address. */
async function handleSendEmailCode() {
  clearMessages()
  const email = pf.newEmail.trim()
  if (!email) return
  sendingEmailCode.value = true
  try {
    await sendEmailCodeApi({ email, purpose: 'change_email' })
    startCooldown(emailCooldown, emailCdTimer)
  } catch (err: any) {
    const msg = err?.response?.data?.message || ''
    if (msg.includes('already sent') || msg.includes('please wait')) {
      startCooldown(emailCooldown, emailCdTimer)
    }
    profileError.value = msg || t('profile.send_code_failed')
  } finally {
    sendingEmailCode.value = false
  }
}

/** Save new email via POST /users/change-email with verification code. */
async function handleSaveEmail() {
  clearMessages()
  if (!pf.newEmail.trim() || !pf.emailCode.trim()) return
  profileSaving.value = true
  try {
    await changeEmailApi({ new_email: pf.newEmail.trim(), code: pf.emailCode.trim() })
    authStore.updateUser({ email: pf.newEmail.trim() })
    pf.newEmail = ''
    pf.emailCode = ''
    profileSuccess.value = t('profile.email_updated')
  } catch (err: any) {
    profileError.value = err?.response?.data?.message || err?.message || 'Update failed'
  } finally {
    profileSaving.value = false
  }
}

/** Send verification code to current email for password reset. */
async function handleSendPwdCode() {
  clearMessages()
  const email = authStore.user?.email
  if (!email) return
  sendingPwdCode.value = true
  try {
    await sendEmailCodeApi({ email, purpose: 'reset_password' })
    startCooldown(pwdCooldown, pwdCdTimer)
  } catch (err: any) {
    const msg = err?.response?.data?.message || ''
    if (msg.includes('already sent') || msg.includes('please wait')) {
      startCooldown(pwdCooldown, pwdCdTimer)
    }
    profileError.value = msg || t('profile.send_code_failed')
  } finally {
    sendingPwdCode.value = false
  }
}

/** Save new password via POST /users/reset-password with email verification code. */
async function handleSavePassword() {
  clearMessages()
  if (!pf.pwdCode.trim() || !pf.newPassword.trim()) return
  if (pf.newPassword.length < 8) {
    profileError.value = t('profile.password_min_length')
    return
  }
  if (pf.newPassword !== pf.confirmPassword) {
    profileError.value = t('profile.password_mismatch')
    return
  }
  const email = authStore.user?.email
  if (!email) return
  profileSaving.value = true
  try {
    await resetPasswordApi({ email, code: pf.pwdCode.trim(), new_password: pf.newPassword })
    pf.pwdCode = ''
    pf.newPassword = ''
    pf.confirmPassword = ''
    profileSuccess.value = t('profile.password_updated')
  } catch (err: any) {
    profileError.value = err?.response?.data?.message || err?.message || 'Update failed'
  } finally {
    profileSaving.value = false
  }
}
</script>
