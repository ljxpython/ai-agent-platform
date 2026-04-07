<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'

const { t } = useI18n()
const { activeProjectId, activeProjects, setActiveProjectId } = useWorkspaceProjectContext()
const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const projectOptions = computed(() =>
  activeProjects.value.map((project) => ({
    value: project.id,
    label: project.name
  }))
)

const currentProjectLabel = computed(
  () => projectOptions.value.find((project) => project.value === activeProjectId.value)?.label || t('topbar.projectPlaceholder')
)

function close() {
  isOpen.value = false
}

function toggle() {
  if (!projectOptions.value.length) {
    return
  }

  isOpen.value = !isOpen.value
}

function selectProject(projectId: string) {
  setActiveProjectId(projectId)
  close()
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
    class="relative max-w-full shrink-0"
  >
    <button
      type="button"
      class="pw-topbar-action min-h-9 min-w-0 max-w-full justify-start gap-1.5 px-2"
      :class="isOpen ? 'pw-topbar-action-active' : ''"
      :disabled="!projectOptions.length"
      :aria-label="t('common.project')"
      @click="toggle"
    >
      <BaseIcon
        name="project"
        size="sm"
        class="shrink-0 text-gray-400 dark:text-dark-400"
      />
      <span
        class="max-w-[min(120px,30vw)] truncate text-sm font-medium text-gray-800 dark:text-gray-100 sm:max-w-[128px]"
        :title="currentProjectLabel"
      >
        {{ currentProjectLabel }}
      </span>
      <BaseIcon
        name="chevron-down"
        size="xs"
        class="shrink-0 text-gray-400 transition"
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
        class="pw-topbar-dropdown right-0 mt-3 w-[min(300px,calc(100vw-2rem))] max-w-[calc(100vw-2rem)] p-2 sm:w-[260px]"
      >
        <div class="max-h-72 overflow-y-auto overscroll-contain">
          <button
            v-for="project in projectOptions"
            :key="project.value"
            type="button"
            class="pw-dropdown-item items-start justify-between gap-3"
            @click="selectProject(project.value)"
          >
            <span
              class="min-w-0 flex-1 break-words text-left font-medium leading-5"
              :title="project.label"
            >
              {{ project.label }}
            </span>
            <BaseIcon
              v-if="project.value === activeProjectId"
              name="check"
              size="sm"
              class="mt-0.5 shrink-0 text-primary-500"
            />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>
