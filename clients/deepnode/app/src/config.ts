/**
 * 全局配置：通过 Vite 环境变量注入，支持 .env 文件覆盖。
 *
 * 统一架构：所有请求均通过 localserver 本地 API 处理，
 * localserver 内部通过 gRPC 与远程 Platform Manager 通信，
 * 前端不再直连任何远程服务，消除跨域问题和 HTTP 端口依赖。
 */

/**
 * 判断是否运行在 Tauri WebView 中。
 */
const _isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

/**
 * 本地 localserver API 地址。
 *
 * - dev 模式：空字符串（走 Vite proxy 代理）
 * - standalone 浏览器模式：空字符串（前端由 localserver 同源托管，直接相对路径访问）
 * - Tauri DMG 模式：完整地址直连 localserver
 */
export const LOCAL_API_BASE: string =
  import.meta.env.VITE_LOCAL_API_BASE ||
  (import.meta.env.DEV || !_isTauri ? '' : 'http://127.0.0.1:8765')
