/**
 * 用户维度 Token 用量查询 API。
 */
import http from './http'

/** 设备贡献明细 */
export function getContribution(params?: Record<string, string>) {
  return http.get('/usage/contribution', { params })
}

/** API Key 消耗明细（按 API Key × 模型 × 天维度） */
export function getConsumption(params?: Record<string, string>) {
  return http.get('/usage/consumption', { params })
}

/** 用量汇总 */
export function getUsageSummary() {
  return http.get('/usage/summary')
}
