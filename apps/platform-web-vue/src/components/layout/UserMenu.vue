<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const authStore = useAuthStore()
const uiStore = useUiStore()
const router = useRouter()
const { t } = useI18n()

const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const initials = computed(() => (authStore.user?.username || 'PW').slice(0, 2).toUpperCase())
const roleLabel = computed(() => (authStore.user?.is_super_admin ? t('common.admin') : t('common.member')))

async function navigateTo(path: string) {
  isOpen.value = false
  await router.push(path)
}

async function handleLogout() {
  authStore.logout()
  uiStore.pushToast({
    type: 'success',
    message: t('toast.logoutSuccess')
  })
  isOpen.value = false
  await router.replace('/auth/login')
}

function close() {
  isOpen.value = false
}

function toggle() {
  isOpen.value = !isOpen.value
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div
    ref="rootRef"
    class="relative"
  >
    <button
      type="button"
      class="pw-topbar-user-trigger"
      :class="isOpen ? 'pw-topbar-user-trigger-active' : ''"
      @click="toggle"
    >
      <div class="pw-topbar-user-avatar">
        {{ initials }}
      </div>
      <div class="pw-topbar-user-copy">
        <div class="max-w-[120px] truncate text-sm font-medium text-gray-900 dark:text-white">
          {{ authStore.user?.username ?? t('common.loading') }}
        </div>
        <div class="text-xs text-gray-500 dark:text-dark-400">
          {{ t('topbar.operator') }}
        </div>
      </div>
      <BaseIcon
        name="chevron-down"
        size="xs"
        class="text-gray-400 transition"
        :class="isOpen ? 'rotate-180' : ''"
      />
    </button>

    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="translate-y-1 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-120 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-1 opacity-0"
    >
      <div
        v-if="isOpen"
        class="pw-topbar-dropdown right-0 mt-3 w-64 p-0"
      >
        <div class="border-b border-gray-100 px-4 py-4 dark:border-dark-800">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-primary text-sm font-semibold text-white">
              {{ initials }}
            </div>
            <div class="min-w-0">
              <div class="truncate text-sm font-semibold text-gray-900 dark:text-white">
                {{ authStore.user?.username ?? t('common.loading') }}
              </div>
              <div class="truncate text-xs text-gray-500 dark:text-dark-400">
                {{ authStore.user?.email || t('common.unavailable') }}
              </div>
            </div>
          </div>
          <div class="mt-3 inline-flex rounded-full border border-primary-100 bg-primary-50 px-3 py-1 text-xs font-semibold text-primary-700 dark:border-primary-900/40 dark:bg-primary-950/30 dark:text-primary-300">
            {{ roleLabel }}
          </div>
        </div>

        <div class="p-2">
          <button
            type="button"
            class="pw-dropdown-item"
            @click="navigateTo('/workspace/me')"
          >
            <BaseIcon
              name="user"
              size="sm"
            />
            {{ t('common.profile') }}
          </button>
          <button
            type="button"
            class="pw-dropdown-item"
            @click="navigateTo('/workspace/security')"
          >
            <BaseIcon
              name="lock"
              size="sm"
            />
            {{ t('common.security') }}
          </button>
          <button
            type="button"
            class="pw-dropdown-item text-rose-600 dark:text-rose-300"
            @click="handleLogout"
          >
            <BaseIcon
              name="logout"
              size="sm"
            />
            {{ t('common.logout') }}
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
