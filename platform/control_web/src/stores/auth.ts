import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as apiLogin } from '@/api/auth'
import type { LoginParams } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('dp_token') || '')
  const user = ref(JSON.parse(localStorage.getItem('dp_user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const username = computed(() => user.value?.username || '')

  async function doLogin(params: LoginParams) {
    const res = await apiLogin(params)
    const data = res.data.data
    token.value = data.token
    user.value = data.user
    localStorage.setItem('dp_token', data.token)
    localStorage.setItem('dp_user', JSON.stringify(data.user))
    return data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('dp_token')
    localStorage.removeItem('dp_user')
    router.push('/login')
  }

  return { token, user, isLoggedIn, isAdmin, username, doLogin, logout }
})
