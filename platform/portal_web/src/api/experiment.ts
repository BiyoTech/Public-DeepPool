/**
 * Experiment trace API endpoints.
 */
import http from './http'

// --- Types ---

export interface TraceConfig {
  id: number
  user_id: number
  name: string
  api_key_ids: number[]
  model_names: string[]
  storage_type: string
  db_type: string
  dsn_masked: string
  db_host: string
  db_port: number
  db_user: string
  db_name: string
  status: string
  created_at: string
  updated_at: string
}

export interface CreateTraceParams {
  name: string
  api_key_ids: number[]
  model_names: string[]
  storage_type: string
  db_type: string
  db_host: string
  db_port: number
  db_user: string
  db_password: string
  db_name: string
}

export interface TestConnectionParams {
  db_type: string
  db_host: string
  db_port: number
  db_user: string
  db_password: string
  db_name: string
}

/** Lightweight trace log item (list view — no request/response body) */
export interface TraceLogItem {
  id: number
  request_id: string
  api_key_id: number
  user_id: number
  model_name: string
  user_query: string
  is_stream: boolean
  first_token_ms: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  reasoning_tokens: number
  duration_ms: number
  success: boolean
  error_message: string
  created_at: string
}

/** Full trace log detail with request/response body */
export interface TraceLogDetail extends TraceLogItem {
  request_body: string
  response_body: string
}

export interface TraceLogsResponse {
  total: number
  logs: TraceLogItem[]
}

export interface TraceLogQueryParams {
  model_name?: string
  api_key_id?: number
  request_id?: string
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}

// --- API calls ---

/** Create a new trace config */
export function createTrace(params: CreateTraceParams) {
  return http.post<{ code: number; data: TraceConfig }>('/traces', params)
}

/** List all trace configs for the current user */
export function listTraces() {
  return http.get<{ code: number; data: TraceConfig[] }>('/traces')
}

/** Update trace status (start/stop) */
export function updateTraceStatus(id: number, status: string) {
  return http.patch<{ code: number }>(`/traces/${id}`, { status })
}

/** Update (edit) a trace config (only allowed when stopped) */
export function updateTrace(id: number, params: UpdateTraceParams) {
  return http.put<{ code: number; data: TraceConfig }>(`/traces/${id}`, params)
}

/** Delete a trace config */
export function deleteTrace(id: number) {
  return http.delete<{ code: number }>(`/traces/${id}`)
}

/** Test external database connection (longer timeout for remote DB handshake) */
export function testDBConnection(params: TestConnectionParams) {
  return http.post<{ code: number; message: string }>('/traces/test-connection', params, {
    timeout: 60000,
  })
}

/** Query paginated trace logs from external database */
export function getTraceLogs(traceId: number, params: TraceLogQueryParams) {
  return http.get<{ code: number; data: TraceLogsResponse }>(`/traces/${traceId}/logs`, { params })
}

/** Get single trace log detail with full request/response body */
export function getTraceLogDetail(traceId: number, logId: number) {
  return http.get<{ code: number; data: TraceLogDetail }>(`/traces/${traceId}/logs/${logId}`)
}
