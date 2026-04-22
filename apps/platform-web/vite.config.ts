import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import checker from 'vite-plugin-checker'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devPort = Number(env.VITE_DEV_PORT || 3000)
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://localhost:2142'
  const workspaceRoot = resolve(__dirname, '../..')
  const packageJson = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8')) as {
    version?: string
  }
  const appVersion = packageJson.version?.trim() || '0.0.0'

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
      __INTLIFY_JIT_COMPILATION__: true,
      __APP_VERSION__: JSON.stringify(appVersion)
    },
    server: {
      host: '0.0.0.0',
      port: devPort,
      strictPort: true,
      fs: {
        allow: [workspaceRoot]
      },
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/api/langgraph': {
          target: proxyTarget,
          changeOrigin: true
        },
        '/_system': {
          target: proxyTarget,
          changeOrigin: true
        }
      }
    }
  }
})
