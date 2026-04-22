<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { FilterSettingItem } from '@/components/platform/filter-settings'

const props = withDefaults(
  defineProps<{
    items: FilterSettingItem[]
    modelValue: string[]
    buttonLabel?: string
  }>(),
  {
    buttonLabel: '筛选设置'
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const menuOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const toggleableItems = computed(() => props.items.filter((item) => !item.alwaysVisible))
const visibleSet = computed(() => new Set(props.modelValue))

function closeMenu() {
  menuOpen.value = false
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function toggleItem(item: FilterSettingItem) {
  if (item.alwaysVisible) {
    return
  }

  const nextVisible = new Set(props.modelValue)
  if (nextVisible.has(item.key)) {
    nextVisible.delete(item.key)
  } else {
    nextVisible.add(item.key)
  }

  emit(
    'update:modelValue',
    props.items
      .filter((candidate) => candidate.alwaysVisible || nextVisible.has(candidate.key))
      .map((candidate) => candidate.key)
  )
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
    v-if="toggleableItems.length"
    ref="rootRef"
    class="relative"
  >
    <button
      type="button"
      class="pw-table-tool-button"
      @click="toggleMenu"
    >
      <BaseIcon
        name="filter"
        size="sm"
      />
      <span>{{ buttonLabel }}</span>
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
        class="pw-data-table-menu right-0 top-full mt-2 min-w-[220px]"
      >
        <div class="border-b border-gray-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-gray-400 dark:border-dark-800 dark:text-dark-500">
          可见筛选项
        </div>
        <button
          v-for="item in toggleableItems"
          :key="item.key"
          type="button"
          class="pw-data-table-menu-item"
          @click="toggleItem(item)"
        >
          <BaseIcon
            :name="visibleSet.has(item.key) ? 'eye' : 'eye-off'"
            size="sm"
          />
          <span class="flex-1 text-left">{{ item.label }}</span>
          <BaseIcon
            v-if="visibleSet.has(item.key)"
            name="check"
            size="sm"
            class="text-primary-500"
          />
        </button>
      </div>
    </Transition>
  </div>
</template>
