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
  storage_type: 'builtin' | 'external'
  db_type?: string
  db_host?: string
  db_port?: number
  db_user?: string
  db_password?: string
  db_name?: string
}

/** Params for updating an existing trace config */
export type UpdateTraceParams = CreateTraceParams

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
  logs: TraceLogItem[]
  has_more: boolean
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

/** Get available storage engine options (whether builtin engine is configured) */
export function getTraceStorageOptions() {
  return http.get<{ code: number; data: { builtin_available: boolean } }>('/traces/storage-options')
}

// --- Annotation types ---

export interface FeedbackItem {
  name: string
  passed: boolean
  reason: string
  source: 'human' | 'ai_judge'
}

export interface ExpectationItem {
  name: string
  data_type: 'text' | 'number' | 'bool' | 'json'
  content: string
  reason: string
}

export interface TraceAnnotation {
  id?: number
  trace_id: number
  log_id: number
  feedbacks: FeedbackItem[]
  expectation: ExpectationItem | null
  created_at?: string
  updated_at?: string
}

// --- Annotation API calls ---

/** Get annotation (feedbacks + expectation) for a trace log */
export function getAnnotation(traceId: number, logId: number) {
  return http.get<{ code: number; data: TraceAnnotation | null }>(
    `/experiment/traces/${traceId}/logs/${logId}/annotation`,
  )
}

/** Save (create or update) annotation for a trace log */
export function saveAnnotation(
  traceId: number,
  logId: number,
  data: {
    feedbacks: FeedbackItem[]
    expectation: ExpectationItem | null
  },
) {
  return http.put<{ code: number; data: TraceAnnotation }>(
    `/experiment/traces/${traceId}/logs/${logId}/annotation`,
    data,
  )
}

// --- Annotation summary for list view ---

export interface AnnotationSummary {
  log_id: number
  has_feedback: boolean
  feedback_passed: boolean
  feedback_count: number
  has_expectation: boolean
}

/** Batch get annotation summaries for multiple log IDs */
export function batchGetAnnotationSummaries(traceId: number, logIds: number[]) {
  return http.post<{ code: number; data: Record<string, AnnotationSummary> | null }>(
    `/experiment/traces/${traceId}/annotation-summaries`,
    { log_ids: logIds },
  )
}

// --- Judge types ---

export interface BuiltinScorer {
  name: string
  display_name: string
  description: string
  prompt_template: string
}

export interface CreateJudgeParams {
  name: string
  scope: 'model' | 'apikey' | 'trace' | 'trace_log'
  scope_value: string
  trace_id: number
  judge_model: string
  judge_apikey_id: number
  scorer_type: 'builtin' | 'custom'
  scorer_name: string
  prompt_template: string
}

export interface JudgeDTO {
  id: number
  user_id: number
  name: string
  scope: string
  scope_value: string
  trace_id: number
  judge_model: string
  judge_apikey_id: number
  scorer_type: string
  scorer_name: string
  prompt_template: string
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  created_at: string
  updated_at: string
}

export interface JudgeResultDTO {
  id: number
  run_id: number
  judge_id: number
  trace_log_id: number
  request_id: string
  passed: boolean
  reason: string
  raw_output: string
  duration_ms: number
  success: boolean
  error_message: string
  created_at: string
}

/** Judge run: each execution of a judge task */
export interface JudgeRunDTO {
  id: number
  judge_id: number
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  pass_rate: number
  created_at: string
  updated_at: string
}

/** Partial update params for a judge task */
export interface UpdateJudgeParams {
  name?: string
  scope?: string
  scope_value?: string
  trace_id?: number
  judge_model?: string
  judge_apikey_id?: number
  scorer_type?: string
  scorer_name?: string
  prompt_template?: string
}

// --- Judge API calls ---

/** List all builtin scorers (pass lang for i18n: "en", "zh", etc.) */
export function listBuiltinScorers(lang?: string) {
  return http.get<{ code: number; data: BuiltinScorer[] }>('/experiment/scorers', {
    params: lang ? { lang } : undefined,
  })
}

/** Create a new judge task */
export function createJudge(params: CreateJudgeParams) {
  return http.post<{ code: number; data: JudgeDTO }>('/experiment/judges', params)
}

/** List all judges for the current user */
export function listJudges() {
  return http.get<{ code: number; data: JudgeDTO[] }>('/experiment/judges')
}

/** Get judge detail by ID */
export function getJudge(id: number) {
  return http.get<{ code: number; data: JudgeDTO }>(`/experiment/judges/${id}`)
}

/** Run a judge task (creates a new run) */
export function runJudge(id: number) {
  return http.post<{ code: number; data: JudgeRunDTO }>(`/experiment/judges/${id}/run`, {})
}

/** Update a judge task config */
export function updateJudge(id: number, params: UpdateJudgeParams) {
  return http.put<{ code: number; data: JudgeDTO }>(`/experiment/judges/${id}`, params)
}

/** List all runs for a judge task */
export function listJudgeRuns(judgeId: number) {
  return http.get<{ code: number; data: JudgeRunDTO[] }>(`/experiment/judges/${judgeId}/runs`)
}

/** Get results for a specific judge run */
export function getJudgeRunResults(judgeId: number, runId: number, page = 1, pageSize = 30) {
  return http.get<{ code: number; data: { items: JudgeResultDTO[]; has_more: boolean } }>(
    `/experiment/judges/${judgeId}/runs/${runId}/results`,
    { params: { page, page_size: pageSize } },
  )
}

/** Get judge results (deprecated: use getJudgeRunResults) */
export function getJudgeResults(id: number, page = 1, pageSize = 30) {
  return http.get<{ code: number; data: { items: JudgeResultDTO[]; has_more: boolean } }>(
    `/experiment/judges/${id}/results`,
    { params: { page, page_size: pageSize } },
  )
}

/** Delete a judge task */
export function deleteJudge(id: number) {
  return http.delete<{ code: number }>(`/experiment/judges/${id}`)
}
