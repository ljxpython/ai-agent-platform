<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'

type DrawerSide = 'left' | 'right'
type DrawerWidth = 'narrow' | 'normal' | 'wide' | 'full'

const props = withDefaults(
  defineProps<{
    show: boolean
    title: string
    side?: DrawerSide
    width?: DrawerWidth
    closeOnEscape?: boolean
    closeOnClickOutside?: boolean
  }>(),
  {
    side: 'right',
    width: 'normal',
    closeOnEscape: true,
    closeOnClickOutside: true
  }
)

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const drawerRef = ref<HTMLElement | null>(null)
let previousActiveElement: HTMLElement | null = null

function widthClass(width: DrawerWidth) {
  switch (width) {
    case 'narrow':
      return 'w-screen sm:w-[320px] sm:max-w-[92vw]'
    case 'wide':
      return 'w-screen sm:w-[520px] sm:max-w-[96vw]'
    case 'full':
      return 'w-screen sm:w-[min(720px,100vw)]'
    default:
      return 'w-screen sm:w-[420px] sm:max-w-[94vw]'
  }
}

function panelPositionClass(side: DrawerSide) {
  return side === 'left' ? 'left-0' : 'right-0'
}

function panelTransitionClass(side: DrawerSide, phase: 'from' | 'to') {
  if (side === 'left') {
    return phase === 'from' ? '-translate-x-full' : 'translate-x-0'
  }
  return phase === 'from' ? 'translate-x-full' : 'translate-x-0'
}

function closeDrawer() {
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
      drawerRef.value?.focus()
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
        class="fixed inset-0 z-[90] bg-slate-950/30 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        @click.self="closeOnClickOutside ? closeDrawer() : undefined"
      >
        <Transition
          enter-active-class="transform transition duration-200 ease-out"
          :enter-from-class="panelTransitionClass(side, 'from')"
          :enter-to-class="panelTransitionClass(side, 'to')"
          leave-active-class="transform transition duration-150 ease-in"
          :leave-from-class="panelTransitionClass(side, 'to')"
          :leave-to-class="panelTransitionClass(side, 'from')"
          appear
        >
          <div
            ref="drawerRef"
            tabindex="-1"
            class="pw-dialog-panel absolute inset-y-0 flex h-full flex-col overflow-hidden"
            :class="[panelPositionClass(side), widthClass(width)]"
          >
            <div class="flex shrink-0 items-center justify-between gap-4 border-b border-gray-100 px-6 py-4 dark:border-dark-800">
              <div class="text-base font-semibold text-gray-900 dark:text-white">
                {{ title }}
              </div>
              <button
                type="button"
                class="rounded-xl p-2 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-dark-800 dark:hover:text-dark-200"
                :aria-label="t('common.close')"
                @click="closeDrawer"
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
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
