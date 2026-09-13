<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, type CSSProperties } from 'vue'
import BaseIcon from '@/components/base/BaseIcon.vue'
import type { Agent } from '@/services/agents/types'

const props = withDefaults(
  defineProps<{
    agents?: Agent[]
    selectedAgentId?: string
    disabled?: boolean
  }>(),
  {
    agents: () => [],
    selectedAgentId: '',
    disabled: false
  }
)

const emit = defineEmits<{
  select: [agentId: string]
}>()

const isOpen = ref(false)
const searchQuery = ref('')
const triggerRef = ref<HTMLButtonElement | null>(null)
const dropdownRef = ref<HTMLElement | null>(null)
const dropdownStyle = ref<CSSProperties>({})

const selectedAgent = computed(() => {
  return props.agents.find((a) => a.id === props.selectedAgentId) ?? null
})

const currentLabel = computed(() => {
  return selectedAgent.value?.name || '选择智能体'
})

const filteredAgents = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return props.agents
  return props.agents.filter(
    (a) =>
      a.name.toLowerCase().includes(query) ||
      (a.description && a.description.toLowerCase().includes(query)) ||
      a.id.toLowerCase().includes(query)
  )
})

function updatePosition() {
  if (!isOpen.value || !triggerRef.value) return
  const rect = triggerRef.value.getBoundingClientRect()
  const spaceBelow = window.innerHeight - rect.bottom
  const dropdownHeight = 260

  const style: CSSProperties = {
    position: 'fixed',
    left: `${Math.max(12, Math.min(rect.left, window.innerWidth - 260))}px`,
    width: '240px',
    zIndex: 100
  }

  if (spaceBelow < dropdownHeight && rect.top > dropdownHeight) {
    style.bottom = `${window.innerHeight - rect.top + 6}px`
  } else {
    style.top = `${rect.bottom + 6}px`
  }

  dropdownStyle.value = style
}

function toggle() {
  if (props.disabled) return
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchQuery.value = ''
    nextTick(() => updatePosition())
  }
}

function select(agentId: string) {
  emit('select', agentId)
  isOpen.value = false
}

function handleClickOutside(event: MouseEvent) {
  if (!isOpen.value) return
  const target = event.target as Node
  if (triggerRef.value?.contains(target) || dropdownRef.value?.contains(target)) return
  isOpen.value = false
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isOpen.value) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  window.addEventListener('resize', updatePosition)
  window.addEventListener('scroll', updatePosition, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
})
</script>

<template>
  <div class="relative inline-flex items-center shrink-0">
    <button
      ref="triggerRef"
      type="button"
      :disabled="disabled"
      aria-label="对话目标"
      :aria-expanded="isOpen"
      class="group relative inline-flex h-8 items-center gap-2 rounded-lg border border-gray-200/90 bg-white/95 px-2.5 text-xs text-gray-700 shadow-2xs transition-all hover:border-primary-400 hover:bg-white hover:text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary-500/20 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 dark:border-dark-700 dark:bg-dark-800/90 dark:text-dark-200 dark:hover:border-primary-500/80 dark:hover:bg-dark-800 dark:hover:text-white"
      :class="isOpen ? 'border-primary-500 ring-2 ring-primary-500/20 dark:border-primary-500' : ''"
      @click="toggle"
    >
      <span class="flex h-4 w-4 items-center justify-center rounded-md bg-gradient-to-tr from-primary-600 to-indigo-500 text-white shadow-2xs">
        <BaseIcon
          name="assistant"
          size="xs"
        />
      </span>

      <span class="font-medium truncate max-w-[130px] sm:max-w-[180px]">
        {{ currentLabel }}
      </span>

      <span
        v-if="selectedAgent"
        class="h-1.5 w-1.5 rounded-full bg-emerald-500 ring-2 ring-emerald-100 dark:ring-emerald-950 shrink-0"
        title="已就绪"
      />

      <BaseIcon
        name="chevron-down"
        size="xs"
        class="text-gray-400 transition-transform duration-200 group-hover:text-gray-600 dark:text-dark-400 dark:group-hover:text-dark-200"
        :class="isOpen ? 'rotate-180 text-primary-500' : ''"
      />
    </button>

    <Teleport to="body">
      <Transition
        enter-active-class="transition duration-150 ease-out"
        enter-from-class="opacity-0 translate-y-1 scale-98"
        enter-to-class="opacity-100 translate-y-0 scale-100"
        leave-active-class="transition duration-100 ease-in"
        leave-from-class="opacity-100 translate-y-0 scale-100"
        leave-to-class="opacity-0 translate-y-1 scale-98"
      >
        <div
          v-if="isOpen"
          ref="dropdownRef"
          :style="dropdownStyle"
          class="rounded-xl border border-gray-200 bg-white p-1.5 shadow-xl ring-1 ring-black/5 dark:border-dark-700 dark:bg-dark-800 dark:ring-white/10"
        >
          <div
            v-if="agents.length > 5"
            class="p-1 pb-1.5"
          >
            <input
              v-model="searchQuery"
              type="text"
              placeholder="搜索智能体..."
              class="w-full rounded-lg border border-gray-200 bg-gray-50 px-2.5 py-1 text-xs text-gray-900 placeholder-gray-400 focus:border-primary-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-primary-500 dark:border-dark-700 dark:bg-dark-900 dark:text-white dark:placeholder-dark-400"
            >
          </div>

          <div class="max-h-60 overflow-y-auto space-y-0.5">
            <button
              v-for="agent in filteredAgents"
              :key="agent.id"
              type="button"
              class="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-xs transition-colors"
              :class="
                agent.id === selectedAgentId
                  ? 'bg-primary-50 text-primary-900 font-medium dark:bg-primary-950/40 dark:text-primary-100'
                  : 'text-gray-700 hover:bg-gray-100 dark:text-dark-200 dark:hover:bg-dark-700/60 dark:hover:text-white'
              "
              @click="select(agent.id)"
            >
              <div class="flex min-w-0 items-center gap-2">
                <span class="flex h-5 w-5 items-center justify-center rounded-md bg-gray-100 text-gray-600 dark:bg-dark-700 dark:text-dark-300">
                  <BaseIcon
                    name="assistant"
                    size="xs"
                  />
                </span>
                <div class="min-w-0 flex-1">
                  <p class="truncate font-medium">
                    {{ agent.name }}
                  </p>
                  <p
                    v-if="agent.description"
                    class="truncate text-[10px] text-gray-400 dark:text-dark-400"
                  >
                    {{ agent.description }}
                  </p>
                </div>
              </div>

              <span
                v-if="agent.id === selectedAgentId"
                class="text-primary-600 dark:text-primary-400 shrink-0"
              >
                <BaseIcon
                  name="check"
                  size="xs"
                />
              </span>
            </button>

            <div
              v-if="filteredAgents.length === 0"
              class="p-3 text-center text-xs text-gray-400 dark:text-dark-400"
            >
              未找到匹配的智能体
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
