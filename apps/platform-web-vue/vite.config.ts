import { resolve } from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import checker from 'vite-plugin-checker'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_DEV_PORT || 3000)
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:2024'

  return {
    plugins: [
      vue(),
      checker({
        typescript: true,
        vueTsc: true
      })
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        'vue-i18n': 'vue-i18n/dist/vue-i18n.runtime.esm-bundler.js'
      }
    },
    define: {
      __INTLIFY_JIT_COMPILATION__: true
    },
    server: {
      host: '0.0.0.0',
      port: devPort,
      strictPort: true,
      proxy: {
        '/_management': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/api/langgraph': {
          target: proxyTarget,
          changeOrigin: true
        }
      }
    }
  }
})
