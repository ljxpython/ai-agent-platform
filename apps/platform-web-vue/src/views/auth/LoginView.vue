<script setup lang="ts">
import { nextTick, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import { useAuthStore } from '@/stores/auth'
import { useWorkspaceStore } from '@/stores/workspace'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()
const authStore = useAuthStore()
const workspaceStore = useWorkspaceStore()

const form = reactive({
  username: 'admin',
  password: 'admin123456'
})

const state = reactive({
  error: '',
  pending: false
})

async function redirectToWorkspace(redirectPath: string) {
  await router.replace(redirectPath)
  await nextTick()

  if (!router.currentRoute.value.path.startsWith('/auth')) {
    return
  }

  await authStore.fetchCurrentUser()
  await workspaceStore.hydrateContext()
  await router.replace(redirectPath)
  await nextTick()

  if (router.currentRoute.value.path.startsWith('/auth')) {
    window.location.assign(redirectPath)
  }
}

async function handleSubmit() {
  state.pending = true
  state.error = ''

  try {
    await authStore.login(form)
    await workspaceStore.hydrateContext()
    const redirectPath =
      typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/workspace')
        ? route.query.redirect
        : '/workspace/overview'

    await redirectToWorkspace(redirectPath)
  } catch (error) {
    state.error = error instanceof Error ? error.message : '登录失败'
  } finally {
    state.pending = false
  }
}
</script>

<template>
  <form
    class="space-y-5"
    @submit.prevent="handleSubmit"
  >
    <div class="space-y-2">
      <label class="block text-sm font-medium text-surface-700 dark:text-surface-300">
        {{ t('auth.username') }}
      </label>
      <BaseInput
        v-model="form.username"
        type="text"
        autocomplete="username"
      />
    </div>

    <div class="space-y-2">
      <label class="block text-sm font-medium text-surface-700 dark:text-surface-300">
        {{ t('auth.password') }}
      </label>
      <BaseInput
        v-model="form.password"
        type="password"
        autocomplete="current-password"
      />
    </div>

    <BaseButton
      type="submit"
      :disabled="state.pending || authStore.loading"
      block
    >
      {{ state.pending || authStore.loading ? '登录中...' : t('auth.login') }}
    </BaseButton>

    <p
      v-if="state.error"
      class="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
    >
      {{ state.error }}
    </p>

    <p class="text-center text-sm text-surface-500 dark:text-surface-400">
      {{ t('auth.hint') }}
    </p>
  </form>
</template>
