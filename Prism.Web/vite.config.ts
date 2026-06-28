import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Load Aspire variables (they are injected as system env vars)
  const env = loadEnv(mode, process.cwd(), '');
  
  // Aspire provides the service URL here
  const target = env.services__apiservice__https__0 || env.services__apiservice__http__0;

  return {
    plugins: [react()],
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
        '/rfp': {
          target: target,
          changeOrigin: true,
          secure: false
        }
      }
    }
  }
})
