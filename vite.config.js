import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  root: 'viewer',
  base: '/ecosystems-evaluate/',
  build: {
    outDir: '../docs',
    emptyOutDir: true
  }
})
