import axios from 'axios'
import router from '@/router'

// axios 实例，统一 baseURL 和拦截器
const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动附带 Authorization
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('dp_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 token expired → clear auth state and redirect to login
http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('dp_token')
      localStorage.removeItem('dp_user')
      // Avoid duplicate navigation if already on login page
      const current = router.currentRoute.value.path
      if (current !== '/login') {
        router.push('/login')
      }
    }
    return Promise.reject(err)
  },
)

export default http
