/**
 * Payment API: create payment order, query order status.
 */
import http from './http'

/** Create a payment order (returns order with QR code URL) */
export function createPaymentOrder(amount: number, channel: string) {
  return http.post('/payment/orders', { amount, channel })
}

/** Query payment order status */
export function getPaymentOrder(orderNo: string) {
  return http.get(`/payment/orders/${orderNo}`)
}
