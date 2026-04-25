import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// 后端 API 代理目标地址，支持通过环境变量 VITE_API_TARGET 覆盖。
// 默认 http://127.0.0.1:8080，启用 HTTPS 后可设为 https://127.0.0.1:8080。
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8080'
const misszhaoTarget = process.env.VITE_MISSZHAO_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5174,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api/misszhao': {
        target: misszhaoTarget,
        changeOrigin: true,
        secure: false,
        rewrite: (path: string) => path.replace(/^\/api\/misszhao/, ''),
      },
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false, // 允许代理到自签名 HTTPS 后端
      },
      '/v1': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  // 支持导入 .md 文件为原始字符串
  assetsInclude: ['**/*.md'],
})
