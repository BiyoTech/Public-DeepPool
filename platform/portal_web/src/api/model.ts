/**
 * Public model API (no auth required).
 */
import http from './http'

export interface PricingTier {
  max_input_tokens: number
  input_price: number
  output_price: number
}

/** Price range computed from hybrid model's child models. */
export interface PriceRange {
  min_input_price: number
  max_input_price: number
  min_output_price: number
  max_output_price: number
  child_models: string[]
}

export interface PublicModel {
  model_name: string
  vendor_type: string
  max_context_length: number
  param_scale: number
  pricing_tiers: PricingTier[]
  contributor_tiers: PricingTier[]
  price_range?: PriceRange // hybrid models only
  tags?: string[]
}

/** Fetch enabled models with pricing tiers (public, no auth) */
export function getPublicModels() {
  return http.get<{ code: number; data: PublicModel[] }>('/public/models')
}
