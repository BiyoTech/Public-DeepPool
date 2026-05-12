/**
 * 路由配置：首页 / 文档 / 服务 / 登录 / 注册。
 */
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      component: () => import('@/layouts/PortalLayout.vue'),
      children: [
        {
          path: '',
          name: 'Home',
          component: () => import('@/views/HomeView.vue'),
        },
        {
          path: 'docs/:pathMatch(.*)*',
          name: 'Docs',
          component: () => import('@/views/DocsView.vue'),
        },
        {
          path: 'models',
          name: 'Models',
          component: () => import('@/views/ModelsView.vue'),
        },
        {
          path: 'service',
          name: 'Service',
          meta: { requiresAuth: true },
          component: () => import('@/views/ServiceView.vue'),
        },
        {
          path: 'data',
          name: 'Data',
          meta: { requiresAuth: true },
          component: () => import('@/views/DataView.vue'),
        },
        {
          path: 'misszhao',
          name: 'MissZhao',
          meta: { requiresAuth: true },
          component: () => import('@/views/MissZhaoView.vue'),
        },
        {
          path: 'wallet/recharge',
          name: 'Recharge',
          meta: { requiresAuth: true },
          component: () => import('@/views/wallet/RechargeView.vue'),
        },
        {
          path: 'wallet/withdraw',
          name: 'Withdraw',
          meta: { requiresAuth: true },
          component: () => import('@/views/wallet/WithdrawView.vue'),
        },
        {
          path: 'wallet/bank-cards',
          name: 'BankCards',
          meta: { requiresAuth: true },
          component: () => import('@/views/wallet/BankCardsView.vue'),
        },
        // --- Experiment module (with sub-layout) ---
        {
          path: 'experiment',
          meta: { requiresAuth: true },
          component: () => import('@/views/experiment/ExperimentLayout.vue'),
          children: [
            { path: '', redirect: '/experiment/trace' },
            { path: 'overview', name: 'ExperimentOverview', component: () => import('@/views/experiment/OverviewView.vue') },
            { path: 'trace', name: 'ExperimentTrace', component: () => import('@/views/experiment/TraceView.vue') },
            { path: 'trace/:traceId/logs', name: 'ExperimentTraceLogs', component: () => import('@/views/experiment/TraceLogsView.vue'), props: true },
            { path: 'judge', name: 'ExperimentJudge', component: () => import('@/views/experiment/JudgeView.vue') },
            { path: 'evaluate', name: 'ExperimentEvaluate', component: () => import('@/views/experiment/EvaluateView.vue') },
          ],
        },
      ],
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/register',
      name: 'Register',
      component: () => import('@/views/RegisterView.vue'),
    },
    {
      path: '/forgot-password',
      name: 'ForgotPassword',
      component: () => import('@/views/ForgotPasswordView.vue'),
    },
  ],
})

// Route guard: redirect to /login when accessing auth-required pages without token
router.beforeEach((to, _from, next) => {
  if (to.meta.requiresAuth) {
    const token = localStorage.getItem('dp_token')
    if (!token) {
      next('/login')
      return
    }
  }
  next()
})

export default router
