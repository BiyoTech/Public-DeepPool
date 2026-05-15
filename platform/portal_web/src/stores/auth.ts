/**
 * Pinia 认证状态管理。
 * 管理登录状态、用户信息和 token。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import router from '@/router'

export interface UserInfo {
  id: number
  username: string
  phone: string
  email: string
  role: string
}

const TOKEN_KEY = 'dp_token'
const USER_KEY = 'dp_user'

/** 从 localStorage 恢复用户信息。 */
function loadUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref<UserInfo | null>(loadUser())

  const isLoggedIn = computed(() => !!token.value)

  function setAuth(newToken: string, userInfo: UserInfo) {
    token.value = newToken
    user.value = userInfo
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(userInfo))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    router.push('/login')
  }

  /** Update local user info after profile edit (partial update). */
  function updateUser(partial: Partial<UserInfo>) {
    if (!user.value) return
    user.value = { ...user.value, ...partial }
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
  }

  return { token, user, isLoggedIn, setAuth, logout, updateUser }
})
