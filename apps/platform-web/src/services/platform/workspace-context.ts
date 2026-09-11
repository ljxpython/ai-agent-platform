export type WorkspaceProjectContextModule =
  | 'projects'
  | 'runtime_gateway'
  | 'assistants'
  | 'announcements'
  | 'audit'

const workspaceProjectContextRules: Array<{
  prefix: string
  module: WorkspaceProjectContextModule
}> = [
  { prefix: '/workspace/overview', module: 'projects' },
  { prefix: '/workspace/projects', module: 'projects' },
  { prefix: '/workspace/announcements', module: 'announcements' },
  { prefix: '/workspace/audit', module: 'audit' }
]


export function getWorkspaceProjectContextModule(path: string): WorkspaceProjectContextModule | null {
  const match = workspaceProjectContextRules.find(
    (rule) => path === rule.prefix || path.startsWith(`${rule.prefix}/`)
  )

  return match?.module || null
}

export function usesRuntimeWorkspaceProjectContext(path: string): boolean {
  return Boolean(getWorkspaceProjectContextModule(path))
}
