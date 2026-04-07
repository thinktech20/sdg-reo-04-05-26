import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import path from 'path'

// API target: when running in Docker compose the env var is injected by the
// frontend container; when running outside Docker it falls back to localhost.
const API_TARGET = process.env.VITE_DATA_SERVICE_URL ?? 'http://localhost:8086'

// QnA agent target for chat REST API.
const QNA_TARGET = process.env.VITE_QNA_AGENT_URL ?? 'http://localhost:8087'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 4000,
    host: '0.0.0.0', // listen on all interfaces so Docker port-forward works
    open: false,     // don't auto-open browser inside container
    proxy: {
      // QnA agent — REST chat. The router is mounted at /questionansweragent/api/v1
      // inside the agent process, so forward the full path without rewriting.
      // (Mirrors the nginx `location /questionansweragent/` passthrough in Docker.)
      '/questionansweragent': {
        target: QNA_TARGET,
        changeOrigin: true,
        secure: false,
      },
      // Data service — /api/* is rewritten to /dataservices/api/v1/* to match
      // the canonical backend route prefix (mirrors the nginx rewrite in Docker).
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/api/, '/dataservices/api/v1'),
      },
      // Passthrough for any direct /dataservices/* calls (backwards compat).
      '/dataservices': {
        target: API_TARGET,
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
