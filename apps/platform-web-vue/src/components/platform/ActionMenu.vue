<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { ActionMenuItem } from '@/components/platform/data-table'

const props = defineProps<{
  items: ActionMenuItem[]
}>()

const menuOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const visibleItems = computed(() => props.items.filter((item) => item))

function closeMenu() {
  menuOpen.value = false
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

async function handleSelect(item: ActionMenuItem) {
  if (item.disabled) {
    return
  }

  closeMenu()
  await item.onSelect()
}

function handleClickOutside(event: MouseEvent) {
  if (rootRef.value && !rootRef.value.contains(event.target as Node)) {
    closeMenu()
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
    v-if="visibleItems.length"
    ref="rootRef"
    class="relative flex justify-end"
  >
    <button
      type="button"
      class="pw-table-tool-button h-9 w-9 px-0"
      aria-label="更多操作"
      @click="toggleMenu"
    >
      <BaseIcon
        name="ellipsis-horizontal"
        size="sm"
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
        v-if="menuOpen"
        class="pw-data-table-menu right-0 top-full mt-2 min-w-[180px]"
      >
        <button
          v-for="item in visibleItems"
          :key="item.key"
          type="button"
          class="pw-data-table-menu-item"
          :class="item.danger ? 'text-rose-600 dark:text-rose-300' : ''"
          :disabled="item.disabled"
          @click="handleSelect(item)"
        >
          <BaseIcon
            v-if="item.icon"
            :name="item.icon as never"
            size="sm"
          />
          <span>{{ item.label }}</span>
        </button>
      </div>
    </Transition>
  </div>
</template>
