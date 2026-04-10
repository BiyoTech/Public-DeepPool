/**
 * Unified HTTP request wrapper.
 *
 * All frontend requests go through localserver (dev / Tauri / standalone),
 * no cross-origin issues — uses native fetch exclusively.
 *
 * isTauri is only used for Tauri-native feature detection (e.g. stop_localserver,
 * menu listeners) and does NOT affect HTTP request routing.
 */

/** Whether running inside a Tauri WebView (for Tauri-native APIs only, not HTTP) */
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
 * Unified fetch — all requests go through localserver proxy via native fetch.
 *
 * Detects unauthorized state in two ways:
 *   1. HTTP status 401 (standard)
 *   2. JSON body with code === 401 (legacy API format, e.g. when platform
 *      returns token-expired but localserver wraps it in HTTP 200)
 *
 * When either is detected, triggers onUnauthorized callback for auto-logout.
 *
 * Note: for JSON body detection, the response is cloned so that callers
 * can still read the original response body normally.
 *
 * @param input  Request URL or Request object
 * @param init   Optional RequestInit configuration
 * @returns      Standard Response object
 */
export async function safeFetch(input: string | URL | Request, init?: RequestInit): Promise<Response> {
  const resp = await fetch(input, init)

  // Check 1: standard HTTP 401
  if (resp.status === 401 && onUnauthorized) {
    onUnauthorized()
    return resp
  }

  // Check 2: JSON body with code === 401 (clone to avoid consuming body)
  if (onUnauthorized && resp.ok) {
    try {
      const cloned = resp.clone()
      const contentType = cloned.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const body = await cloned.json()
        if (body && body.code === 401) {
          onUnauthorized()
        }
      }
    } catch {
      // Ignore JSON parse errors — not all responses are JSON
    }
  }

  return resp
}
