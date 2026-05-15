/**
 * Guardrail management API client: CRUD operations, template listing, and evaluation results.
 */
import http from './http'

// --- Types ---

export interface GuardrailTemplate {
  name: string
  display_name: string
  description: string
  phase: string        // input / output / both
  prompt_template: string
}

export interface Guardrail {
  id: number
  api_key_id: number
  name: string
  phase: string        // input / output
  action: string       // block / log
  prompt: string
  evaluator_model: string
  evaluator_api_key_id: number
  storage_type: string // builtin / external
  db_type: string
  db_host: string
  db_port: number
  db_user: string
  db_name: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CreateGuardrailParams {
  name: string
  phase: string
  action: string
  prompt: string
  evaluator_model: string
  evaluator_api_key_id: number
  storage_type: string
  db_type?: string
  db_host?: string
  db_port?: number
  db_user?: string
  db_password?: string
  db_name?: string
}

export interface UpdateGuardrailParams {
  name?: string
  phase?: string
  action?: string
  prompt?: string
  evaluator_model?: string
  evaluator_api_key_id?: number
  enabled?: boolean
  storage_type?: string
  db_type?: string
  db_host?: string
  db_port?: number
  db_user?: string
  db_password?: string
  db_name?: string
}

export interface GuardrailResult {
  id: number
  guardrail_id: number
  api_key_id: number
  request_id: string
  phase: string
  action: string
  flagged: boolean
  confidence: number
  evaluator_response: string
  blocked: boolean
  duration_ms: number
  error_message: string
  created_at: string
}

export interface GuardrailResultsResponse {
  has_more: boolean
  results: GuardrailResult[]
}

// --- API calls ---

/** List built-in guardrail templates (pass lang for i18n, e.g. "en" or "zh") */
export function listGuardrailTemplates(lang?: string) {
  const params = lang ? { lang } : {}
  return http.get<{ code: number; data: GuardrailTemplate[] }>('/guardrail-templates', { params })
}

/** Create a guardrail rule for the given API Key */
export function createGuardrail(apiKeyId: number, params: CreateGuardrailParams) {
  return http.post<{ code: number; data: Guardrail }>(`/guardrails/${apiKeyId}`, params)
}

/** List all guardrail rules for the given API Key */
export function listGuardrails(apiKeyId: number) {
  return http.get<{ code: number; data: Guardrail[] }>(`/guardrails/${apiKeyId}`)
}

/** Update a guardrail rule */
export function updateGuardrail(apiKeyId: number, guardrailId: number, params: UpdateGuardrailParams) {
  return http.patch<{ code: number }>(`/guardrails/${apiKeyId}/${guardrailId}`, params)
}

/** Delete a guardrail rule */
export function deleteGuardrail(apiKeyId: number, guardrailId: number) {
  return http.delete(`/guardrails/${apiKeyId}/${guardrailId}`)
}

/** List evaluation results for the given API Key (scroll-based pagination) */
export function listGuardrailResults(apiKeyId: number, params?: {
  guardrail_id?: number
  request_id?: string
  flagged?: boolean
  start_time?: string
  end_time?: string
  page?: number
  page_size?: number
}) {
  return http.get<{ code: number; data: GuardrailResultsResponse }>(`/guardrails/${apiKeyId}/results`, { params })
}
