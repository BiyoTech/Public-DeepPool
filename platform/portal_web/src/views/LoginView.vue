<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
    <!-- 背景装饰 -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-20 left-1/4 w-[400px] h-[400px] bg-blue-100/40 rounded-full blur-3xl" />
      <div class="absolute bottom-20 right-1/4 w-[300px] h-[300px] bg-purple-100/30 rounded-full blur-3xl" />
    </div>

    <!-- 登录卡片 -->
    <div class="relative w-full max-w-[420px] bg-white rounded-2xl shadow-lg p-8">
      <!-- Logo -->
      <div class="flex justify-center mb-8">
        <router-link to="/" class="flex items-center gap-2.5">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-dp-blue to-dp-blue-dark flex items-center justify-center">
            <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <span class="text-2xl font-bold text-dp-title">DeepPool</span>
        </router-link>
      </div>

      <h2 class="text-xl font-bold text-dp-title text-center mb-6">{{ $t('auth.login.title') }}</h2>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-sm">
        {{ errorMsg }}
      </div>

      <form @submit.prevent="handleLogin" class="space-y-5">
        <!-- 账号 -->
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.account') }}</label>
          <input
            v-model="form.account"
            type="text"
            :placeholder="$t('auth.login.account_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                   transition-all duration-200"
            required
          />
        </div>

        <!-- 密码 -->
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.password') }}</label>
          <input
            v-model="form.password"
            type="password"
            :placeholder="$t('auth.login.password_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                   transition-all duration-200"
            required
          />
        </div>

        <!-- 登录按钮 -->
        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
                 shadow-sm hover:shadow-md hover:from-dp-blue-dark hover:to-dp-blue-deeper
                 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ loading ? '...' : $t('auth.login.submit') }}
        </button>
      </form>

      <!-- 跳转注册 -->
      <p class="mt-6 text-center text-sm text-dp-muted">
        {{ $t('auth.login.no_account') }}
        <router-link to="/register" class="text-dp-blue hover:text-dp-blue-dark font-medium transition-colors">
          {{ $t('auth.login.go_register') }}
        </router-link>
      </p>

      <!-- 语言切换 -->
      <div class="mt-4 flex justify-center">
        <LangSwitch />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { loginApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import LangSwitch from '@/components/LangSwitch.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const form = ref({ account: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginApi(form.value)
    const data = res.data?.data || res.data
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch {
    errorMsg.value = t('auth.error.login_failed')
  } finally {
    loading.value = false
  }
}
</script>
