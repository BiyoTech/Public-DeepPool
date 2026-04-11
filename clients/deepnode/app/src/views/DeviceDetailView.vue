<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { LOCAL_API_BASE } from '../config'
import { safeFetch, isTauri } from '../http'

type UserInfo = {
  id: number
  username: string
  phone: string
  email: string
}

type SupportedLocales = {
  zhCN: string
  enUS: string
}

type UnlistenFn = () => void

/** localserver /api/stats/snapshot response structure */
type StatsData = {
  device_status: string  // "active" / "blocked" / "cheating"
  service: {
    running: boolean
    model_name: string
    engine_type: string
    uptime_seconds: number
  }
  hardware: {
    cpu_percent: number
    memory_percent: number
    gpu_name: string
    gpu_load_percent: number
    gpu_temp_celsius: number
  }
  total: {
    requests: number
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
    reasoning_tokens: number
    avg_duration_ms: number
    local_requests: number
    tunnel_requests: number
  }
  today: {
    requests: number
    prompt_tokens: number
    completion_tokens: number
    total_tokens: number
  }
  recent_60s: {
    requests: number
    prompt_tokens: number
    completion_tokens: number
    token_output_rate: number
  }
}

const props = defineProps<{
  currentUser: UserInfo | null
  currentLocale: string
  supportedLocales: SupportedLocales
}>()

const emit = defineEmits<{
  logout: []
  changeLocale: [locale: string]
  stopService: []
}>()

const { t } = useI18n()

const paused = ref(false)
const stopping = ref(false)
const smartIdle = ref(true)
const settingsVisible = ref(false)
let unlistenMenuEvent: UnlistenFn | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

// 统计数据（来自 localserver API）
const stats = ref<StatsData | null>(null)

const userDisplayName = computed(() => props.currentUser?.username || t('common.loggedInUser'))
const gpuName = computed(() => stats.value?.hardware.gpu_name || '--')
const cpuUsage = computed(() => stats.value ? `${Math.round(stats.value.hardware.cpu_percent)}%` : '--')
const gpuUsage = computed(() => stats.value ? `${Math.round(stats.value.hardware.gpu_load_percent)}%` : '--')
const memUsage = computed(() => stats.value ? `${Math.round(stats.value.hardware.memory_percent)}%` : '--')
const gpuTemp = computed(() => {
  if (!stats.value) return '--'
  const temp = stats.value.hardware.gpu_temp_celsius
  return temp > 0 ? `${temp}°C` : '--'
})
const modelName = computed(() => stats.value?.service.model_name || '--')
const engineType = computed(() => stats.value?.service.engine_type || '--')
const serviceRunning = computed(() => stats.value?.service.running ?? false)
const deviceBlocked = computed(() => {
  const status = stats.value?.device_status
  return status === 'blocked' || status === 'cheating'
})

// 格式化大数字
function fmtNum(n: number): string {
  return n >= 1000 ? n.toLocaleString() : String(n)
}

// 格式化运行时间
function fmtUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return `${h}h ${m}m`
}

const uptimeStr = computed(() => {
  if (!stats.value) return '--'
  return fmtUptime(stats.value.service.uptime_seconds)
})

// 今日统计
const todayRequests = computed(() => stats.value ? fmtNum(stats.value.today.requests) : '0')
const todayPromptTokens = computed(() => stats.value ? fmtNum(stats.value.today.prompt_tokens) : '0')
const todayCompletionTokens = computed(() => stats.value ? fmtNum(stats.value.today.completion_tokens) : '0')

// 全量统计
const totalRequests = computed(() => stats.value ? fmtNum(stats.value.total.requests) : '0')
const totalPromptTokens = computed(() => stats.value ? fmtNum(stats.value.total.prompt_tokens) : '0')
const totalCompletionTokens = computed(() => stats.value ? fmtNum(stats.value.total.completion_tokens) : '0')
const avgDuration = computed(() => stats.value ? `${stats.value.total.avg_duration_ms}` : '0')
const tunnelRequests = computed(() => stats.value ? fmtNum(stats.value.total.tunnel_requests) : '0')

// 最近 60s（近似速率）
const recentPromptTokens = computed(() => stats.value ? fmtNum(stats.value.recent_60s.prompt_tokens) : '0')
const recentCompletionTokens = computed(() => stats.value ? fmtNum(stats.value.recent_60s.completion_tokens) : '0')

// Token output throughput (tokens/sec)
const tokenOutputRate = computed(() => {
  if (!stats.value) return '0'
  const rate = stats.value.recent_60s.token_output_rate
  return rate >= 100 ? Math.round(rate).toLocaleString() : rate.toFixed(1)
})

/** 从 localserver 拉取最新统计快照 */
async function fetchStats() {
  try {
    const resp = await safeFetch(`${LOCAL_API_BASE}/api/stats/snapshot`, {
      signal: AbortSignal.timeout(3000),
    })
    if (!resp.ok) return
    const payload = await resp.json()
    if (payload.code === 0 && payload.data) {
      stats.value = payload.data
    }
  } catch {
    // 网络异常时静默忽略，保留上次数据
  }
}

function togglePause() {
  paused.value = !paused.value
}

/** 停止推理服务：调用 localserver API，成功后通知父组件跳转到初始化页 */
async function stopService() {
  if (stopping.value) return
  stopping.value = true
  try {
    const resp = await safeFetch(`${LOCAL_API_BASE}/api/init/stop`, {
      method: 'POST',
      signal: AbortSignal.timeout(10000),
    })
    if (resp.ok) {
      const payload = await resp.json()
      if (payload.code === 0) {
        emit('stopService')
        return
      }
    }
    // 即使 API 返回异常，仍然跳转（服务可能已部分停止）
    emit('stopService')
  } catch {
    // 网络超时等异常也跳转
    emit('stopService')
  } finally {
    stopping.value = false
  }
}

function openSettings() {
  settingsVisible.value = true
}

function closeSettings() {
  settingsVisible.value = false
}

function setLocale(nextLocale: string) {
  emit('changeLocale', nextLocale)
}

onMounted(async () => {
  // 立即拉取一次
  fetchStats()
  // 每 5 秒轮询
  pollTimer = setInterval(fetchStats, 5000)

  // 仅 Tauri 模式下监听原生菜单事件
  if (isTauri) {
    try {
      const { listen } = await import('@tauri-apps/api/event')
      unlistenMenuEvent = await listen('open-settings', () => {
        openSettings()
      })
    } catch {
      unlistenMenuEvent = null
    }
  }
})

onBeforeUnmount(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  if (unlistenMenuEvent) {
    unlistenMenuEvent()
  }
})
</script>

<template>
  <div class="page">
    <header class="topbar glass">
      <div class="brand">
        <div class="logo">⚡</div>
        <div class="meta">
          <div class="title-row">
            <h1>DeepPool</h1>
            <span class="version">v1.2.4</span>
          </div>
          <p class="status">
            <span class="dot" :class="{ offline: !serviceRunning || deviceBlocked, blocked: deviceBlocked }" />
            {{ deviceBlocked ? t('device.statusBlocked') : (userDisplayName + ' ' + (serviceRunning ? t('device.statusSuffix') : t('device.statusOffline'))) }}
          </p>
        </div>
      </div>
      <div class="toolbar-actions">
        <button class="toolbar-btn" @click="openSettings">{{ t('settings.menu') }}</button>
        <button class="toolbar-btn" @click="emit('logout')">{{ t('device.switchUser') }}</button>
        <button class="toolbar-btn toolbar-btn-danger" aria-label="logout" @click="emit('logout')">{{ t('device.logout') }}</button>
      </div>
    </header>

    <main class="layout">
      <aside class="left-column">
        <!-- 硬件信息 -->
        <section class="card glass hardware-card">
          <div class="card-title">{{ t('device.hardwareInfo') }}</div>
          <div class="kv">
            <span>{{ t('device.gpuModel') }}</span>
            <strong>{{ gpuName }}</strong>
          </div>
          <div class="kv">
            <span>{{ t('device.modelLabel') }}</span>
            <strong class="model-name">{{ modelName }}</strong>
          </div>
          <div class="kv">
            <span>{{ t('device.engineLabel') }}</span>
            <strong class="engine-type">{{ engineType }}</strong>
          </div>
          <div class="grid-3">
            <div>
              <p class="muted">{{ t('device.cpuUsage') }}</p>
              <p class="value">{{ cpuUsage }}</p>
            </div>
            <div>
              <p class="muted">{{ t('device.gpuUsage') }}</p>
              <p class="value">{{ gpuUsage }}</p>
            </div>
            <div>
              <p class="muted">{{ t('device.memUsage') }}</p>
              <p class="value">{{ memUsage }}</p>
            </div>
          </div>
          <div class="grid-2" style="margin-top: 8px;">
            <div>
              <p class="muted">{{ t('device.temp') }}</p>
              <p class="value small">{{ gpuTemp }}</p>
            </div>
          </div>
          <div class="grid-2" style="margin-top: 8px;">
            <div>
              <p class="muted">{{ t('device.uptime') }}</p>
              <p class="value small">{{ uptimeStr }}</p>
            </div>
            <div>
              <p class="muted">{{ t('device.avgLatency') }}</p>
              <p class="value small">{{ avgDuration }}<span class="unit">ms</span></p>
            </div>
          </div>
        </section>

        <!-- 积分（预留） -->
        <section class="wallet">
          <div class="wallet-top">
            <span class="wallet-icon">💳</span>
            <button class="history">{{ t('device.history') }}</button>
          </div>
          <p class="wallet-label">{{ t('device.scoreLabel') }}</p>
          <p class="wallet-score">-- <span>SGP</span></p>
          <p class="wallet-hint">{{ t('device.scorePending') }}</p>
        </section>
      </aside>

      <!-- 右侧实时统计面板 -->
      <section class="right-panel glass">
        <div class="panel-title-row">
          <h2>{{ t('device.realtimeTitle') }}</h2>
          <span class="chip" :class="{ active: serviceRunning && !deviceBlocked, blocked: deviceBlocked }">
            {{ deviceBlocked ? t('device.statusBlocked') : (serviceRunning ? t('device.grpcConnected') : t('device.grpcDisconnected')) }}
          </span>
        </div>

        <!-- 今日统计 -->
        <div class="section-label">{{ t('device.todayStats') }}</div>
        <div class="stats-grid triple">
          <article class="stat-card">
            <p class="muted">{{ t('device.todayRequests') }}</p>
            <p class="speed">{{ todayRequests }}</p>
          </article>
          <article class="stat-card">
            <p class="muted">{{ t('device.todayTotalTokens') }}</p>
            <p class="speed">{{ stats ? fmtNum(stats.today.total_tokens) : '0' }}</p>
          </article>
          <article class="stat-card highlight-rate">
            <p class="muted">{{ t('device.tokenOutputRate') }}</p>
            <p class="speed rate-value">{{ tokenOutputRate }}<span class="rate-unit">{{ t('device.tokenPerSec') }}</span></p>
          </article>
        </div>

        <!-- Token 流量 -->
        <div class="section-label" style="margin-top: 12px;">{{ t('device.tokenTraffic') }}</div>
        <div class="stats-grid">
          <article class="stat-card">
            <p class="muted">{{ t('device.inboundToken') }}</p>
            <p class="token-value green">{{ totalPromptTokens }}</p>
            <p class="muted mini">{{ t('device.recent60s') }}: {{ recentPromptTokens }}</p>
          </article>
          <article class="stat-card">
            <p class="muted">{{ t('device.outboundToken') }}</p>
            <p class="token-value blue">{{ totalCompletionTokens }}</p>
            <p class="muted mini">{{ t('device.recent60s') }}: {{ recentCompletionTokens }}</p>
          </article>
        </div>

        <!-- 累计/来源 -->
        <div class="section-label" style="margin-top: 12px;">{{ t('device.totalStats') }}</div>
        <div class="stats-grid triple">
          <article class="stat-card compact">
            <p class="muted">{{ t('device.totalRequests') }}</p>
            <p class="compact-value">{{ totalRequests }}</p>
          </article>
          <article class="stat-card compact">
            <p class="muted">{{ t('device.tunnelRequests') }}</p>
            <p class="compact-value">{{ tunnelRequests }}</p>
          </article>
          <article class="stat-card compact">
            <p class="muted">{{ t('device.todayCompletionTokens') }}</p>
            <p class="compact-value">{{ todayCompletionTokens }}</p>
          </article>
        </div>

        <div class="actions">
          <button class="stop-btn" :disabled="stopping" @click="stopService">
            {{ stopping ? t('device.stopping') : t('device.stopService') }}
          </button>

          <label class="idle-box">
            <div>
              <p class="idle-title">{{ t('device.smartIdleTitle') }}</p>
              <p class="idle-desc">{{ t('device.smartIdleDesc') }}</p>
            </div>
            <input v-model="smartIdle" type="checkbox" />
            <span class="switch" />
          </label>
        </div>
      </section>
    </main>

    <footer class="notice glass" :class="{ 'notice-blocked': deviceBlocked }">
      <strong>{{ deviceBlocked ? t('device.blockedNoticeTitle') : t('device.safeNoticeTitle') }}</strong>
      {{ deviceBlocked ? t('device.blockedNoticeBody') : t('device.safeNoticeBody') }}
    </footer>

    <!-- 设置弹窗 -->
    <div v-if="settingsVisible" class="settings-mask" @click.self="closeSettings">
      <section class="settings-modal glass">
        <div class="settings-header">
          <h3>{{ t('settings.title') }}</h3>
          <button class="close-btn" @click="closeSettings">{{ t('settings.close') }}</button>
        </div>

        <div class="settings-body">
          <p class="settings-item-title">{{ t('settings.language') }}</p>
          <div class="lang-options">
            <button
              class="lang-btn"
              :class="{ active: currentLocale === supportedLocales.zhCN }"
              @click="setLocale(supportedLocales.zhCN)"
            >
              {{ t('common.chinese') }}
            </button>
            <button
              class="lang-btn"
              :class="{ active: currentLocale === supportedLocales.enUS }"
              @click="setLocale(supportedLocales.enUS)"
            >
              {{ t('common.english') }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  max-width: 1600px;
  margin: 0 auto;
  padding: clamp(12px, 2vw, 20px);
  display: flex;
  flex-direction: column;
  gap: clamp(10px, 1.2vw, 16px);
}

.glass {
  background: linear-gradient(135deg, rgba(17, 30, 63, 0.9), rgba(11, 20, 42, 0.88));
  border: 1px solid rgba(100, 130, 255, 0.2);
  box-shadow: 0 10px 30px rgba(1, 8, 23, 0.45);
  backdrop-filter: blur(8px);
}

.topbar {
  border-radius: 14px;
  padding: clamp(10px, 1.2vw, 14px) clamp(12px, 1.6vw, 18px);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo {
  width: clamp(36px, 3vw, 42px);
  height: clamp(36px, 3vw, 42px);
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #2563ff, #1143d0);
  box-shadow: 0 8px 20px rgba(37, 99, 255, 0.4);
}

.title-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

h1, h2, p { margin: 0; }

h1 {
  font-size: clamp(22px, 2.4vw, 32px);
  line-height: 1.1;
}

.version {
  color: #3e82ff;
  font-weight: 600;
  font-size: clamp(14px, 1.4vw, 24px);
}

.status {
  margin-top: 2px;
  color: #b5c7f3;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: clamp(12px, 1.1vw, 14px);
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00db8d;
  box-shadow: 0 0 10px #00db8d;
}

.dot.offline {
  background: #ff6075;
  box-shadow: 0 0 10px #ff6075;
}

.dot.blocked {
  background: #ff6075;
  box-shadow: 0 0 10px #ff6075;
  animation: blocked-pulse 2s ease-in-out infinite;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  border: 0;
  border-radius: 8px;
  cursor: pointer;
  color: #bdd0ff;
  background: rgba(255, 255, 255, 0.06);
  padding: 8px 12px;
}

.toolbar-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.toolbar-btn-danger {
  color: #ff8b9a;
  border: 1px solid rgba(255, 96, 117, 0.24);
}

.toolbar-btn-danger:hover {
  background: rgba(255, 96, 117, 0.1);
}

.layout {
  display: grid;
  grid-template-columns: minmax(290px, 360px) minmax(0, 1fr);
  gap: clamp(10px, 1.2vw, 16px);
}

.left-column {
  display: flex;
  flex-direction: column;
  gap: clamp(10px, 1.2vw, 16px);
}

.card {
  border-radius: 14px;
  padding: clamp(14px, 1.5vw, 18px);
}

.card-title {
  font-weight: 700;
  margin-bottom: 12px;
  font-size: clamp(16px, 1.4vw, 22px);
}

.kv {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 10px;
}

.kv span, .muted {
  color: #95a9d6;
  font-size: clamp(12px, 1vw, 14px);
}

.kv strong {
  font-size: clamp(16px, 1.6vw, 26px);
  line-height: 1.25;
}

.model-name, .engine-type {
  font-size: clamp(14px, 1.2vw, 18px) !important;
  color: #7eb3ff;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.grid-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.value {
  margin-top: 4px;
  font-size: clamp(28px, 2.4vw, 40px);
  font-weight: 700;
}

.value.small {
  font-size: clamp(20px, 1.8vw, 30px);
}

.unit {
  font-size: 0.5em;
  color: #95a9d6;
  margin-left: 2px;
}

.wallet {
  border-radius: 16px;
  padding: clamp(14px, 1.5vw, 18px);
  background: linear-gradient(180deg, #1f4df3 0%, #183bc3 100%);
  box-shadow: 0 15px 30px rgba(18, 52, 179, 0.45);
}

.wallet-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history {
  border: none;
  border-radius: 8px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
  cursor: pointer;
  font-size: clamp(12px, 1vw, 14px);
}

.wallet-label {
  margin-top: 12px;
  font-size: clamp(13px, 1.1vw, 15px);
  color: #d6e4ff;
}

.wallet-score {
  margin-top: 6px;
  font-size: clamp(44px, 4vw, 60px);
  font-weight: 800;
  line-height: 1;
}

.wallet-score span {
  font-size: clamp(26px, 2vw, 34px);
}

.wallet-hint {
  margin-top: 10px;
  font-size: clamp(12px, 1vw, 13px);
  color: rgba(255, 255, 255, 0.55);
}

.right-panel {
  border-radius: 14px;
  padding: clamp(14px, 1.7vw, 22px);
}

.panel-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  gap: 10px;
}

h2 {
  font-size: clamp(22px, 2vw, 34px);
}

.chip {
  color: #ff6075;
  background: rgba(255, 96, 117, 0.1);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: clamp(12px, 1vw, 14px);
  white-space: nowrap;
}

.chip.active {
  color: #2cf6a6;
  background: rgba(44, 246, 166, 0.1);
}

.chip.blocked {
  color: #ff6075;
  background: rgba(255, 96, 117, 0.15);
  border: 1px solid rgba(255, 96, 117, 0.3);
  animation: blocked-pulse 2s ease-in-out infinite;
}

@keyframes blocked-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.section-label {
  color: #95a9d6;
  font-size: clamp(12px, 1vw, 14px);
  margin-bottom: 8px;
  font-weight: 600;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: clamp(10px, 1.2vw, 16px);
}

.stats-grid.triple {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.stat-card {
  border-radius: 12px;
  padding: clamp(14px, 1.5vw, 18px);
  background: rgba(8, 16, 35, 0.65);
  border: 1px solid rgba(111, 138, 237, 0.16);
}

.stat-card.compact {
  padding: clamp(10px, 1vw, 14px);
}

.speed {
  margin-top: 8px;
  font-size: clamp(36px, 3vw, 56px);
  font-weight: 800;
  line-height: 1;
}

.speed span {
  font-size: clamp(18px, 1.5vw, 28px);
}

.token { margin-top: 4px; }

.token-value {
  margin-top: 8px;
  font-size: clamp(32px, 2.8vw, 48px);
  font-weight: 800;
  line-height: 1;
}

.compact-value {
  margin-top: 6px;
  font-size: clamp(24px, 2vw, 36px);
  font-weight: 800;
  line-height: 1;
}

.green { color: #2cf6a6; }
.blue { color: #40a2ff; }

.highlight-rate {
  border-color: rgba(44, 246, 166, 0.3);
  background: rgba(44, 246, 166, 0.06);
}

.rate-value {
  color: #2cf6a6;
}

.rate-unit {
  font-size: 0.35em;
  color: #95a9d6;
  margin-left: 4px;
  font-weight: 600;
}

.mini {
  margin-top: 8px;
  font-size: clamp(11px, 0.9vw, 13px) !important;
  opacity: 0.7;
}

.actions {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(10px, 1.2vw, 16px);
}

.stop-btn {
  border: 1px solid rgba(242, 88, 105, 0.25);
  border-radius: 12px;
  background: rgba(26, 13, 20, 0.82);
  color: #ff6075;
  padding: clamp(14px, 1.6vw, 18px);
  font-size: clamp(26px, 2.1vw, 40px);
  font-weight: 800;
  cursor: pointer;
}

.stop-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.idle-box {
  border: 1px solid rgba(102, 138, 230, 0.2);
  border-radius: 12px;
  background: rgba(8, 16, 35, 0.65);
  padding: clamp(12px, 1.3vw, 16px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
}

.idle-title {
  font-size: clamp(22px, 1.9vw, 32px);
  font-weight: 800;
}

.idle-desc {
  margin-top: 6px;
  color: #92a8d9;
  font-size: clamp(12px, 1vw, 14px);
}

.idle-box input { display: none; }

.switch {
  width: 56px;
  height: 30px;
  background: #4d5a75;
  border-radius: 999px;
  position: relative;
  flex-shrink: 0;
  transition: background 0.2s ease;
}

.switch::after {
  content: '';
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  position: absolute;
  top: 3px;
  left: 3px;
  transition: transform 0.2s ease;
}

.idle-box input:checked + .switch { background: #3e82ff; }
.idle-box input:checked + .switch::after { transform: translateX(26px); }

.notice {
  border-radius: 12px;
  padding: clamp(12px, 1.2vw, 14px) clamp(12px, 1.4vw, 16px);
  color: #9fb2df;
  font-size: clamp(12px, 1vw, 14px);
  border-color: rgba(255, 173, 57, 0.22);
}

.notice strong { color: #ffb347; }

.notice-blocked {
  border-color: rgba(255, 96, 117, 0.35);
  background: linear-gradient(135deg, rgba(60, 15, 20, 0.9), rgba(35, 10, 15, 0.88));
  color: #ffb0b8;
}

.notice-blocked strong { color: #ff6075; }

.settings-mask {
  position: fixed;
  inset: 0;
  background: rgba(2, 7, 18, 0.6);
  display: grid;
  place-items: center;
  z-index: 100;
  padding: 16px;
}

.settings-modal {
  width: min(520px, 100%);
  border-radius: 14px;
  padding: 16px;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.settings-header h3 { margin: 0; }

.close-btn {
  border: 1px solid rgba(100, 130, 255, 0.3);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: #c7d8ff;
  padding: 6px 10px;
  cursor: pointer;
}

.settings-item-title {
  color: #9fb2df;
  margin-bottom: 10px;
}

.lang-options {
  display: flex;
  gap: 8px;
}

.lang-btn {
  border: 1px solid rgba(100, 130, 255, 0.24);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: #bdd0ff;
  padding: 8px 10px;
  cursor: pointer;
}

.lang-btn.active {
  background: #2a63ff;
  border-color: #2a63ff;
  color: #fff;
}

@media (max-width: 1280px) {
  .layout { grid-template-columns: 1fr; }
  .left-column { display: grid; grid-template-columns: 1fr 1fr; }
}

@media (max-width: 920px) {
  .left-column, .stats-grid, .stats-grid.triple, .actions, .grid-3 { grid-template-columns: 1fr; }
  .panel-title-row { flex-wrap: wrap; }
  .chip { margin-left: 0; }
  .toolbar-actions { flex-wrap: wrap; justify-content: flex-end; }
}
</style>
