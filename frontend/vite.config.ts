import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Optional same-origin development path: VITE_API_BASE_URL=/.
  // Forward actual requests; never substitute mock responses.
  server: { host: '127.0.0.1', proxy: { '/api': { target: 'http://127.0.0.1:8001', changeOrigin: true } } },
})

