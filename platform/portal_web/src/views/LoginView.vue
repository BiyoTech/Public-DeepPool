<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
    <!-- Background decoration -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-20 left-1/4 w-[400px] h-[400px] bg-blue-100/40 rounded-full blur-3xl" />
      <div class="absolute bottom-20 right-1/4 w-[300px] h-[300px] bg-purple-100/30 rounded-full blur-3xl" />
    </div>

    <!-- Login card -->
    <div class="relative w-full max-w-[420px] bg-white rounded-2xl shadow-lg p-8">
      <!-- Logo -->
      <div class="flex justify-center mb-8">
        <router-link to="/" class="flex items-center gap-2.5">
          <DeepPoolLogo :size="40" />
          <span class="text-2xl font-bold text-dp-title">DeepPool</span>
        </router-link>
      </div>

      <h2 class="text-xl font-bold text-dp-title text-center mb-6">{{ $t('auth.login.title') }}</h2>

      <!-- Login mode tabs -->
      <div class="flex mb-6 bg-slate-100 rounded-lg p-1">
        <button
          class="flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200"
          :class="loginMode === 'password' ? 'bg-white text-dp-blue shadow-sm' : 'text-dp-muted hover:text-dp-body'"
          @click="switchMode('password')"
        >
          {{ $t('auth.login.tab_password') }}
        </button>
        <button
          class="flex-1 py-2 text-sm font-medium rounded-md transition-all duration-200"
          :class="loginMode === 'email' ? 'bg-white text-dp-blue shadow-sm' : 'text-dp-muted hover:text-dp-body'"
          @click="switchMode('email')"
        >
          {{ $t('auth.login.tab_email') }}
        </button>
      </div>

      <!-- Error message -->
      <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-sm">
        {{ errorMsg }}
      </div>

      <!-- Password login form -->
      <form v-if="loginMode === 'password'" @submit.prevent="handlePasswordLogin" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.account') }}</label>
          <input
            v-model="passwordForm.account"
            type="text"
            :placeholder="$t('auth.login.account_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-sm font-medium text-dp-body">{{ $t('auth.login.password') }}</label>
            <router-link to="/forgot-password" class="text-xs text-dp-blue hover:text-dp-blue-dark transition-colors">
              {{ $t('auth.login.forgot_password') }}
            </router-link>
          </div>
          <input
            v-model="passwordForm.password"
            type="password"
            :placeholder="$t('auth.login.password_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium shadow-sm hover:shadow-md hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ loading ? '...' : $t('auth.login.submit') }}
        </button>
      </form>

      <!-- Email code login form -->
      <form v-else @submit.prevent="handleEmailLogin" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.email') }}</label>
          <input
            v-model="emailForm.email"
            type="email"
            :placeholder="$t('auth.login.email_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.code') }}</label>
          <div class="flex gap-3">
            <input
              v-model="emailForm.code"
              type="text"
              maxlength="6"
              :placeholder="$t('auth.login.code_placeholder')"
              class="flex-1 px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
              required
            />
            <button
              type="button"
              :disabled="codeCooldown > 0 || sendingCode"
              class="shrink-0 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
              :class="codeCooldown > 0 ? 'bg-slate-100 text-dp-muted' : 'bg-blue-50 text-dp-blue hover:bg-blue-100'"
              @click="handleSendCode('login')"
            >
              {{
                codeCooldown > 0 ? $t('auth.login.code_sent', { seconds: codeCooldown }) : $t('auth.login.send_code')
              }}
            </button>
          </div>
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium shadow-sm hover:shadow-md hover:from-dp-blue-dark hover:to-dp-blue-deeper transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ loading ? '...' : $t('auth.login.submit') }}
        </button>
      </form>

      <!-- Register link -->
      <p class="mt-6 text-center text-sm text-dp-muted">
        {{ $t('auth.login.no_account') }}
        <router-link to="/register" class="text-dp-blue hover:text-dp-blue-dark font-medium transition-colors">
          {{ $t('auth.login.go_register') }}
        </router-link>
      </p>

      <!-- Language switch -->
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
import { loginApi, loginByEmailApi, sendEmailCodeApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import LangSwitch from '@/components/LangSwitch.vue'
import DeepPoolLogo from '@/components/DeepPoolLogo.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const loginMode = ref<'password' | 'email'>('password')
const loading = ref(false)
const errorMsg = ref('')
const sendingCode = ref(false)
const codeCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

const passwordForm = ref({ account: '', password: '' })
const emailForm = ref({ email: '', code: '' })

function switchMode(mode: 'password' | 'email') {
  loginMode.value = mode
  errorMsg.value = ''
}

function startCooldown() {
  codeCooldown.value = 60
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    codeCooldown.value--
    if (codeCooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

async function handleSendCode(purpose: 'login' | 'reset_password') {
  const email = emailForm.value.email.trim()
  if (!email) return
  sendingCode.value = true
  errorMsg.value = ''
  try {
    await sendEmailCodeApi({ email, purpose })
    startCooldown()
  } catch (err: any) {
    const msg = err?.response?.data?.message || ''
    if (msg.includes('already sent') || msg.includes('please wait')) {
      startCooldown()
      errorMsg.value = t('auth.error.code_rate_limit')
    } else if (msg) {
      errorMsg.value = msg
    } else {
      errorMsg.value = t('auth.error.send_code_failed')
    }
  } finally {
    sendingCode.value = false
  }
}

async function handlePasswordLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginApi(passwordForm.value)
    const data = res.data?.data || res.data
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch {
    errorMsg.value = t('auth.error.login_failed')
  } finally {
    loading.value = false
  }
}

async function handleEmailLogin() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await loginByEmailApi(emailForm.value)
    const data = res.data?.data || res.data
    authStore.setAuth(data.token, data.user)
    router.push('/')
  } catch {
    errorMsg.value = t('auth.error.email_login_failed')
  } finally {
    loading.value = false
  }
}
</script>
