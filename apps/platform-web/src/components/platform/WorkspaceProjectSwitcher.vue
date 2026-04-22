<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import BaseIcon from '@/components/base/BaseIcon.vue'
import { useTopbarDropdown } from '@/composables/useTopbarDropdown'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { activeProjectId, activeProjects, setActiveProjectId, workspaceStore } = useWorkspaceProjectContext()
const refreshing = ref(false)
const {
  close,
  dropdownPlacement,
  dropdownRef,
  dropdownStyle,
  isOpen,
  rootRef,
  toggle: toggleDropdown,
  triggerRef
} = useTopbarDropdown({
  alignment: 'end',
  fallbackWidth: 260,
  minWidth: 220
})

const projectOptions = computed(() =>
  activeProjects.value.map((project) => ({
    value: project.id,
    label: project.name
  }))
)

const currentProjectLabel = computed(
  () => projectOptions.value.find((project) => project.value === activeProjectId.value)?.label || t('topbar.projectPlaceholder')
)

async function ensureProjectOptions() {
  if (refreshing.value) {
    return
  }

  refreshing.value = true

  try {
    await workspaceStore.hydrateContext()
  } finally {
    refreshing.value = false
  }
}

async function toggle() {
  await ensureProjectOptions()

  if (!projectOptions.value.length) {
    return
  }

  toggleDropdown()
}

async function selectProject(projectId: string) {
  if (projectId === activeProjectId.value) {
    close()
    return
  }

  const currentRouteProjectId = typeof route.params.projectId === 'string' ? route.params.projectId.trim() : ''
  if (currentRouteProjectId) {
    await router.replace({
      name: String(route.name || ''),
      params: {
        ...route.params,
        projectId,
      },
      query: route.query,
      hash: route.hash,
    })
  } else {
    setActiveProjectId(projectId)
  }

  close()
}

onMounted(() => {
  if (projectOptions.value.length <= 1) {
    void ensureProjectOptions()
  }
})
</script>

<template>
  <div
    ref="rootRef"
    class="relative max-w-full shrink-0"
  >
    <button
      ref="triggerRef"
      type="button"
      class="pw-topbar-action min-h-9 min-w-0 max-w-full justify-start gap-1.5 px-2.5"
      :class="isOpen ? 'pw-topbar-action-active' : ''"
      :disabled="refreshing || !projectOptions.length"
      :aria-label="t('common.project')"
      @click="void toggle()"
    >
      <BaseIcon
        name="project"
        size="sm"
        class="shrink-0 text-gray-400 dark:text-dark-400"
      />
      <span
        class="max-w-[min(112px,28vw)] truncate text-sm font-medium text-gray-800 dark:text-gray-100 sm:max-w-[120px]"
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
      <Teleport to="body">
        <div
          v-if="isOpen"
          ref="dropdownRef"
          class="pw-topbar-dropdown p-2"
          :class="dropdownPlacement === 'top' ? 'origin-bottom' : 'origin-top'"
          :style="dropdownStyle"
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
      </Teleport>
    </Transition>
  </div>
</template>
