import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseEnv } from 'node:util'

export const platformUrl = process.env.PLATFORM_TEST_URL ?? 'http://127.0.0.1:2142'

export function testCredentials() {
  const envPath = resolve(process.cwd(), '../platform-api/.env')
  const settings = existsSync(envPath) ? parseEnv(readFileSync(envPath, 'utf8')) : {}
  const credentials = {
    username: process.env.PLATFORM_TEST_USERNAME ?? settings.PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME ?? 'admin',
    password: process.env.PLATFORM_TEST_PASSWORD ?? settings.PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD
  }
  if (!credentials.password) throw new Error('Configure PLATFORM_TEST_PASSWORD or the local bootstrap password before E2E')
  return credentials
}

export async function createPlatformFixture(graphId = 'workflow_demo') {
  const login = await fetch(`${platformUrl}/api/identity/session`, {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(testCredentials())
  })
  if (!login.ok) throw new Error(`Test login failed: HTTP ${login.status}`)
  const session = await login.json() as { tokens: { access_token: string; refresh_token: string; token_type: string } }
  let projectId = ''
  async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
    const response = await fetch(`${platformUrl}${path}`, { method,
      headers: { authorization: `Bearer ${session.tokens.access_token}`, 'content-type': 'application/json',
        ...(projectId ? { 'x-project-id': projectId } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body) })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { error?: { code?: string } }
      throw new Error(`${method} ${path}: HTTP ${response.status} ${payload.error?.code ?? ''}`)
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>
  }
  const project = await request<{ id: string }>('/api/projects', 'POST', { name: `Web refactor ${crypto.randomUUID().slice(0, 8)}` })
  projectId = project.id
  const cleanup = () => request(`/api/projects/${projectId}`, 'DELETE')
  try {
    await request('/api/runtime/graphs/refresh', 'POST')
    const graphs = await request<{ graphs: Array<{ id: string; graph_id: string }> }>('/api/runtime/graphs')
    const graph = graphs.graphs.find((item) => item.graph_id === graphId)
    if (!graph) throw new Error(`Deploy graph ${graphId} before running chain tests; available: ${graphs.graphs.map((item) => item.graph_id).join(', ')}`)
    await request(`/api/projects/${projectId}/runtime-policies/graphs/${graph.id}`, 'PUT', { is_enabled: true })
    await request('/api/runtime/tools/refresh', 'POST')
    const tools = await request<{ tools: Array<{ id: string; tool_key: string }> }>('/api/runtime/tools')
    for (const tool of tools.tools) {
      if (graphId === 'showcase_demo' || tool.tool_key === 'read_reference') {
        await request(`/api/projects/${projectId}/runtime-policies/tools/${tool.id}`, 'PUT', { is_enabled: true })
      }
    }
    const models = await request<{ models: Array<{ id: string; enabled: boolean; credential_configured: boolean }> }>('/api/runtime/models')
    let model = models.models.find((item) => item.enabled && item.credential_configured)
    if (!model && process.env.Q5_QUEUE_FIXTURE === '1') {
      model = await request('/api/runtime/models', 'POST', {
        provider: 'openai', protocol: 'openai', display_name: 'Q5 deterministic fixture',
        model: 'q5-fixture', base_url: 'https://example.com/v1', api_key: 'fixture-only', enabled: true
      })
    }
    if (!model && process.env.PLATFORM_TEST_SEED_MODEL === '1') {
      const runtime = parseEnv(readFileSync(resolve(process.cwd(), '../runtime-service/.env'), 'utf8'))
      if (!runtime.DEEPSEEK_PROXY_URL || !runtime.DEEPSEEK_PROXY_API_KEY) throw new Error('Test model credentials are not configured')
      model = await request('/api/runtime/models', 'POST', {
        provider: 'deepseek', protocol: 'deepseek', display_name: 'Web refactor test model',
        model: process.env.PLATFORM_TEST_MODEL ?? 'DeepSeek-V4-Flash',
        base_url: runtime.DEEPSEEK_PROXY_URL, api_key: runtime.DEEPSEEK_PROXY_API_KEY, enabled: true
      })
    }
    if (!model) throw new Error('A configured enabled test model is required')
    await request(`/api/projects/${projectId}/runtime-policies/models/${model.id}`, 'PUT', {
      is_enabled: true, is_default_for_project: true
    })
    const aligned = await request<{ items: Array<{ id: string; graph_id: string }> }>(
      `/api/projects/${projectId}/agents?graph_id=${encodeURIComponent(graphId)}`
    )
    const automatic = aligned.items.find(item => item.graph_id === graphId)
    if (!automatic) throw new Error('Authorized graph did not produce an Agent')
    const agent = await request<{ id: string; graph_id: string }>(`/api/agents/${automatic.id}`, 'PATCH', {
      name: 'Web refactor test', context: { model_id: model.id }
    })
    return { projectId, graphId, modelId: model.id, agent, request, cleanup, tokens: session.tokens }
  } catch (error) {
    await cleanup()
    throw error
  }
}
