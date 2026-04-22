import { computed } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

export function useWorkspaceProjectContext() {
  const workspaceStore = useWorkspaceStore()

  const activeProjectId = computed(() => workspaceStore.currentProjectId)
  const activeProject = computed(() => workspaceStore.currentProject)
  const activeProjects = computed(() => workspaceStore.projects)

  function setActiveProjectId(projectId: string) {
    workspaceStore.setProjectId(projectId)
  }

  return {
    workspaceStore,
    activeProjectId,
    activeProject,
    activeProjects,
    setActiveProjectId
  }
}
