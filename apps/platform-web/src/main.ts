import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { useThemeStore } from '@/stores/theme'
import '@/styles/index.css'

async function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)

  const themeStore = useThemeStore(pinia)
  themeStore.init()

  app.use(router)
  app.use(i18n)

  await router.isReady()
  app.mount('#app')
}

void bootstrap()
