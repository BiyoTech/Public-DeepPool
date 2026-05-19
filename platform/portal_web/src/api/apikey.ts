/**
 * API Key management endpoints.
 */
import http from './http'

export interface APIKey {
  id: number
  name: string
  key_prefix: string
  status: string
  rate_limit_rpm: number
  rate_limit_tpm: number
  quota_total: number // -1 means unlimited
  quota_used: number
  last_used_at: string | null
  created_at: string
}

export interface APIKeyCreated extends APIKey {
  full_key: string
}

export interface CreateAPIKeyParams {
  name: string
  rate_limit_rpm?: number // 0 = unlimited
  rate_limit_tpm?: number // 0 = unlimited
}

export interface UpdateAPIKeyParams {
  name?: string
  rate_limit_rpm?: number // 0 = unlimited
  rate_limit_tpm?: number // 0 = unlimited
  quota_total?: number // -1 = unlimited
}

/** Create an API Key */
export function createAPIKey(params: CreateAPIKeyParams | string) {
  const body = typeof params === 'string' ? { name: params } : params
  return http.post<{ code: number; data: APIKeyCreated }>('/apikeys', body)
}

/** Update API Key rate-limit settings */
export function updateAPIKey(id: number, params: UpdateAPIKeyParams) {
  return http.patch<{ code: number }>(`/apikeys/${id}`, params)
}

/** List API Keys */
export function listAPIKeys() {
  return http.get<{ code: number; data: APIKey[] }>('/apikeys')
}

/** Delete an API Key */
export function deleteAPIKey(id: number) {
  return http.delete(`/apikeys/${id}`)
}

/** Retrieve the full (decrypted) API Key from server */
export function fetchKeySecret(id: number) {
  return http.get<{ code: number; data: { full_key: string } }>(`/apikeys/${id}/secret`)
}
