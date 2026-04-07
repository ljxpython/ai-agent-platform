<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'

const props = withDefaults(
  defineProps<{
    text: string
    label?: string
    align?: 'left' | 'center' | 'right'
  }>(),
  {
    label: '帮助说明',
    align: 'center'
  }
)

const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

function open() {
  isOpen.value = true
}

function close() {
  isOpen.value = false
}

function toggle() {
  isOpen.value = !isOpen.value
}

function alignmentClass() {
  if (props.align === 'left') {
    return 'left-0'
  }
  if (props.align === 'right') {
    return 'right-0'
  }
  return 'left-1/2 -translate-x-1/2'
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
  <span
    ref="rootRef"
    class="relative inline-flex"
    @mouseenter="open"
    @mouseleave="close"
  >
    <button
      type="button"
      class="inline-flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:text-dark-400 dark:hover:bg-dark-800 dark:hover:text-dark-100"
      :aria-label="label"
      @click.stop="toggle"
    >
      <BaseIcon
        name="info"
        size="xs"
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
        class="absolute top-full z-20 mt-2 w-[min(280px,calc(100vw-2rem))] rounded-2xl border border-gray-200 bg-white px-3 py-3 text-xs leading-6 text-gray-600 shadow-lg dark:border-dark-700 dark:bg-dark-900 dark:text-dark-200"
        :class="alignmentClass()"
      >
        {{ text }}
      </div>
    </Transition>
  </span>
</template>
