"""Web Dashboard 状态页 + 设备指纹 API + Vue SPA 静态文件托管。

提供：
  - GET /api/device/fingerprint  返回当前设备 simei
  - GET /                        Vue SPA 入口（standalone 模式）或内置 HTML 状态页（sidecar 模式）

standalone 模式下，Vue 构建产物（dist-standalone/）随二进制打包分发，
由 FastAPI StaticFiles 中间件托管静态资源，`GET /` 返回 Vue 的 index.html。
用户打开浏览器即可看到完整的登录 → 初始化 → 主面板界面。

sidecar（Tauri）模式下，前端由 Tauri WebView 加载，localserver 仅提供 API，
`GET /` 回退到内置的轻量 HTML 状态页。
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, FileResponse

from service.device_fingerprint import get_cached_simei

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ─────────────────────────────────────────────────
# Vue SPA 静态文件目录探测
# ─────────────────────────────────────────────────

def _find_web_dist_dir() -> Path | None:
    """探测 Vue SPA 构建产物目录。

    按优先级搜索：
      1. PyInstaller 打包后的 _MEIPASS/web-dist/
      2. 同级 web-dist/ 目录（手动部署场景）
      3. 开发环境相邻的 ../app/dist-standalone/
    """
    candidates: list[Path] = []

    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        candidates.append(Path(meipass) / 'web-dist')

    localserver_dir = Path(__file__).resolve().parent.parent
    candidates.extend([
        localserver_dir / 'web-dist',
        localserver_dir.parent / 'app' / 'dist-standalone',
    ])

    for path in candidates:
        index = path / 'index.html'
        if index.is_file():
            logger.info("vue SPA found at %s", path)
            return path

    return None


# 模块加载时探测一次，后续复用
_WEB_DIST_DIR = _find_web_dist_dir()


def get_web_dist_dir() -> Path | None:
    """返回 Vue SPA 构建产物目录（供 main.py 挂载 StaticFiles 使用）。"""
    return _WEB_DIST_DIR


# ─────────────────────────────────────────────────
# API 端点
# ─────────────────────────────────────────────────

@router.get("/api/device/fingerprint")
def get_fingerprint() -> dict:
    """返回当前设备 simei（由 Python 指纹模块生成并缓存）。"""
    try:
        simei = get_cached_simei()
        return {"code": 0, "message": "ok", "data": {"simei": simei}}
    except RuntimeError as exc:
        logger.error("failed to get device fingerprint: %s", exc)
        return {"code": 500, "message": f"fingerprint unavailable: {exc}"}


@router.get("/", response_model=None)
def dashboard_page() -> HTMLResponse | FileResponse:
    """返回前端页面。

    如果探测到 Vue SPA 构建产物，返回 SPA 的 index.html（支持完整登录流程）。
    否则返回内置的轻量 HTML 状态页。
    """
    if _WEB_DIST_DIR is not None:
        return FileResponse(_WEB_DIST_DIR / 'index.html', media_type='text/html')
    return HTMLResponse(_FALLBACK_DASHBOARD_HTML)


# ─────────────────────────────────────────────────
# 内置回退 HTML 状态页（精简版，当 Vue SPA 不可用时使用）
# ─────────────────────────────────────────────────

_FALLBACK_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DeepNode Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{
  background:radial-gradient(1200px 700px at 70% -15%,#213f8e 0%,rgba(15,21,44,0) 55%),
             linear-gradient(180deg,#060b1f 0%,#040814 100%);
  color:#e8f0ff;
  font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  min-height:100vh;
}
/* 顶部导航 */
.navbar{
  height:56px;display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;border-bottom:1px solid rgba(100,130,255,0.15);
  background:rgba(8,14,32,0.7);backdrop-filter:blur(10px);
  position:sticky;top:0;z-index:10;
}
.nav-left{display:flex;align-items:center;gap:10px}
.logo{font-size:18px;font-weight:700;letter-spacing:0.5px}
.logo span{color:#4a84ff}
.version{font-size:11px;color:#5a6e9e;background:rgba(74,132,255,0.12);padding:2px 8px;border-radius:4px}
.nav-right{display:flex;align-items:center;gap:12px;font-size:13px;color:#8a9bc0}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.status-dot.online{background:#2dd96f;box-shadow:0 0 6px rgba(45,217,111,0.5)}
.status-dot.offline{background:#ff5a5a;box-shadow:0 0 6px rgba(255,90,90,0.5)}

/* 主内容 */
.main{max-width:1100px;margin:0 auto;padding:24px}

/* 信息卡片区 */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:24px}
.card{
  background:linear-gradient(135deg,rgba(17,30,63,0.9),rgba(11,20,42,0.88));
  border:1px solid rgba(100,130,255,0.12);border-radius:8px;
  padding:16px 18px;position:relative;overflow:hidden;
}
.card::before{content:'';position:absolute;left:0;top:0;width:3px;height:100%;background:#4a84ff;border-radius:2px}
.card-label{font-size:12px;color:#6b7da0;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
.card-value{font-size:16px;font-weight:600;color:#e8f0ff;word-break:break-all;font-family:'SF Mono',Consolas,monospace}

/* 硬件监控 */
.monitor-section{margin-bottom:24px}
.section-title{font-size:14px;font-weight:600;color:#8a9bc0;margin-bottom:14px;text-transform:uppercase;letter-spacing:1px}
.gauges{display:flex;gap:32px;justify-content:center;flex-wrap:wrap}
.gauge{text-align:center}
.gauge svg{width:100px;height:100px}
.gauge-bg{fill:none;stroke:rgba(255,255,255,0.08);stroke-width:8}
.gauge-fill{fill:none;stroke-width:8;stroke-linecap:round;transition:stroke-dashoffset 0.6s ease,stroke 0.6s ease}
.gauge-text{font-size:18px;font-weight:700;fill:#e8f0ff;font-family:'SF Mono',Consolas,monospace}
.gauge-label{font-size:12px;color:#6b7da0;margin-top:6px}
.gpu-name{font-size:12px;color:#5a6e9e;margin-top:4px;text-align:center}

/* 统计数据 */
.stats-section{margin-bottom:24px}
.stats-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.stats-block{
  background:linear-gradient(135deg,rgba(17,30,63,0.9),rgba(11,20,42,0.88));
  border:1px solid rgba(100,130,255,0.12);border-radius:8px;padding:18px;
}
.stats-block h3{font-size:13px;color:#8a9bc0;margin-bottom:12px;font-weight:600}
.stat-row{display:flex;justify-content:space-between;align-items:center;padding:4px 0}
.stat-label{font-size:12px;color:#6b7da0}
.stat-value{font-size:15px;font-weight:600;color:#e8f0ff;font-family:'SF Mono',Consolas,monospace}
.rate-row{
  margin-top:16px;padding-top:12px;border-top:1px solid rgba(100,130,255,0.1);
  display:flex;justify-content:center;gap:32px;
}
.rate-item{text-align:center}
.rate-val{font-size:14px;font-weight:600;color:#4a84ff;font-family:'SF Mono',Consolas,monospace}
.rate-label{font-size:11px;color:#5a6e9e;margin-top:2px}

/* 底部状态栏 */
.footer{
  text-align:center;padding:16px;font-size:12px;color:#5a6e9e;
  border-top:1px solid rgba(100,130,255,0.08);
}
.footer span{margin:0 12px}

/* Disconnect banner */
.disconnect-banner{
  display:none;background:rgba(255,70,70,0.15);border:1px solid rgba(255,90,90,0.4);
  border-radius:8px;padding:12px 18px;margin-bottom:18px;text-align:center;
  color:#ff8a8a;font-size:13px;
}
.disconnect-banner strong{color:#ff5a5a}

@media(max-width:600px){
  .stats-grid{grid-template-columns:1fr}
  .gauges{gap:20px}
}
</style>
</head>
<body>

<nav class="navbar">
  <div class="nav-left">
    <div class="logo">Deep<span>Node</span></div>
    <span class="version">v1.0</span>
  </div>
  <div class="nav-right">
    <span id="nav-simei">--</span>
    <span class="status-dot" id="status-dot"></span>
  </div>
</nav>

<div class="main">
  <!-- Disconnect warning banner -->
  <div class="disconnect-banner" id="disconnect-banner">
    <strong>Platform Disconnected</strong> — Backend service unreachable. Auto-reconnecting...
  </div>

  <!-- 信息卡片 -->
  <div class="cards">
    <div class="card"><div class="card-label">设备 SIMEI</div><div class="card-value" id="c-simei">--</div></div>
    <div class="card"><div class="card-label">推理模型</div><div class="card-value" id="c-model">--</div></div>
    <div class="card"><div class="card-label">推理引擎</div><div class="card-value" id="c-engine">--</div></div>
    <div class="card"><div class="card-label">运行时长</div><div class="card-value" id="c-uptime">--</div></div>
  </div>

  <!-- 硬件监控 -->
  <div class="monitor-section">
    <div class="section-title">硬件监控</div>
    <div class="gauges">
      <div class="gauge">
        <svg viewBox="0 0 100 100">
          <circle class="gauge-bg" cx="50" cy="50" r="40"/>
          <circle class="gauge-fill" id="g-cpu" cx="50" cy="50" r="40"
                  stroke-dasharray="251.3" stroke-dashoffset="251.3"
                  transform="rotate(-90 50 50)"/>
          <text class="gauge-text" x="50" y="54" text-anchor="middle" id="g-cpu-text">0%</text>
        </svg>
        <div class="gauge-label">CPU</div>
      </div>
      <div class="gauge">
        <svg viewBox="0 0 100 100">
          <circle class="gauge-bg" cx="50" cy="50" r="40"/>
          <circle class="gauge-fill" id="g-mem" cx="50" cy="50" r="40"
                  stroke-dasharray="251.3" stroke-dashoffset="251.3"
                  transform="rotate(-90 50 50)"/>
          <text class="gauge-text" x="50" y="54" text-anchor="middle" id="g-mem-text">0%</text>
        </svg>
        <div class="gauge-label">内存</div>
      </div>
      <div class="gauge">
        <svg viewBox="0 0 100 100">
          <circle class="gauge-bg" cx="50" cy="50" r="40"/>
          <circle class="gauge-fill" id="g-gpu" cx="50" cy="50" r="40"
                  stroke-dasharray="251.3" stroke-dashoffset="251.3"
                  transform="rotate(-90 50 50)"/>
          <text class="gauge-text" x="50" y="54" text-anchor="middle" id="g-gpu-text">0%</text>
        </svg>
        <div class="gauge-label">GPU</div>
      </div>
    </div>
    <div class="gpu-name" id="gpu-name"></div>
  </div>

  <!-- 推理统计 -->
  <div class="stats-section">
    <div class="section-title">推理统计</div>
    <div class="stats-grid">
      <div class="stats-block">
        <h3>全量统计</h3>
        <div class="stat-row"><span class="stat-label">总请求数</span><span class="stat-value" id="s-total-req">0</span></div>
        <div class="stat-row"><span class="stat-label">Prompt Tokens</span><span class="stat-value" id="s-total-pt">0</span></div>
        <div class="stat-row"><span class="stat-label">Completion Tokens</span><span class="stat-value" id="s-total-ct">0</span></div>
        <div class="stat-row"><span class="stat-label">总 Tokens</span><span class="stat-value" id="s-total-tt">0</span></div>
      </div>
      <div class="stats-block">
        <h3>今日统计</h3>
        <div class="stat-row"><span class="stat-label">总请求数</span><span class="stat-value" id="s-today-req">0</span></div>
        <div class="stat-row"><span class="stat-label">Prompt Tokens</span><span class="stat-value" id="s-today-pt">0</span></div>
        <div class="stat-row"><span class="stat-label">Completion Tokens</span><span class="stat-value" id="s-today-ct">0</span></div>
        <div class="stat-row"><span class="stat-label">总 Tokens</span><span class="stat-value" id="s-today-tt">0</span></div>
      </div>
    </div>
    <div class="rate-row">
      <div class="rate-item"><div class="rate-val" id="r-rpm">0</div><div class="rate-label">请求/分钟</div></div>
      <div class="rate-item"><div class="rate-val" id="r-tpm">0</div><div class="rate-label">Tokens/分钟</div></div>
    </div>
  </div>
</div>

<div class="footer">
  <span id="f-start">启动时间: --</span>
  <span id="f-now">当前时间: --</span>
  <span id="f-refresh">下次刷新: 5s</span>
</div>

<script>
const REFRESH_INTERVAL = 5000;
let countdown = 5;
let startTime = null;

// 颜色渐变：绿 → 黄 → 红
function gaugeColor(pct) {
  if (pct < 50) return `hsl(${120 - pct * 1.2}, 80%, 55%)`;
  if (pct < 80) return `hsl(${120 - pct * 1.2}, 90%, 50%)`;
  return `hsl(0, 85%, 58%)`;
}

function setGauge(id, pct) {
  const el = document.getElementById(id);
  const textEl = document.getElementById(id + '-text');
  const circumference = 251.3;
  const offset = circumference * (1 - Math.min(pct, 100) / 100);
  el.style.strokeDashoffset = offset;
  el.style.stroke = gaugeColor(pct);
  textEl.textContent = Math.round(pct) + '%';
}

function formatUptime(sec) {
  if (!sec || sec < 0) return '--';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  return `${h}h ${m}m ${s}s`;
}

function formatNum(n) {
  return (n || 0).toLocaleString();
}

function nowStr() {
  return new Date().toLocaleString('zh-CN', {hour12: false});
}

async function fetchSimei() {
  try {
    const resp = await fetch('/api/device/fingerprint');
    const data = await resp.json();
    const simei = data.data?.simei || '--';
    document.getElementById('c-simei').textContent = simei;
    document.getElementById('nav-simei').textContent = simei.length > 12 ? simei.slice(0,12) + '...' : simei;
  } catch(e) {
    console.warn('fetch simei failed', e);
  }
}

let prevPlatformConnected = true;

async function refresh() {
  try {
    const resp = await fetch('/api/stats/snapshot');
    const json = await resp.json();
    const d = json.data || {};
    const svc = d.service || {};
    const hw = d.hardware || {};
    const total = d.total || {};
    const today = d.today || {};
    const recent = d.recent_60s || {};

    // Platform connectivity — auto-reload page when backend recovers
    const connected = d.platform_connected !== false;
    if (!prevPlatformConnected && connected) {
      console.log('platform recovered, reloading page...');
      location.reload();
      return;
    }
    prevPlatformConnected = connected;

    // Show/hide disconnected banner
    const banner = document.getElementById('disconnect-banner');
    if (banner) {
      banner.style.display = connected ? 'none' : 'block';
    }

    // Service info
    document.getElementById('c-model').textContent = svc.model_name || '--';
    document.getElementById('c-engine').textContent = svc.engine_type || '--';
    document.getElementById('c-uptime').textContent = formatUptime(svc.uptime_seconds);

    // Status indicator
    const dot = document.getElementById('status-dot');
    dot.className = 'status-dot ' + (svc.running && connected ? 'online' : 'offline');

    // Hardware
    setGauge('g-cpu', hw.cpu_percent || 0);
    setGauge('g-mem', hw.memory_percent || 0);
    setGauge('g-gpu', hw.gpu_load_percent || 0);
    document.getElementById('gpu-name').textContent = hw.gpu_name || '';

    // Stats
    document.getElementById('s-total-req').textContent = formatNum(total.requests);
    document.getElementById('s-total-pt').textContent = formatNum(total.prompt_tokens);
    document.getElementById('s-total-ct').textContent = formatNum(total.completion_tokens);
    document.getElementById('s-total-tt').textContent = formatNum(total.total_tokens);
    document.getElementById('s-today-req').textContent = formatNum(today.requests);
    document.getElementById('s-today-pt').textContent = formatNum(today.prompt_tokens);
    document.getElementById('s-today-ct').textContent = formatNum(today.completion_tokens);
    document.getElementById('s-today-tt').textContent = formatNum(today.total_tokens);

    // 速率（最近 60s 换算为每分钟）
    document.getElementById('r-rpm').textContent = formatNum(recent.requests);
    const recentTokens = (recent.prompt_tokens || 0) + (recent.completion_tokens || 0);
    document.getElementById('r-tpm').textContent = formatNum(recentTokens);

    // 启动时间
    if (svc.running && svc.uptime_seconds > 0 && !startTime) {
      startTime = new Date(Date.now() - svc.uptime_seconds * 1000);
    }
    document.getElementById('f-start').textContent = '启动时间: ' + (startTime ? startTime.toLocaleString('zh-CN', {hour12:false}) : '--');
  } catch(e) {
    console.warn('refresh failed', e);
  }
}

// 初始化
fetchSimei();
refresh();

setInterval(() => {
  refresh();
  countdown = 5;
}, REFRESH_INTERVAL);

setInterval(() => {
  countdown = Math.max(0, countdown - 1);
  document.getElementById('f-now').textContent = '当前时间: ' + nowStr();
  document.getElementById('f-refresh').textContent = '下次刷新: ' + countdown + 's';
}, 1000);
</script>
</body>
</html>"""
