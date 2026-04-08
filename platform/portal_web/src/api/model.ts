/**
 * Public model API (no auth required).
 */
import http from './http'

export interface PricingTier {
  max_input_tokens: number
  input_price: number
  output_price: number
}

export interface PublicModel {
  model_name: string
  max_context_length: number
  param_scale: number
  pricing_tiers: PricingTier[]
  contributor_tiers: PricingTier[]
}

/** Fetch enabled models with pricing tiers (public, no auth) */
export function getPublicModels() {
  return http.get<{ code: number; data: PublicModel[] }>('/public/models')
}
