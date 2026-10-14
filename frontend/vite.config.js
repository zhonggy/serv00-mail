import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base: './' —— build 产物可直接丢进 serv00 的 public_html，
// 用相对路径引用资源，无需配置子路径或 rewrite 规则。
export default defineConfig({
  plugins: [vue()],
  base: './',
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
