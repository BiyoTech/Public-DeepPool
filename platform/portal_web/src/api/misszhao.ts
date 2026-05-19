/**
 * misszhao AI assistant API wrapper.
 *
 * - sendMessage: SSE streaming chat with semantic event support
 * - getChatHistory: get chat history
 * - createNewChat: create new conversation
 * - listWorkspaceFiles: browse workspace files
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

// ── Semantic event types ──

export interface ToolCalledEvent {
  type: 'tool_called'
  tool_name: string
  arguments: string
  call_id: string
}

export interface ToolOutputEvent {
  type: 'tool_output'
  output: string
  call_id: string
}

export interface ReasoningEvent {
  type: 'reasoning'
  content: string
}

export interface HandoffEvent {
  type: 'handoff'
  source_agent: string
  target_agent: string
}

export interface AgentUpdatedEvent {
  type: 'agent_updated'
  agent_name: string
}

export type AgentEvent = ToolCalledEvent | ToolOutputEvent | ReasoningEvent | HandoffEvent | AgentUpdatedEvent

// ── SSE streaming chat ──

export interface StreamCallbacks {
  onContent: (text: string) => void
  onEvent: (event: AgentEvent) => void
  onDone: () => void
  onError: (error: string) => void
}

/** Required LLM config for web channel chat. */
export interface SendMessageOptions {
  model: string
  apiKey: string
}

/**
 * Send SSE streaming chat request with semantic event support.
 *
 * SSE payload types:
 *   - {"content": "..."} — text delta
 *   - {"event": {...}}   — semantic event (tool_called, reasoning, etc.)
 *   - [DONE]             — end marker
 *
 * Returns AbortController for caller to abort the stream.
 */
export function sendMessage(message: string, callbacks: StreamCallbacks, options: SendMessageOptions): AbortController {
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
            // Semantic event
            if (parsed.event) {
              callbacks.onEvent(parsed.event as AgentEvent)
            }
            // Text delta
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

export async function getChatHistory(limit = 50, threadId?: string): Promise<ChatMessage[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  if (threadId) params.set('thread_id', threadId)

  const resp = await fetch(`${MISSZHAO_BASE}/chat/history?${params}`, {
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

// ── Workspace file browsing ──

export interface FileEntry {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified_at: string
  file_type: string // "document" | "image" | "code" | "spreadsheet" | "other"
  children: FileEntry[] | null
}

export interface WorkspaceFilesResponse {
  files: FileEntry[]
  workspace_path: string
}

export async function listWorkspaceFiles(subPath = '', recursive = true): Promise<WorkspaceFilesResponse> {
  const params = new URLSearchParams()
  if (subPath) params.set('path', subPath)
  params.set('recursive', String(recursive))

  const resp = await fetch(`${MISSZHAO_BASE}/workspace/files?${params}`, {
    method: 'GET',
    headers: buildHeaders(),
  })

  if (!resp.ok) {
    throw new Error(`Failed to list workspace files (${resp.status})`)
  }

  return resp.json()
}
