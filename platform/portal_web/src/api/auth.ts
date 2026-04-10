/**
 * 认证相关 API（登录、注册、邮箱验证码、密码重置）。
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
  email_code: string
}

export interface EmailLoginParams {
  email: string
  code: string
}

export interface SendEmailCodeParams {
  email: string
  purpose: 'login' | 'register' | 'reset_password' | 'change_email'
}

export interface ResetPasswordParams {
  email: string
  code: string
  new_password: string
}

export interface ChangeEmailParams {
  new_email: string
  code: string
}

/** Login with account + password */
export function loginApi(data: LoginParams) {
  return http.post('/users/login', data)
}

/** Login with email + verification code */
export function loginByEmailApi(data: EmailLoginParams) {
  return http.post('/users/login-by-email', data)
}

/** Send email verification code */
export function sendEmailCodeApi(data: SendEmailCodeParams) {
  return http.post('/users/send-email-code', data)
}

/** Reset password using email verification code */
export function resetPasswordApi(data: ResetPasswordParams) {
  return http.post('/users/reset-password', data)
}

/** Change email for logged-in user */
export function changeEmailApi(data: ChangeEmailParams) {
  return http.post('/users/change-email', data)
}

/** User registration */
export function registerApi(data: RegisterParams) {
  return http.post('/users/register', data)
}
