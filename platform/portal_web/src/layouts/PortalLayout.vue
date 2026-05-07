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

              <!-- 底部链接 -->
              <div class="pt-3 border-t border-slate-100 flex items-center justify-between">
                <router-link to="/data" class="text-xs text-dp-blue hover:text-dp-blue-dark transition-colors">
                  {{ $t('wallet.view_data') }}
                </router-link>
                <button
                  class="text-xs text-dp-muted hover:text-dp-title transition-colors"
                  @click="authStore.logout()"
                >
                  {{ $t('nav.logout') }}
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </header>

  <!-- 主内容区域（导航栏高度偏移） -->
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
  { path: '/service', label: t('nav.service') },
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
</script>
