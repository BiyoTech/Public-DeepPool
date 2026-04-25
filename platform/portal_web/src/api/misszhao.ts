/**
 * misszhao AI assistant API wrapper.
 *
 * - sendMessage: SSE streaming chat (fetch + ReadableStream, supports custom headers)
 * - getChatHistory: get chat history
 * - createNewChat: create new conversation
 */

const MISSZHAO_BASE = import.meta.env.VITE_MISSZHAO_API_URL || '/api/misszhao'

/** Get auth token */
function getToken(): string {
  return localStorage.getItem('dp_token') || ''
}

/** Build common request headers */
function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${getToken()}`,
    ...extra,
  }
}

// ── Chat history types ──

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

// ── SSE streaming chat ──

export interface StreamCallbacks {
  onContent: (text: string) => void
  onDone: () => void
  onError: (error: string) => void
}

/** Required LLM config for web channel chat. */
export interface SendMessageOptions {
  model: string
  apiKey: string
}

/**
 * Send SSE streaming chat request.
 *
 * Uses fetch + ReadableStream (not EventSource) because EventSource does not support custom headers.
 * Returns AbortController for caller to abort the stream.
 */
export function sendMessage(
  message: string,
  callbacks: StreamCallbacks,
  options: SendMessageOptions,
): AbortController {
  const controller = new AbortController()

  const body = {
    message,
    model: options.model,
    api_key: options.apiKey,
  }

  ;(async () => {
    try {
      const resp = await fetch(`${MISSZHAO_BASE}/chat/completions`, {
        method: 'POST',
        headers: buildHeaders(),
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!resp.ok) {
        if (resp.status === 401) {
          callbacks.onError('Authentication failed, please log in again')
          return
        }
        callbacks.onError(`Request failed (${resp.status})`)
        return
      }

      const reader = resp.body?.getReader()
      if (!reader) {
        callbacks.onError('Cannot read response stream')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue

          const payload = trimmed.slice(6)
          if (payload === '[DONE]') {
            callbacks.onDone()
            return
          }

          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) {
              callbacks.onError(parsed.error)
              return
            }
            if (parsed.content) {
              callbacks.onContent(parsed.content)
            }
          } catch {
            // Ignore non-JSON lines
          }
        }
      }

      // Stream ended normally without [DONE]
      callbacks.onDone()
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        callbacks.onDone()
        return
      }
      callbacks.onError((err as Error).message || 'Network request failed')
    }
  })()

  return controller
}

// ── Chat history ──

export async function getChatHistory(limit = 50): Promise<ChatMessage[]> {
  const resp = await fetch(`${MISSZHAO_BASE}/chat/history?limit=${limit}`, {
    method: 'GET',
    headers: buildHeaders(),
  })

  if (!resp.ok) {
    throw new Error(`Failed to get chat history (${resp.status})`)
  }

  const data = await resp.json()
  return data.messages || data || []
}

// ── New conversation ──

export interface NewChatResult {
  thread_id: string
}

export async function createNewChat(): Promise<NewChatResult> {
  const resp = await fetch(`${MISSZHAO_BASE}/chat/new`, {
    method: 'POST',
    headers: buildHeaders(),
  })

  if (!resp.ok) {
    throw new Error(`Failed to create new chat (${resp.status})`)
  }

  return resp.json()
}
