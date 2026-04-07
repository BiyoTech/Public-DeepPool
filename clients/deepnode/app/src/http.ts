/**
 * 统一 HTTP 请求封装。
 *
 * 所有前端请求均通过 localserver 转发（无论 dev / Tauri / standalone），
 * 不存在跨域问题，统一使用原生 fetch。
 *
 * isTauri 变量仅用于 Tauri 原生功能检测（如 stop_localserver、菜单监听），
 * 不再影响 HTTP 请求方式。
 */

/** 是否运行在 Tauri WebView 环境中（仅用于 Tauri 原生 API 调用，不影响 HTTP 请求） */
export const isTauri: boolean =
  typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

/**
 * Global callback invoked when any API response returns 401 (token expired).
 * Set by App.vue to trigger clearAuth() and redirect to login.
 */
let onUnauthorized: (() => void) | null = null

/** Register the global 401 handler. Called once from App.vue. */
export function setOnUnauthorized(handler: () => void) {
  onUnauthorized = handler
}

/**
 * 统一 fetch —— 所有请求走 localserver 代理，直接使用原生 fetch。
 * Automatically triggers onUnauthorized callback when response is 401.
 *
 * @param input  请求 URL 或 Request 对象
 * @param init   可选的 RequestInit 配置
 * @returns      标准 Response 对象
 */
export async function safeFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  const resp = await fetch(input, init)
  if (resp.status === 401 && onUnauthorized) {
    onUnauthorized()
  }
  return resp
}
