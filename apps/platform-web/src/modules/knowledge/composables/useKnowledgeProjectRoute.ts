import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceProjectContext } from '@/composables/useWorkspaceProjectContext'

export function useKnowledgeProjectRoute() {
  const route = useRoute()
  const { activeProjectId, activeProjects, setActiveProjectId } = useWorkspaceProjectContext()

  const projectId = computed(() =>
    typeof route.params.projectId === 'string' ? route.params.projectId.trim() : ''
  )

  const project = computed(() =>
    activeProjects.value.find((item) => item.id === projectId.value) ?? null
  )

  watch(
    () => projectId.value,
    (nextProjectId) => {
      if (nextProjectId && nextProjectId !== activeProjectId.value) {
        setActiveProjectId(nextProjectId)
      }
    },
    { immediate: true }
  )

  return {
    projectId,
    project
  }
}
