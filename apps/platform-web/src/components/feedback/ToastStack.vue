<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useUiStore, type UiToastType } from '@/stores/ui'

const uiStore = useUiStore()
const { t } = useI18n()

const toasts = computed(() => uiStore.toasts)

function iconName(type: UiToastType) {
  switch (type) {
    case 'success':
      return 'check'
    case 'error':
      return 'x'
    case 'warning':
      return 'alert'
    default:
      return 'info'
  }
}

function toneClass(type: UiToastType) {
  switch (type) {
    case 'success':
      return 'border-emerald-200/80 text-emerald-600 dark:border-emerald-900/60 dark:text-emerald-300'
    case 'error':
      return 'border-rose-200/80 text-rose-600 dark:border-rose-900/60 dark:text-rose-300'
    case 'warning':
      return 'border-amber-200/80 text-amber-600 dark:border-amber-900/60 dark:text-amber-300'
    default:
      return 'border-sky-200/80 text-sky-600 dark:border-sky-900/60 dark:text-sky-300'
  }
}
</script>

<template>
  <Teleport to="body">
    <div class="pointer-events-none fixed right-4 top-4 z-[100] flex max-w-[calc(100vw-2rem)] flex-col gap-3">
      <TransitionGroup
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="translate-x-6 opacity-0"
        enter-to-class="translate-x-0 opacity-100"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="translate-x-0 opacity-100"
        leave-to-class="translate-x-6 opacity-0"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="pointer-events-auto pw-toast-card"
        >
          <div class="flex items-start gap-3">
            <div
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border bg-white/70 backdrop-blur dark:bg-dark-900/70"
              :class="toneClass(toast.type)"
            >
              <BaseIcon
                :name="iconName(toast.type)"
                size="sm"
              />
            </div>
            <div class="min-w-0 flex-1">
              <div
                v-if="toast.title"
                class="text-sm font-semibold text-gray-900 dark:text-white"
              >
                {{ toast.title }}
              </div>
              <p class="text-sm leading-6 text-gray-600 dark:text-dark-300">
                {{ toast.message }}
              </p>
            </div>
            <button
              type="button"
              class="rounded-xl p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-dark-200"
              :aria-label="t('common.close')"
              @click="uiStore.removeToast(toast.id)"
            >
              <BaseIcon
                name="x"
                size="sm"
              />
            </button>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
