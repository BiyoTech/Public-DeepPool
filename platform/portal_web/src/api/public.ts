/**
 * 公开 API（无需鉴权）。
 */
import http from './http'

/** 获取平台公开统计数据 */
export function getPublicStats() {
  return http.get('/public/stats')
}
