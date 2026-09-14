import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  // Load Aspire variables (they are injected as system env vars)
  const env = loadEnv(mode, process.cwd(), '');

  // Aspire provides the service URL here; standalone builds/preview (no Aspire orchestrator)
  // fall back to VITE_API_BASE_URL, then to the local Aspire default port.
  const target =
    env.services__apiservice__https__0 ||
    env.services__apiservice__http__0 ||
    env.VITE_API_BASE_URL ||
    'http://localhost:7217';

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      // signalRService connects directly to the API origin (browser-to-backend,
      // per AppHost.cs's WithExternalHttpEndpoints comment) rather than through
      // the /api proxy below, so it needs the same resolved `target` as that
      // proxy - otherwise import.meta.env.VITE_API_BASE_URL is undefined in any
      // dev run that doesn't set it explicitly (Aspire F5 only injects the
      // services__apiservice__* vars, not VITE_API_BASE_URL itself), producing
      // a hub URL of "undefined/hubs/document".
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(target),
    },
    server: {
      port: parseInt(env.VITE_PORT) || 5173, 
      strictPort: true,
      proxy: {
        // Chat Requests
        '/api': {
          target: target,
          changeOrigin: true,
          secure: false,
          // Removed rewrite unless your backend doesn't have /api in the route
        },
        // File Uploads
        '/api/papers': {
          target: target,
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
