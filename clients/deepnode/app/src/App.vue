<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AuthView from './views/AuthView.vue'
import DeviceInitView from './views/DeviceInitView.vue'
import DeviceDetailView from './views/DeviceDetailView.vue'
import { LOCALE_KEY, SUPPORTED_LOCALES } from './i18n'
import { LOCAL_API_BASE } from './config'
import { safeFetch, isTauri, setOnUnauthorized } from './http'

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

type SupportedLocale = (typeof SUPPORTED_LOCALES)[keyof typeof SUPPORTED_LOCALES]

/** 设备初始化原因，决定 DeviceInitView 展示的提示文案 */
type DeviceInitReason =
  | ''
  | 'device_not_registered'
  | 'model_service_not_ready'
  | 'localserver_unavailable'
  | 'network_error'

const TOKEN_KEY = 'deepnode_token'
const USER_KEY = 'deepnode_user'

const token = ref(localStorage.getItem(TOKEN_KEY) ?? '')
const currentUser = ref<UserInfo | null>(readUserFromStorage())

const isAuthed = computed(() => Boolean(token.value))
const { t, locale } = useI18n()
const currentLocale = computed(() => locale.value as SupportedLocale)

// ---- 设备指纹 & 设备状态 ----
const deviceFingerprint = ref('')
const deviceCheckLoading = ref(false)
const deviceExists = ref(false)
const deviceInitReason = ref<DeviceInitReason>('')
const deviceCheckDone = ref(false)
/** 加载页提示文字，可动态变化反映当前阶段 */
const loadingMessage = ref('')

function readUserFromStorage(): UserInfo | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as UserInfo } catch { return null }
}

function persistAuth(nextToken: string, user: UserInfo) {
  token.value = nextToken
  currentUser.value = user
  localStorage.setItem(TOKEN_KEY, nextToken)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

function clearAuth() {
  token.value = ''
  currentUser.value = null
  deviceFingerprint.value = ''
  deviceExists.value = false
  deviceInitReason.value = ''
  deviceCheckDone.value = false
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  // 停止 localserver sidecar（仅 Tauri 模式下通知 Rust 侧 kill 进程）
  if (isTauri) {
    import('@tauri-apps/api/core').then(({ invoke }) => {
      invoke('stop_localserver').catch(() => {})
    }).catch(() => {})
  }
}

// Register global 401 handler: any API returning 401 triggers logout → login page.
setOnUnauthorized(() => clearAuth())

function switchLocale(next: SupportedLocale) {
  locale.value = next
  localStorage.setItem(LOCALE_KEY, next)
}

// ── localserver 就绪等待 ──────────────────────────────────
// 首次检测：Production 模式下监听 Rust 侧 emit 事件（Rust 侧 120s 超时轮询 TCP 端口）；
// 重新检测：直接 HTTP 轮询 /health（localserver 可能已启动，无需等 Rust 事件）。
// Dev 模式始终直接轮询 /health。

/** 标记是否为首次检测，首次走 Rust 事件监听，后续走 HTTP 轮询 */
let isFirstCheck = true

/**
 * 等待 localserver 就绪。
 * - 首次 Tauri production 检测: 监听 Rust 侧 "localserver-ready/failed" 事件
 * - standalone 浏览器模式 / dev 模式 / 重新检测: 直接轮询 /health 端点（30s 超时）
 * @returns true=就绪, false=超时或失败
 */
async function waitForLocalServer(): Promise<boolean> {
  // 非 Tauri 环境（standalone 浏览器）、dev 模式、或重新检测：直接 HTTP 轮询
  if (!isTauri || import.meta.env.DEV || !isFirstCheck) {
    return pollLocalServerHealth()
  }

  // 首次 production 检测：监听 Rust 侧 TCP 轮询结果
  isFirstCheck = false
  const { listen } = await import('@tauri-apps/api/event')
  return new Promise<boolean>((resolve) => {
    let settled = false
    const cleanup: Array<() => void> = []

    const settle = (ok: boolean) => {
      if (settled) return
      settled = true
      cleanup.forEach((fn) => fn())
      resolve(ok)
    }

    listen('localserver-ready', () => settle(true)).then((unlisten) => {
      cleanup.push(unlisten)
      if (settled) unlisten()
    })
    listen('localserver-failed', () => settle(false)).then((unlisten) => {
      cleanup.push(unlisten)
      if (settled) unlisten()
    })

    // 兜底超时 125s（略大于 Rust 侧 120s），防止事件丢失导致永远挂起
    setTimeout(() => settle(false), 125_000)
  })
}

/**
 * 轮询 localserver /health 端点。
 * dev 模式或重新检测时使用，最多等 30s。
 */
async function pollLocalServerHealth(): Promise<boolean> {
  const maxWait = 30_000
  const interval = 500
  const start = Date.now()
  while (Date.now() - start < maxWait) {
    try {
      const resp = await safeFetch(`${LOCAL_API_BASE}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      })
      if (resp.ok) return true
    } catch { /* 连接失败，继续重试 */ }
    await new Promise((r) => setTimeout(r, interval))
  }
  return false
}

/**
 * 设备状态校验主流程（线性三步）：
 * 1. 等待 localserver 就绪
 * 2. 查询平台设备是否已注册
 * 3. 设备已注册时检查本地推理服务是否可用
 */
async function checkDeviceStatus() {
  if (!token.value) return
  deviceCheckLoading.value = true
  deviceCheckDone.value = false
  deviceInitReason.value = ''

  try {
    // 步骤1：等待 localserver 就绪
    loadingMessage.value = t('deviceInit.localserverStarting')
    const localReady = await waitForLocalServer()
    if (!localReady) {
      console.warn('[DeepNode] localserver not ready after timeout')
      deviceInitReason.value = 'localserver_unavailable'
      return
    }

    // 步骤2：从 localserver 获取设备指纹（simei 统一由 Python 生成）
    loadingMessage.value = t('common.loggedInUser')
    let fingerprint = ''
    try {
      const fpResp = await safeFetch(`${LOCAL_API_BASE}/api/device/fingerprint`, {
        method: 'GET',
        signal: AbortSignal.timeout(10_000)
      })
      if (fpResp.ok) {
        const fpData = (await fpResp.json()) as ApiResponse<{ simei?: string }>
        fingerprint = fpData.data?.simei?.trim() ?? ''
      }
    } catch (err) {
      console.warn('[DeepNode] failed to get fingerprint from localserver:', err)
    }
    if (!fingerprint) {
      deviceInitReason.value = 'localserver_unavailable'
      return
    }
    deviceFingerprint.value = fingerprint

    let platformResp: Response
    try {
      platformResp = await safeFetch(`${LOCAL_API_BASE}/api/device/check/${fingerprint}`, {
        method: 'GET',
        headers: { Authorization: `Bearer ${token.value}` },
        signal: AbortSignal.timeout(10_000)
      })
    } catch (err) {
      // 平台网络不可达（DNS 失败、连接拒绝等）
      console.warn('[DeepNode] device check request failed:', err)
      deviceInitReason.value = 'network_error'
      return
    }

    if (platformResp.status === 401) {
      // Token expired — safeFetch already triggered clearAuth() via onUnauthorized.
      return
    }

    if (!platformResp.ok) {
      // 404 或其他非 200：设备未注册
      deviceExists.value = false
      deviceInitReason.value = 'device_not_registered'
      console.warn('[DeepNode] device not found on platform, simei=%s, status=%d', fingerprint, platformResp.status)
      return
    }

    // 解析平台响应
    let platformExists = false
    try {
      const payload = (await platformResp.json()) as ApiResponse<unknown>
      platformExists = payload.code === 0 && !!payload.data
    } catch { /* json parse fail */ }

    if (!platformExists) {
      deviceExists.value = false
      deviceInitReason.value = 'device_not_registered'
      return
    }

    // 步骤3：设备已注册，检查本地推理服务状态
    deviceExists.value = true
    const inferReady = await checkLocalInferStatus()
    if (!inferReady) {
      deviceInitReason.value = 'model_service_not_ready'
      console.warn('[DeepNode] device registered but model service not ready, simei=%s', fingerprint)
    }
  } catch (err) {
    // 意料之外的错误（如 invoke 失败），归为网络异常
    console.error('[DeepNode] checkDeviceStatus unexpected error:', err)
    deviceInitReason.value = 'network_error'
  } finally {
    deviceCheckLoading.value = false
    deviceCheckDone.value = true
    loadingMessage.value = ''
  }
}

/** 查询 localserver 推理服务状态，就绪返回 true */
async function checkLocalInferStatus(): Promise<boolean> {
  try {
    const resp = await safeFetch(`${LOCAL_API_BASE}/api/init/status`, {
      method: 'GET',
      signal: AbortSignal.timeout(3000)
    })
    if (!resp.ok) return false
    const payload = (await resp.json()) as ApiResponse<{ infer_ready?: boolean }>
    return payload.code === 0 && payload.data?.infer_ready === true
  } catch {
    return false
  }
}

/** 初始化成功后的回调：重新执行完整设备检查 */
function onDeviceRegistered() {
  checkDeviceStatus()
}

/** 用户主动停止推理服务后的回调 */
function onStopService() {
  deviceInitReason.value = 'model_service_not_ready'
  deviceCheckDone.value = true
}

// 当 token 变化且非空时，自动执行设备检查
watch(
  () => token.value,
  (newToken) => {
    if (newToken) {
      checkDeviceStatus()
    }
  },
  { immediate: true }
)
</script>

<template>
  <!-- 未登录 → 认证页 -->
  <AuthView v-if="!isAuthed" @authenticated="persistAuth" />

  <!-- 已登录但设备检查中 → 加载提示 -->
  <div v-else-if="!deviceCheckDone" class="loading-page">
    <div class="loading-card glass">
      <div class="spinner" />
      <p>{{ loadingMessage || t('deviceInit.localserverStarting') }}</p>
    </div>
  </div>

  <!-- 已登录但设备未注册 → 设备初始化页 -->
  <DeviceInitView
    v-else-if="!deviceExists || deviceInitReason !== ''"
    :current-user="currentUser"
    :token="token"
    :unique-id="deviceFingerprint"
    :init-reason="deviceInitReason"
    @device-registered="onDeviceRegistered"
    @logout="clearAuth"
  />

  <!-- 已登录且设备已注册 → 主面板 -->
  <DeviceDetailView
    v-else
    :current-user="currentUser"
    :current-locale="currentLocale"
    :supported-locales="SUPPORTED_LOCALES"
    @logout="clearAuth"
    @change-locale="switchLocale"
    @stop-service="onStopService"
  />
</template>

<style scoped>
:global(*) {
  box-sizing: border-box;
}

:global(body) {
  margin: 0;
  background: radial-gradient(1000px 600px at 70% -20%, #213f8e 0%, rgba(15, 21, 44, 0) 60%),
    linear-gradient(180deg, #060b1f 0%, #040814 100%);
  color: #e8f0ff;
  font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.loading-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 20px;
}

.loading-card {
  width: min(400px, 100%);
  border-radius: 16px;
  padding: 40px 24px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.loading-card p {
  margin: 0;
  color: #9fb2df;
  font-size: 15px;
}

.spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(100, 130, 255, 0.2);
  border-top-color: #4a84ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.glass {
  background: linear-gradient(135deg, rgba(17, 30, 63, 0.9), rgba(11, 20, 42, 0.88));
  border: 1px solid rgba(100, 130, 255, 0.2);
  box-shadow: 0 10px 30px rgba(1, 8, 23, 0.45);
  backdrop-filter: blur(8px);
}
</style>
