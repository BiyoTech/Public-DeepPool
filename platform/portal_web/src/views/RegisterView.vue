<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
    <!-- 背景装饰 -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-20 left-1/4 w-[400px] h-[400px] bg-blue-100/40 rounded-full blur-3xl" />
      <div class="absolute bottom-20 right-1/4 w-[300px] h-[300px] bg-purple-100/30 rounded-full blur-3xl" />
    </div>

    <!-- 注册卡片 -->
    <div class="relative w-full max-w-[480px] bg-white rounded-2xl shadow-lg p-8">
      <!-- Logo -->
      <div class="flex justify-center mb-6">
        <router-link to="/" class="flex items-center gap-2.5">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-dp-blue to-dp-blue-dark flex items-center justify-center">
            <svg class="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
          </div>
          <span class="text-2xl font-bold text-dp-title">DeepPool</span>
        </router-link>
      </div>

      <h2 class="text-xl font-bold text-dp-title text-center mb-6">{{ $t('auth.register.title') }}</h2>

      <!-- 错误提示 -->
      <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-sm">
        {{ errorMsg }}
      </div>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <!-- 用户名 -->
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.username') }}</label>
          <input
            v-model="form.username"
            type="text"
            :placeholder="$t('auth.register.username_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                   transition-all duration-200"
            required
          />
        </div>

        <!-- 密码行 -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.password') }}</label>
            <input
              v-model="form.password"
              type="password"
              :placeholder="$t('auth.register.password_placeholder')"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                     transition-all duration-200"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.confirm_password') }}</label>
            <input
              v-model="form.confirmPassword"
              type="password"
              :placeholder="$t('auth.register.confirm_password_placeholder')"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                     transition-all duration-200"
              required
            />
          </div>
        </div>

        <!-- 手机号和邮箱 -->
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.phone') }}</label>
            <input
              v-model="form.phone"
              type="text"
              :placeholder="$t('auth.register.phone_placeholder')"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                     transition-all duration-200"
              required
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.email') }}</label>
            <input
              v-model="form.email"
              type="email"
              :placeholder="$t('auth.register.email_placeholder')"
              class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                     transition-all duration-200"
              required
            />
          </div>
        </div>

        <!-- 注册按钮 -->
        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium
                 shadow-sm hover:shadow-md hover:from-dp-blue-dark hover:to-dp-blue-deeper
                 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed mt-2"
        >
          {{ loading ? '...' : $t('auth.register.submit') }}
        </button>
      </form>

      <!-- 跳转登录 -->
      <p class="mt-6 text-center text-sm text-dp-muted">
        {{ $t('auth.register.has_account') }}
        <router-link to="/login" class="text-dp-blue hover:text-dp-blue-dark font-medium transition-colors">
          {{ $t('auth.register.go_login') }}
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
import { registerApi } from '@/api/auth'
import LangSwitch from '@/components/LangSwitch.vue'

const { t } = useI18n()
const router = useRouter()

const form = ref({
  username: '',
  password: '',
  confirmPassword: '',
  phone: '',
  email: '',
})
const loading = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  if (form.value.password !== form.value.confirmPassword) {
    errorMsg.value = t('auth.error.password_mismatch')
    return
  }

  loading.value = true
  errorMsg.value = ''
  try {
    await registerApi({
      username: form.value.username,
      password: form.value.password,
      phone: form.value.phone,
      email: form.value.email,
    })
    router.push('/login')
  } catch {
    errorMsg.value = t('auth.error.register_failed')
  } finally {
    loading.value = false
  }
}
</script>
