import type { PlatformClientModule } from '@/services/platform/control-plane'

const workspaceProjectContextRules: Array<{
  prefix: string
  module: PlatformClientModule
}> = [
  { prefix: '/workspace/overview', module: 'projects' },
  { prefix: '/workspace/runtime', module: 'runtime_gateway' },
  { prefix: '/workspace/chat', module: 'runtime_gateway' },
  { prefix: '/workspace/threads', module: 'runtime_gateway' },
  { prefix: '/workspace/sql-agent', module: 'runtime_gateway' },
  { prefix: '/workspace/assistants', module: 'assistants' },
  { prefix: '/workspace/testcase', module: 'testcase' },
  { prefix: '/workspace/announcements', module: 'announcements' },
  { prefix: '/workspace/operations', module: 'operations' },
  { prefix: '/workspace/projects', module: 'projects' },
  { prefix: '/workspace/audit', module: 'audit' }
]

export function getWorkspaceProjectContextModule(path: string): PlatformClientModule | null {
  const match = workspaceProjectContextRules.find(
    (rule) => path === rule.prefix || path.startsWith(`${rule.prefix}/`)
  )

  return match?.module || null
}

export function usesRuntimeWorkspaceProjectContext(path: string): boolean {
  return Boolean(getWorkspaceProjectContextModule(path))
}
