import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 仅开发期使用：生产/容器为单端口模式，前端产物由后端在 3000 端口一并托管
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  resolve: {
    alias: { '@': '/src' },
  },
})
