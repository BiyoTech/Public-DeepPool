<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
    <!-- Background decoration -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-20 left-1/4 w-[400px] h-[400px] bg-blue-100/40 rounded-full blur-3xl" />
      <div class="absolute bottom-20 right-1/4 w-[300px] h-[300px] bg-purple-100/30 rounded-full blur-3xl" />
    </div>

    <!-- Register card -->
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

      <!-- Success message -->
      <div v-if="successMsg" class="mb-4 px-4 py-3 rounded-lg bg-green-50 text-green-600 text-sm text-center">
        {{ successMsg }}
      </div>

      <!-- Error message -->
      <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-sm">
        {{ errorMsg }}
      </div>

      <form v-show="!successMsg" @submit.prevent="handleRegister" class="space-y-4">
        <!-- Username -->
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

        <!-- Password row -->
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

        <!-- Phone (optional) -->
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.phone') }}</label>
          <input
            v-model="form.phone"
            type="text"
            :placeholder="$t('auth.register.phone_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                   placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                   transition-all duration-200"
          />
        </div>

        <!-- Email -->
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

        <!-- Email verification code -->
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.register.email_code') }}</label>
          <div class="flex gap-3">
            <input
              v-model="form.emailCode"
              type="text"
              maxlength="6"
              :placeholder="$t('auth.register.email_code_placeholder')"
              class="flex-1 px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body
                     placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100
                     transition-all duration-200"
              required
            />
            <button
              type="button"
              :disabled="codeCooldown > 0 || sendingCode || !form.email.trim()"
              class="shrink-0 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200
                     disabled:opacity-60 disabled:cursor-not-allowed"
              :class="codeCooldown > 0
                ? 'bg-slate-100 text-dp-muted'
                : 'bg-blue-50 text-dp-blue hover:bg-blue-100'"
              @click="handleSendCode"
            >
              {{ codeCooldown > 0 ? $t('auth.register.code_sent', { seconds: codeCooldown }) : $t('auth.register.send_code') }}
            </button>
          </div>
        </div>

        <!-- Register button -->
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

      <!-- Go to login -->
      <p class="mt-6 text-center text-sm text-dp-muted">
        {{ $t('auth.register.has_account') }}
        <router-link to="/login" class="text-dp-blue hover:text-dp-blue-dark font-medium transition-colors">
          {{ $t('auth.register.go_login') }}
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
import { registerApi, sendEmailCodeApi } from '@/api/auth'
import LangSwitch from '@/components/LangSwitch.vue'

const { t } = useI18n()
const router = useRouter()

const form = ref({
  username: '',
  password: '',
  confirmPassword: '',
  phone: '',
  email: '',
  emailCode: '',
})
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const sendingCode = ref(false)
const codeCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

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

async function handleSendCode() {
  const email = form.value.email.trim()
  if (!email) return
  sendingCode.value = true
  errorMsg.value = ''
  try {
    await sendEmailCodeApi({ email, purpose: 'register' })
    startCooldown()
  } catch (err: any) {
    const msg = err?.response?.data?.message || ''
    if (msg.includes('already sent') || msg.includes('please wait')) {
      // Server says code was already sent recently — start cooldown to prevent re-clicks.
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
      email_code: form.value.emailCode,
    })
    loading.value = false
    successMsg.value = t('auth.register.register_success')
    setTimeout(() => router.push('/login'), 3000)
    return
  } catch (err: any) {
    const status = err?.response?.status
    const msg = err?.response?.data?.message || ''
    if (status === 409 || msg.includes('already exists')) {
      errorMsg.value = t('auth.error.register_duplicate')
    } else if (msg) {
      errorMsg.value = msg
    } else {
      errorMsg.value = t('auth.error.register_failed')
    }
  } finally {
    loading.value = false
  }
}
</script>
