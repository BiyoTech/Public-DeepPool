/**
 * User custom model API (hybrid + provider).
 */
import http from './http'

export interface CustomModel {
  id: number
  user_id: number
  model_name: string
  display_name: string
  vendor_type: 'hybrid' | 'provider'
  // hybrid fields
  child_models: string[]
  routing_policy: string
  // provider fields
  model_family: string
  endpoint: string
  upstream_model: string
  api_key: string // masked in responses ("••••••")
  supports_reasoning: boolean
  supports_vision: boolean
  supports_function_call: boolean
  tags: string[]
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CreateCustomModelReq {
  display_name: string
  vendor_type: 'hybrid' | 'provider'
  // hybrid
  child_models?: string[]
  routing_policy?: string
  // provider
  model_family?: string
  endpoint?: string
  upstream_model?: string
  api_key?: string
  supports_reasoning?: boolean
  supports_vision?: boolean
  supports_function_call?: boolean
  tags?: string[]
}

export interface UpdateCustomModelReq {
  // hybrid
  child_models?: string[]
  routing_policy?: string
  // provider
  model_family?: string
  endpoint?: string
  upstream_model?: string
  api_key?: string
  supports_reasoning?: boolean
  supports_vision?: boolean
  supports_function_call?: boolean
  tags?: string[]
  enabled?: boolean
}

/** List current user's custom models */
export function listCustomModels() {
  return http.get<{ code: number; data: CustomModel[] }>('/custom-models')
}

/** Create a custom model (hybrid or provider) */
export function createCustomModel(data: CreateCustomModelReq) {
  return http.post<{ code: number; data: CustomModel }>('/custom-models', data)
}

/** Update a custom model */
export function updateCustomModel(id: number, data: UpdateCustomModelReq) {
  return http.put<{ code: number }>(`/custom-models/${id}`, data)
}

/** Delete a custom model */
export function deleteCustomModel(id: number) {
  return http.delete<{ code: number }>(`/custom-models/${id}`)
}
