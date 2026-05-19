import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'nodes', name: 'Nodes', component: () => import('@/views/NodesView.vue') },
      { path: 'users', name: 'Users', component: () => import('@/views/UsersView.vue') },
      { path: 'devices', name: 'Devices', component: () => import('@/views/DevicesView.vue') },
      { path: 'models', name: 'Models', component: () => import('@/views/ModelsView.vue') },
      { path: 'endpoints', name: 'Endpoints', component: () => import('@/views/EndpointsView.vue') },
      {
        path: 'consumer-operations',
        name: 'ConsumerOperations',
        component: () => import('@/views/ConsumerOperationView.vue'),
      },
      { path: 'chat', name: 'Chat', component: () => import('@/views/ChatView.vue') },
    ],
  },
]

const router = createRouter({
  // import.meta.env.BASE_URL 由 vite.config.ts 的 base 决定，
  // 本地开发为 '/'，生产部署为 '/admin/'。
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

// 路由守卫：未登录跳转登录页，非 admin 角色拒绝访问
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('dp_token')
  const user = JSON.parse(localStorage.getItem('dp_user') || 'null')

  if (to.meta.requiresAuth) {
    if (!token) {
      next('/login')
      return
    }
    if (user?.role !== 'admin') {
      next('/login')
      return
    }
  }

  // 已登录访问登录页 → 跳转首页
  if (to.path === '/login' && token && user?.role === 'admin') {
    next('/dashboard')
    return
  }

  next()
})

export default router
