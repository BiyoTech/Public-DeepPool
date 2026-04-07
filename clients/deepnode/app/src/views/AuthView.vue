<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCAL_API_BASE } from '../config'
import { safeFetch } from '../http'

type UserInfo = {
  id: number
  username: string
  phone: string
  email: string
}

type ApiResponse<T> = {
  code: number
  message: string
  data?: T
}

const emit = defineEmits<{
  authenticated: [token: string, user: UserInfo]
}>()

const { t } = useI18n()

const authMode = ref<'login' | 'register'>('login')
const loading = ref(false)
const authError = ref('')

const loginForm = ref({
  account: '',
  password: ''
})

const registerForm = ref({
  username: '',
  password: '',
  confirmPassword: '',
  phone: '',
  email: ''
})

const authTitle = computed(() => (authMode.value === 'login' ? t('auth.loginWelcome') : t('auth.registerWelcome')))
const authSubTitle = computed(() => (authMode.value === 'login' ? t('auth.loginSubtitle') : t('auth.registerSubtitle')))

function switchAuthMode(mode: 'login' | 'register') {
  authMode.value = mode
  authError.value = ''
}

async function requestApi<T>(path: string, method: 'POST' | 'PUT', body: unknown): Promise<ApiResponse<T>> {
  const response = await safeFetch(`${LOCAL_API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })

  let payload: ApiResponse<T>
  try {
    payload = (await response.json()) as ApiResponse<T>
  } catch {
    throw new Error(t('auth.badServiceResponse'))
  }

  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || t('auth.requestFailed'))
  }
  return payload
}

async function submitLogin() {
  if (loading.value) {
    return
  }
  authError.value = ''

  if (!loginForm.value.account.trim() || !loginForm.value.password) {
    authError.value = t('auth.fillAccountPassword')
    return
  }

  loading.value = true
  try {
    const payload = await requestApi<{ token: string; user: UserInfo }>('/api/auth/login', 'POST', {
      account: loginForm.value.account.trim(),
      password: loginForm.value.password
    })
    if (!payload.data?.token || !payload.data?.user) {
      throw new Error(t('auth.missingLoginData'))
    }
    emit('authenticated', payload.data.token, payload.data.user)
  } catch (err) {
    authError.value = err instanceof Error ? err.message : t('auth.loginFailed')
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  if (loading.value) {
    return
  }
  authError.value = ''

  if (!registerForm.value.username.trim() || !registerForm.value.password || !registerForm.value.confirmPassword || !registerForm.value.phone.trim() || !registerForm.value.email.trim()) {
    authError.value = t('auth.fillRegister')
    return
  }

  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    authError.value = t('auth.passwordMismatch')
    return
  }

  loading.value = true
  try {
    await requestApi<UserInfo>('/api/auth/register', 'POST', {
      username: registerForm.value.username.trim(),
      password: registerForm.value.password,
      phone: registerForm.value.phone.trim(),
      email: registerForm.value.email.trim()
    })

    loginForm.value.account = registerForm.value.username.trim()
    loginForm.value.password = registerForm.value.password
    authMode.value = 'login'
    await submitLogin()
  } catch (err) {
    authError.value = err instanceof Error ? err.message : t('auth.registerFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card glass">
      <div class="auth-header">
        <div class="auth-logo">SN</div>
        <div>
          <h1>{{ authTitle }}</h1>
          <p>{{ authSubTitle }}</p>
        </div>
      </div>

      <div class="auth-tabs">
        <button :class="['tab-btn', { active: authMode === 'login' }]" @click="switchAuthMode('login')">{{ t('auth.login') }}</button>
        <button :class="['tab-btn', { active: authMode === 'register' }]" @click="switchAuthMode('register')">{{ t('auth.register') }}</button>
      </div>

      <form v-if="authMode === 'login'" class="auth-form" @submit.prevent="submitLogin">
        <label>
          <span>{{ t('auth.account') }}</span>
          <input v-model="loginForm.account" type="text" :placeholder="t('auth.accountPlaceholder')" />
        </label>
        <label>
          <span>{{ t('auth.password') }}</span>
          <input v-model="loginForm.password" type="password" :placeholder="t('auth.passwordPlaceholder')" />
        </label>
        <p v-if="authError" class="error-tip">{{ authError }}</p>
        <button class="auth-submit" :disabled="loading" type="submit">
          {{ loading ? t('auth.loginLoading') : t('auth.login') }}
        </button>
      </form>

      <form v-else class="auth-form" @submit.prevent="submitRegister">
        <label>
          <span>{{ t('auth.username') }}</span>
          <input v-model="registerForm.username" type="text" :placeholder="t('auth.usernamePlaceholder')" />
        </label>
        <label>
          <span>{{ t('auth.password') }}</span>
          <input v-model="registerForm.password" type="password" :placeholder="t('auth.min8Placeholder')" />
        </label>
        <label>
          <span>{{ t('auth.confirmPassword') }}</span>
          <input v-model="registerForm.confirmPassword" type="password" :placeholder="t('auth.confirmPasswordPlaceholder')" />
        </label>
        <label>
          <span>{{ t('auth.phone') }}</span>
          <input v-model="registerForm.phone" type="text" :placeholder="t('auth.phonePlaceholder')" />
        </label>
        <label>
          <span>{{ t('auth.email') }}</span>
          <input v-model="registerForm.email" type="email" :placeholder="t('auth.emailPlaceholder')" />
        </label>
        <p v-if="authError" class="error-tip">{{ authError }}</p>
        <button class="auth-submit" :disabled="loading" type="submit">
          {{ loading ? t('auth.registerLoading') : t('auth.registerAndLogin') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  padding: 20px;
  display: grid;
  place-items: center;
}

.auth-card {
  width: min(460px, 100%);
  border-radius: 16px;
  padding: 20px;
}

.auth-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.auth-logo {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-weight: 700;
  background: linear-gradient(180deg, #2563ff, #1143d0);
}

.auth-header h1 {
  margin: 0;
  font-size: 24px;
}

.auth-header p {
  margin: 4px 0 0;
  color: #9fb2df;
  font-size: 13px;
}

.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  background: rgba(255, 255, 255, 0.06);
  padding: 4px;
  border-radius: 10px;
  margin-bottom: 14px;
}

.tab-btn {
  border: none;
  border-radius: 8px;
  padding: 8px 10px;
  background: transparent;
  color: #bdd0ff;
  cursor: pointer;
}

.tab-btn.active {
  background: #2a63ff;
  color: #fff;
}

.auth-form {
  display: grid;
  gap: 10px;
}

.auth-form label {
  display: grid;
  gap: 6px;
}

.auth-form span {
  color: #9fb2df;
  font-size: 13px;
}

.auth-form input {
  height: 40px;
  border-radius: 10px;
  border: 1px solid rgba(138, 165, 240, 0.28);
  padding: 0 12px;
  outline: none;
  color: #e8f0ff;
  background: rgba(3, 10, 23, 0.72);
}

.auth-form input:focus {
  border-color: #4a84ff;
}

.error-tip {
  margin: 0;
  color: #ff8b9a;
  font-size: 13px;
}

.auth-submit {
  margin-top: 4px;
  height: 42px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(180deg, #2563ff, #1143d0);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.auth-submit:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.glass {
  background: linear-gradient(135deg, rgba(17, 30, 63, 0.9), rgba(11, 20, 42, 0.88));
  border: 1px solid rgba(100, 130, 255, 0.2);
  box-shadow: 0 10px 30px rgba(1, 8, 23, 0.45);
  backdrop-filter: blur(8px);
}
</style>
