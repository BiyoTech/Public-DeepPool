/**
 * Axios HTTP client with unified Authorization header and error handling.
 * In production, VITE_API_BASE_URL points to the dedicated API domain;
 * in development, requests are proxied via Vite dev server.
 */
import axios from 'axios'
import router from '@/router'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
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
