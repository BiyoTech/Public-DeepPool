<template>
  <div class="login-page min-h-screen flex items-center justify-center bg-dp-bg-1 relative overflow-hidden">
    <!-- 背景装饰 -->
    <div class="absolute inset-0 bg-gradient-to-br from-dp-bg-1 via-dp-bg-3 to-dp-bg-1"></div>
    <div class="absolute top-1/4 left-1/4 w-96 h-96 bg-dp-blue/5 rounded-full blur-3xl"></div>
    <div class="absolute bottom-1/4 right-1/4 w-80 h-80 bg-dp-blue/3 rounded-full blur-3xl"></div>

    <div class="relative z-10 flex items-center gap-20 max-w-5xl w-full px-8">
      <!-- 左侧品牌区域 -->
      <div class="hidden lg:flex flex-col gap-6 flex-1">
        <div class="flex items-center gap-3">
          <DeepPoolLogo :size="48" />
          <span class="text-3xl font-bold text-dp-text-1">DeepPool</span>
        </div>
        <h2 class="text-xl text-dp-text-2 leading-relaxed">分布式 LLM 推理算力池<br />管控平台</h2>
        <p class="text-dp-text-3 text-sm leading-relaxed max-w-sm">
          统一管理所有 NodeManager 节点与在线设备，监控平台运行状态，调试 OpenAI 兼容推理接口。
        </p>
      </div>

      <!-- 登录卡片 -->
      <div class="w-full max-w-md backdrop-blur-xl bg-dp-bg-3/80 rounded-2xl p-8 border border-white/5 shadow-2xl">
        <h1 class="text-2xl font-semibold text-dp-text-1 mb-2">管理员登录</h1>
        <p class="text-dp-text-3 text-sm mb-8">请使用管理员账号登录管控平台</p>

        <t-form ref="formRef" :data="formData" :rules="rules" @submit="handleLogin" label-width="0">
          <t-form-item name="account">
            <t-input
              v-model="formData.account"
              placeholder="用户名 / 手机号 / 邮箱"
              size="large"
              clearable
              :prefix-icon="UserCircleIcon"
            />
          </t-form-item>
          <t-form-item name="password">
            <t-input
              v-model="formData.password"
              type="password"
              placeholder="密码"
              size="large"
              :prefix-icon="LockOnIcon"
              @keyup.enter="handleLogin"
            />
          </t-form-item>
          <t-form-item>
            <t-button
              theme="primary"
              type="submit"
              block
              size="large"
              :loading="loading"
              class="!bg-gradient-to-r !from-dp-blue !to-dp-blue-active hover:!shadow-lg hover:!shadow-dp-blue/20 !border-none !rounded-lg !h-12"
            >
              登 录
            </t-button>
          </t-form-item>
        </t-form>

        <p v-if="errorMsg" class="text-dp-red text-sm mt-2 text-center">{{ errorMsg }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ServerIcon, UserCircleIcon, LockOnIcon } from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const errorMsg = ref('')

const formData = reactive({
  account: '',
  password: '',
})

const rules = {
  account: [{ required: true, message: '请输入账号' }],
  password: [{ required: true, message: '请输入密码' }],
}

async function handleLogin() {
  loading.value = true
  errorMsg.value = ''
  const data = await authStore.doLogin(formData).catch((err: any) => {
    errorMsg.value = err.response?.data?.message || '登录失败，请检查账号密码'
    return null
  })
  loading.value = false
  if (data) {
    if (data.user?.role !== 'admin') {
      errorMsg.value = '该账号不是管理员，无权访问管控平台'
      authStore.logout()
      return
    }
    router.push('/dashboard')
  }
}
</script>
