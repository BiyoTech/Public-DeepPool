/**
 * Axios HTTP 实例封装。
 * 统一添加 Authorization 头和错误处理。
 */
import axios from 'axios'
import router from '@/router'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：自动注入 Bearer Token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('dp_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：401 token expired → clear auth state and redirect to login
http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('dp_token')
      localStorage.removeItem('dp_user')
      // Avoid pushing /login if already on login/register page
      const current = router.currentRoute.value.path
      if (current !== '/login' && current !== '/register') {
        router.push('/login')
      }
    }
    return Promise.reject(err)
  },
)

export default http
