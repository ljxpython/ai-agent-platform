<script setup lang="ts">
import { computed, onMounted } from 'vue'
import SurfaceCard from '@/components/base/SurfaceCard.vue'
import { useRoute, useRouter } from 'vue-router'
import { hasStoredAuthSession } from '@/services/auth/token'
import { defaultWorkspacePath } from '@/services/auth/permissions'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const redirectPath = computed(() => {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return redirect.startsWith('/workspace') ? redirect : defaultWorkspacePath(auth.user)
})

const fallbackTarget = computed(() =>
  redirectPath.value === '/workspace/overview'
    ? '/auth/login'
    : {
        path: '/auth/login',
        query: {
          redirect: redirectPath.value
        }
      }
)

onMounted(async () => {
  if (hasStoredAuthSession()) {
    await auth.hydrate()
    await router.replace(redirectPath.value)
    return
  }

  await router.replace(fallbackTarget.value)
})
</script>

<template>
  <SurfaceCard class="rounded-[28px] p-8 text-center">
    <div class="text-sm font-semibold text-gray-900 dark:text-white">
      正在返回智能体平台控制台
    </div>
    <p class="mt-3 text-sm leading-7 text-gray-500 dark:text-dark-300">
      登录回跳入口已保留，当前会自动回到正式登录页或已有会话对应的工作区。
    </p>
  </SurfaceCard>
</template>
