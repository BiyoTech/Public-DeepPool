<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCAL_API_BASE } from '../config'
import { safeFetch } from '../http'

const props = defineProps<{
  currentUser: {
    id: number
    username: string
    phone: string
    email: string
  } | null
  token: string
  uniqueId: string
  initReason: '' | 'device_not_registered' | 'model_service_not_ready' | 'localserver_unavailable' | 'network_error'
}>()

const emit = defineEmits<{
  deviceRegistered: []
  logout: []
}>()

const { t } = useI18n()

const initializing = ref(false)
const progress = ref(0)
const initError = ref('')
const statusText = ref('')

// macOS version detection: show upgrade warning for versions below 15.0
const showMacosWarning = ref(false)

onMounted(() => {
  // Detect macOS version from navigator.userAgent
  // macOS UA format: "Mac OS X 10_15_7" or "Mac OS X 15_0_1"
  const ua = navigator.userAgent
  const match = ua.match(/Mac OS X (\d+)[_.](\d+)/)
  if (match) {
    const major = parseInt(match[1], 10)
    // macOS 10.x = old numbering (Catalina and earlier)
    // macOS 11+ = Big Sur, 12 = Monterey, 13 = Ventura, 14 = Sonoma, 15 = Sequoia
    if (major < 15) {
      showMacosWarning.value = true
    }
  }
})

type ApiResponse<T> = {
  code: number
  message: string
  data?: T
}

type LocalInitData = {
  device_ip?: string
  device_config?: Record<string, unknown>
  model_loading?: boolean
}

type StatusData = {
  infer_ready: boolean
  models?: Array<{ model_name: string; state: string; error_msg?: string }>
}

const progressLabel = computed(() => {
  if (statusText.value) return statusText.value
  return t('deviceInit.progressLabel', { value: progress.value })
})

const isBlockingError = computed(() =>
  props.initReason === 'localserver_unavailable' || props.initReason === 'network_error'
)

const reasonHint = computed(() => {
  switch (props.initReason) {
    case 'model_service_not_ready': return t('deviceInit.modelServiceNotReady')
    case 'device_not_registered': return t('deviceInit.deviceNotRegistered')
    case 'localserver_unavailable': return t('deviceInit.localserverFailed')
    case 'network_error': return t('deviceInit.networkError')
    default: return ''
  }
})

// 轮询定时器引用，用于组件销毁时清理
let pollTimer: ReturnType<typeof setTimeout> | null = null

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})

/** Step 1: 注册设备到 platform（快速，不等模型加载） */
async function callLocalInitApi(): Promise<LocalInitData> {
  const response = await safeFetch(`${LOCAL_API_BASE}/api/init/device`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      token: props.token,
      supported_models: ['qwen', 'deepseek', 'gemini']
    })
  })

  let payload: ApiResponse<LocalInitData>
  try {
    payload = (await response.json()) as ApiResponse<LocalInitData>
  } catch {
    throw new Error(`${t('deviceInit.localInitFailed')} (HTTP ${response.status})`)
  }

  if (!response.ok || payload.code !== 0) {
    throw new Error(payload.message || `${t('deviceInit.localInitFailed')} (code=${payload.code})`)
  }

  return payload.data || {}
}

/** Step 2: 轮询模型加载状态，直到 infer_ready=true 或超时 */
async function pollModelReady(maxWaitMs = 600_000): Promise<void> {
  const startTime = Date.now()
  const pollInterval = 3000

  while (Date.now() - startTime < maxWaitMs) {
    try {
      const resp = await safeFetch(`${LOCAL_API_BASE}/api/init/status`, {
        signal: AbortSignal.timeout(5000)
      })
      const body = (await resp.json()) as ApiResponse<StatusData>

      if (body.code === 0 && body.data) {
        if (body.data.infer_ready) {
          return
        }

        // 更新进度信息
        const models = body.data.models || []
        const loading = models.find(m => m.state === 'loading')
        const errored = models.find(m => m.state === 'error')

        if (errored) {
          throw new Error(errored.error_msg || t('deviceInit.modelLoadFailed'))
        }

        if (loading) {
          statusText.value = t('deviceInit.modelLoading', { name: loading.model_name })
          // 平滑增加进度（50% ~ 95%）
          const elapsed = Date.now() - startTime
          progress.value = Math.min(95, 50 + Math.floor(elapsed / maxWaitMs * 45))
        }
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('modelLoadFailed')) {
        throw err
      }
      // 网络抖动等暂时性错误，继续轮询
    }

    await new Promise(resolve => { pollTimer = setTimeout(resolve, pollInterval) })
  }

  // 超时：模型仍在加载，但设备已注册成功，允许用户进入（后台继续加载）
  console.warn('[DeepNode] model loading timeout, proceeding anyway')
}

async function startInit() {
  if (initializing.value) return

  initializing.value = true
  progress.value = 0
  initError.value = ''
  statusText.value = ''

  try {
    console.warn('[DeepNode] user triggered init, reason=%s, uniqueId=%s', props.initReason, props.uniqueId)

    // Phase 1: 注册设备（快速）
    progress.value = 10
    statusText.value = t('deviceInit.registeringDevice')
    const initData = await callLocalInitApi()
    progress.value = 40
    statusText.value = t('deviceInit.deviceRegistered')

    // Phase 2: 等待模型加载（后台异步，前端轮询）
    if (initData.model_loading) {
      progress.value = 50
      statusText.value = t('deviceInit.waitingModelLoad')
      await pollModelReady()
    }

    progress.value = 100
    statusText.value = ''
    emit('deviceRegistered')
  } catch (err) {
    const msg = err instanceof Error ? err.message : t('deviceInit.registerFailed')
    console.error('[DeepNode] init failed:', err)
    initError.value = msg
  } finally {
    initializing.value = false
    statusText.value = ''
  }
}
</script>

<template>
  <div class="init-page">
    <!-- Top-right user menu (visible when user is authenticated) -->
    <div v-if="props.currentUser" class="user-bar">
      <span class="user-name">{{ props.currentUser.username }}</span>
      <button class="user-bar-btn" @click="emit('logout')">{{ t('device.switchUser') }}</button>
      <button class="user-bar-btn logout" @click="emit('logout')">{{ t('device.logout') }}</button>
    </div>

    <section class="init-card glass">
      <h1>{{ t('deviceInit.title') }}</h1>
      <p class="subtitle">{{ t('deviceInit.subtitle') }}</p>

      <!-- macOS upgrade warning for versions below 15.0 -->
      <div v-if="showMacosWarning" class="macos-warning">
        <strong>{{ t('deviceInit.macosUpgradeTitle') }}</strong>
        <p>{{ t('deviceInit.macosUpgradeBody') }}</p>
      </div>

      <p v-if="reasonHint" class="reason-text" :class="{ 'error-hint': isBlockingError }">{{ reasonHint }}</p>

      <!-- localserver 未就绪或网络异常：仅显示重试按钮 -->
      <template v-if="isBlockingError">
        <button class="confirm-btn retry-btn" @click="emit('deviceRegistered')">
          {{ t('deviceInit.retryCheck') }}
        </button>
        <button class="logout-btn" @click="emit('logout')">
          {{ t('device.logout') }}
        </button>
      </template>

      <!-- 正常初始化流程 -->
      <template v-else>
        <button class="confirm-btn" :disabled="initializing" @click="startInit">
          {{ initializing ? t('deviceInit.initializing') : t('deviceInit.confirmJoin') }}
        </button>
      </template>

      <div v-if="initializing || progress > 0" class="progress-wrap" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
        <div class="progress-track">
          <div class="progress-inner" :style="{ width: `${progress}%` }" />
        </div>
        <p class="progress-text">{{ progressLabel }}</p>
      </div>

      <p v-if="initError" class="error-text">{{ initError }}</p>
    </section>
  </div>
</template>

<style scoped>
.init-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 20px;
  position: relative;
}

.user-bar {
  position: absolute;
  top: 16px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 10;
}

.user-name {
  color: #b5c7f3;
  font-size: 13px;
  margin-right: 4px;
}

.user-bar-btn {
  border: 1px solid rgba(100, 130, 255, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: #bdd0ff;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.user-bar-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: #e8f0ff;
}

.user-bar-btn.logout {
  border-color: rgba(255, 96, 117, 0.24);
  color: #ff8b9a;
}

.user-bar-btn.logout:hover {
  background: rgba(255, 96, 117, 0.1);
}

.init-card {
  width: min(560px, 100%);
  border-radius: 16px;
  padding: 28px;
  text-align: center;
}

.init-card h1 {
  margin: 0;
  font-size: 28px;
}

.subtitle {
  margin: 10px 0 0;
  color: #9fb2df;
  font-size: 14px;
}

.reason-text {
  margin: 8px 0 0;
  color: #ffcf66;
  font-size: 13px;
}

.confirm-btn {
  margin-top: 24px;
  width: 100%;
  height: 48px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(180deg, #2563ff, #1143d0);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
}

.confirm-btn:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}

.retry-btn {
  background: linear-gradient(180deg, #ff8f3a, #e06b10);
}

.logout-btn {
  margin-top: 12px;
  width: 100%;
  height: 40px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 10px;
  background: transparent;
  color: #9fb2df;
  font-size: 14px;
  cursor: pointer;
}

.logout-btn:hover {
  color: #e8f0ff;
  border-color: rgba(255, 255, 255, 0.3);
}

.error-hint {
  color: #ff8b9a;
}

.progress-wrap {
  margin-top: 18px;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  overflow: hidden;
}

.progress-inner {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #44d1ff, #4a84ff);
  transition: width 0.2s ease;
}

.progress-text {
  margin: 8px 0 0;
  color: #9fb2df;
  font-size: 13px;
}

.error-text {
  margin: 10px 0 0;
  color: #ff8b9a;
  font-size: 13px;
}

.macos-warning {
  margin: 16px 0 0;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(255, 170, 50, 0.1);
  border: 1px solid rgba(255, 170, 50, 0.3);
  text-align: left;
}

.macos-warning strong {
  color: #ffb74d;
  font-size: 14px;
}

.macos-warning p {
  margin: 6px 0 0;
  color: #e8c98a;
  font-size: 13px;
  line-height: 1.6;
}

.glass {
  background: linear-gradient(135deg, rgba(17, 30, 63, 0.9), rgba(11, 20, 42, 0.88));
  border: 1px solid rgba(100, 130, 255, 0.2);
  box-shadow: 0 10px 30px rgba(1, 8, 23, 0.45);
  backdrop-filter: blur(8px);
}
</style>
