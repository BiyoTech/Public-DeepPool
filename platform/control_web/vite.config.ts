import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 部署子路径，通过环境变量 VITE_BASE 控制。
// 开发环境默认 '/'，生产部署到 /admin/ 时设为 '/admin/'。
const base = process.env.VITE_BASE || '/'

// 后端 API 代理目标地址，支持通过环境变量覆盖。
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8080'

export default defineConfig({
  base,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/v1': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
