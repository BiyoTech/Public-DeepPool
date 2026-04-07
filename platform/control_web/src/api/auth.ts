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

// 管理员登录（复用用户登录接口）
export function login(params: LoginParams) {
  return http.post('/users/login', params)
}

// 管理员注册
export function adminRegister(params: RegisterParams) {
  return http.post('/admin/register', params)
}
