/**
 * 银行卡 API：查询、绑定、删除。
 */
import http from './http'

/** 银行卡列表 */
export function listBankCards() {
  return http.get('/bank-cards')
}

/** 绑定银行卡 */
export function createBankCard(data: { bank_name: string; card_number: string; card_holder: string }) {
  return http.post('/bank-cards', data)
}

/** 删除银行卡 */
export function deleteBankCard(id: number) {
  return http.delete(`/bank-cards/${id}`)
}
