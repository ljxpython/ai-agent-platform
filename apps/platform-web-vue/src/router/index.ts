import { createRouter, createWebHistory } from 'vue-router'
import { registerRouterGuards } from './guards'
import { routes } from './routes'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

registerRouterGuards(router)

export default router
