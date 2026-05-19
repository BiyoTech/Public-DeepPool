<template>
  <div class="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-12">
    <!-- Background decoration -->
    <div class="absolute inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-20 left-1/4 w-[400px] h-[400px] bg-blue-100/40 rounded-full blur-3xl" />
      <div class="absolute bottom-20 right-1/4 w-[300px] h-[300px] bg-purple-100/30 rounded-full blur-3xl" />
    </div>

    <!-- Card -->
    <div class="relative w-full max-w-[420px] bg-white rounded-2xl shadow-lg p-8">
      <!-- Logo -->
      <div class="flex justify-center mb-8">
        <router-link to="/" class="flex items-center gap-2.5">
          <DeepPoolLogo :size="40" />
          <span class="text-2xl font-bold text-dp-title">DeepPool</span>
        </router-link>
      </div>

      <h2 class="text-xl font-bold text-dp-title text-center mb-6">{{ $t('auth.forgot.title') }}</h2>

      <!-- Step indicator -->
      <div class="flex items-center justify-center gap-3 mb-6">
        <div class="flex items-center gap-2">
          <span
            class="w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center"
            :class="step >= 1 ? 'bg-dp-blue text-white' : 'bg-slate-200 text-dp-muted'"
            >1</span
          >
          <span class="text-xs" :class="step >= 1 ? 'text-dp-blue font-medium' : 'text-dp-muted'">
            {{ $t('auth.forgot.step1_title') }}
          </span>
        </div>
        <div class="w-8 h-px bg-slate-200" />
        <div class="flex items-center gap-2">
          <span
            class="w-7 h-7 rounded-full text-xs font-bold flex items-center justify-center"
            :class="step >= 2 ? 'bg-dp-blue text-white' : 'bg-slate-200 text-dp-muted'"
            >2</span
          >
          <span class="text-xs" :class="step >= 2 ? 'text-dp-blue font-medium' : 'text-dp-muted'">
            {{ $t('auth.forgot.step2_title') }}
          </span>
        </div>
      </div>

      <!-- Error message -->
      <div v-if="errorMsg" class="mb-4 px-4 py-3 rounded-lg bg-red-50 text-red-600 text-sm">
        {{ errorMsg }}
      </div>

      <!-- Success message -->
      <div v-if="successMsg" class="mb-4 px-4 py-3 rounded-lg bg-green-50 text-green-700 text-sm">
        {{ successMsg }}
      </div>

      <!-- Step 1: Verify email -->
      <form v-if="step === 1" @submit.prevent="handleVerifyEmail" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.email') }}</label>
          <input
            v-model="form.email"
            type="email"
            :placeholder="$t('auth.forgot.email_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.login.code') }}</label>
          <div class="flex gap-3">
            <input
              v-model="form.code"
              type="text"
              maxlength="6"
              :placeholder="$t('auth.forgot.code_placeholder')"
              class="flex-1 px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
              required
            />
            <button
              type="button"
              :disabled="codeCooldown > 0 || sendingCode"
              class="shrink-0 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
              :class="codeCooldown > 0 ? 'bg-slate-100 text-dp-muted' : 'bg-blue-50 text-dp-blue hover:bg-blue-100'"
              @click="handleSendCode"
            >
              {{
                codeCooldown > 0 ? $t('auth.forgot.code_sent', { seconds: codeCooldown }) : $t('auth.forgot.send_code')
              }}
            </button>
          </div>
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ loading ? '...' : $t('auth.forgot.next_step') }}
        </button>
      </form>

      <!-- Step 2: Set new password -->
      <form v-if="step === 2" @submit.prevent="handleResetPassword" class="space-y-5">
        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.forgot.new_password') }}</label>
          <input
            v-model="form.newPassword"
            type="password"
            :placeholder="$t('auth.forgot.new_password_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-dp-body mb-1.5">{{ $t('auth.forgot.confirm_password') }}</label>
          <input
            v-model="form.confirmPassword"
            type="password"
            :placeholder="$t('auth.forgot.confirm_password_placeholder')"
            class="w-full px-4 py-2.5 rounded-lg border border-slate-200 text-sm text-dp-body placeholder:text-dp-placeholder focus:outline-none focus:border-dp-blue focus:ring-2 focus:ring-blue-100 transition-all duration-200"
            required
          />
        </div>

        <button
          type="submit"
          :disabled="loading"
          class="w-full py-3 rounded-lg bg-gradient-to-r from-dp-blue to-dp-blue-dark text-white font-medium shadow-sm hover:shadow-md transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {{ loading ? '...' : $t('auth.forgot.reset_submit') }}
        </button>
      </form>

      <!-- Back to login -->
      <p class="mt-6 text-center">
        <router-link to="/login" class="text-sm text-dp-blue hover:text-dp-blue-dark font-medium transition-colors">
          {{ $t('auth.forgot.back_to_login') }}
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
import { sendEmailCodeApi, resetPasswordApi } from '@/api/auth'
import LangSwitch from '@/components/LangSwitch.vue'
import DeepPoolLogo from '@/components/DeepPoolLogo.vue'

const { t } = useI18n()
const router = useRouter()

const step = ref(1)
const loading = ref(false)
const errorMsg = ref('')
const successMsg = ref('')
const sendingCode = ref(false)
const codeCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

const form = ref({
  email: '',
  code: '',
  newPassword: '',
  confirmPassword: '',
})

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
    await sendEmailCodeApi({ email, purpose: 'reset_password' })
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

// Step 1 → Step 2: just validate email and code are filled, actual verification happens on reset.
function handleVerifyEmail() {
  errorMsg.value = ''
  if (!form.value.email.trim() || !form.value.code.trim()) return
  step.value = 2
}

async function handleResetPassword() {
  errorMsg.value = ''
  successMsg.value = ''

  if (form.value.newPassword !== form.value.confirmPassword) {
    errorMsg.value = t('auth.error.password_mismatch')
    return
  }
  if (form.value.newPassword.length < 8) {
    errorMsg.value = t('auth.error.password_mismatch')
    return
  }

  loading.value = true
  try {
    await resetPasswordApi({
      email: form.value.email.trim(),
      code: form.value.code.trim(),
      new_password: form.value.newPassword,
    })
    successMsg.value = t('auth.forgot.reset_success')
    setTimeout(() => router.push('/login'), 3000)
  } catch {
    errorMsg.value = t('auth.error.reset_failed')
    // If code expired, go back to step 1 for retry.
    step.value = 1
  } finally {
    loading.value = false
  }
}
</script>
