import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthorization } from '@/composables/useAuthorization'

type SidebarItem = {
  to: string
  label: string
  icon: string
  sectionTitle?: string
  exact?: boolean
}

type SidebarGroup = {
  id: string
  label: string
  items: SidebarItem[]
}

export function useNavigation() {
const router = useRouter()
const authorization = useAuthorization()
const groups = computed(() => {
  const projectId = authorization.currentProjectId.value
  const result = new Map<string, SidebarGroup>()
  for (const item of router.getRoutes()) {
    const nav = item.meta.navigation
    if (!nav || item.path.includes(':projectId') && !projectId) continue
    const permissions = item.meta.requiredPermissions ?? []
    const allowed = item.meta.permissionMode === 'any'
      ? permissions.some(permission => authorization.can(permission, projectId))
      : permissions.every(permission => authorization.can(permission, projectId))
    if (!allowed) continue
    const group = result.get(nav.group) ?? { id: nav.group, label: nav.group, items: [] }
    group.items.push({ to: item.path.replace(':projectId', encodeURIComponent(projectId)).replace('/:threadId?', ''), label: nav.label, icon: nav.icon, exact: item.name === 'workspace-projects' })
    result.set(nav.group, group)
  }
  return ['工作区', '项目管理', '平台管理'].flatMap(key => result.has(key) ? [result.get(key)!] : [])
})

return groups
}
