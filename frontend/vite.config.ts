import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('monaco') || id.includes('@monaco-editor')) return 'monaco'
            if (id.includes('plotly')) return 'plotly'
            if (id.includes('3dmol')) return '3dmol'
            if (id.includes('reactflow') || id.includes('@reactflow') || id.includes('d3-') || id.includes('zustand')) return 'reactflow'
            return 'vendor'
          }
        },
      },
    },
  },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000', '/docs': 'http://127.0.0.1:8000', '/openapi.json': 'http://127.0.0.1:8000' } },
})
