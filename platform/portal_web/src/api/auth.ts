/**
 * 认证相关 API（登录、注册）。
 */
import http from './http'

export interface LoginParams {
  account: string
  password: string
}

export interface RegisterParams {
  username: string
  password: string
  phone: string
  email: string
}

/** 用户登录 */
export function loginApi(data: LoginParams) {
  return http.post('/users/login', data)
}

/** 用户注册 */
export function registerApi(data: RegisterParams) {
  return http.post('/users/register', data)
}
