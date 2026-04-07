import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * 通过环境变量 BUILD_MODE 区分构建目标：
 *   - 默认 (tauri):     输出到 dist/，供 Tauri 桌面应用使用
 *   - standalone:       输出到 dist-standalone/，嵌入 localserver 独立可执行文件
 *
 * standalone 模式下 base 设为 './'，确保静态资源使用相对路径，
 * 由 FastAPI StaticFiles 中间件同源托管，无跨域问题。
 */
const isStandalone = process.env.BUILD_MODE === 'standalone'

export default defineConfig({
  plugins: [vue()],
  base: isStandalone ? './' : '/',
  build: {
    ...(isStandalone && {
      outDir: 'dist-standalone',
      emptyOutDir: true,
    }),
  },
  server: {
    port: 5174,
    strictPort: true,
    // 代理 localserver 请求，解决 Tauri WebView 中 localhost → 127.0.0.1 的跨域问题
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8765',
        changeOrigin: true,
      },
    },
  },
})
