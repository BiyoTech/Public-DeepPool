<template>
  <div class="admin-layout min-h-screen flex bg-dp-bg-1">
    <!-- 左侧菜单 -->
    <aside class="w-56 bg-dp-bg-2 border-r border-white/5 flex flex-col shrink-0">
      <!-- Logo 区域 -->
      <div class="h-16 flex items-center gap-3 px-5 border-b border-white/5">
        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-dp-blue to-dp-blue-active flex items-center justify-center">
          <ServerIcon class="w-5 h-5 text-white" />
        </div>
        <span class="text-lg font-semibold text-dp-text-1">DeepPool</span>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 py-4 px-3 space-y-1">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 group"
          :class="[
            isActive(item.path)
              ? 'bg-dp-blue/10 text-dp-blue border-l-2 border-dp-blue'
              : 'text-dp-text-2 hover:bg-white/5 hover:text-dp-text-1 border-l-2 border-transparent'
          ]"
        >
          <component :is="item.icon" class="w-5 h-5" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
    </aside>

    <!-- 右侧主区域 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部栏 -->
      <header class="h-16 bg-dp-bg-3 border-b border-white/5 flex items-center justify-between px-6 shrink-0">
        <h2 class="text-lg font-medium text-dp-text-1">{{ currentPageTitle }}</h2>
        <div class="flex items-center gap-4">
          <span class="text-sm text-dp-text-2">{{ authStore.username }}</span>
          <t-button variant="text" size="small" @click="authStore.logout()" class="!text-dp-text-3 hover:!text-dp-red">
            <template #icon><LogoutIcon /></template>
            退出
          </t-button>
        </div>
      </header>

      <!-- 内容区 -->
      <main class="flex-1 p-6 overflow-auto">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  ServerIcon,
  DashboardIcon,
  DeviceIcon,
  UserIcon,
  CpuIcon,
  ChatIcon,
  LogoutIcon,
  LayersIcon,
} from 'tdesign-icons-vue-next'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const authStore = useAuthStore()

const menuItems = [
  { path: '/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { path: '/nodes', label: '在线设备', icon: CpuIcon },
  { path: '/users', label: '用户管理', icon: UserIcon },
  { path: '/devices', label: '设备管理', icon: DeviceIcon },
  { path: '/models', label: '模型管理', icon: LayersIcon },
  { path: '/chat', label: 'Chat 调试', icon: ChatIcon },
]

const currentPageTitle = computed(() => {
  const item = menuItems.find((m) => route.path.startsWith(m.path))
  return item?.label || 'DeepPool 管控平台'
})

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>
