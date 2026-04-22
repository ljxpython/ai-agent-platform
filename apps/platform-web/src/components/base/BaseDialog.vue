<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'

type DialogWidth = 'narrow' | 'normal' | 'wide' | 'full'

const props = withDefaults(
  defineProps<{
    show: boolean
    title: string
    width?: DialogWidth
    closeOnEscape?: boolean
    closeOnClickOutside?: boolean
  }>(),
  {
    width: 'normal',
    closeOnEscape: true,
    closeOnClickOutside: true
  }
)

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const dialogRef = ref<HTMLElement | null>(null)
let previousActiveElement: HTMLElement | null = null

function widthClass(width: DialogWidth) {
  switch (width) {
    case 'narrow':
      return 'max-w-md'
    case 'wide':
      return 'max-w-4xl'
    case 'full':
      return 'max-w-6xl'
    default:
      return 'max-w-xl'
  }
}

function closeDialog() {
  emit('close')
}

function handleEscape(event: KeyboardEvent) {
  if (props.show && props.closeOnEscape && event.key === 'Escape') {
    emit('close')
  }
}

watch(
  () => props.show,
  async (isOpen) => {
    if (typeof document === 'undefined') {
      return
    }

    if (isOpen) {
      previousActiveElement = document.activeElement as HTMLElement | null
      document.body.classList.add('pw-dialog-open')
      await nextTick()
      dialogRef.value?.focus()
      return
    }

    document.body.classList.remove('pw-dialog-open')
    previousActiveElement?.focus?.()
    previousActiveElement = null
  },
  { immediate: true }
)

onMounted(() => {
  document.addEventListener('keydown', handleEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscape)
  document.body.classList.remove('pw-dialog-open')
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="show"
        class="fixed inset-0 z-[90] flex items-start justify-center overflow-y-auto bg-slate-950/30 p-3 backdrop-blur-sm sm:items-center sm:p-4"
        role="dialog"
        aria-modal="true"
        @click.self="closeOnClickOutside ? closeDialog() : undefined"
      >
        <div
          ref="dialogRef"
          tabindex="-1"
          class="pw-dialog-panel my-3 flex max-h-[calc(100vh-1.5rem)] w-full flex-col overflow-hidden sm:my-0 sm:max-h-[calc(100vh-2rem)]"
          :class="widthClass(width)"
        >
          <div class="flex shrink-0 items-center justify-between gap-4 border-b border-gray-100 px-6 py-4 dark:border-dark-800">
            <div class="text-base font-semibold text-gray-900 dark:text-white">
              {{ title }}
            </div>
            <button
              type="button"
              class="rounded-xl p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-dark-200"
              :aria-label="t('common.close')"
              @click="closeDialog"
            >
              <BaseIcon
                name="x"
                size="sm"
              />
            </button>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto px-6 py-5">
            <slot />
          </div>

          <div
            v-if="$slots.footer"
            class="flex shrink-0 justify-end border-t border-gray-100 px-6 py-4 dark:border-dark-800"
          >
            <slot name="footer" />
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
