/**
 * 钱包 API：余额查询、充值、提现、交易流水。
 */
import http from './http'

/** 获取钱包概览 */
export function getWallet() {
  return http.get('/wallet')
}

/** 充值 */
export function recharge(amount: number) {
  return http.post('/wallet/recharge', { amount })
}

/** 提现 */
export function withdraw(amount: number, bankCardId: number) {
  return http.post('/wallet/withdraw', { amount, bank_card_id: bankCardId })
}

/** 交易流水 */
export function getTransactions(params?: Record<string, string>) {
  return http.get('/wallet/transactions', { params })
}
