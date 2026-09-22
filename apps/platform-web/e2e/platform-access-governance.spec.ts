import { test, expect, type APIRequestContext, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

test.skip(process.env.RUN_LOCAL_GOVERNANCE_E2E !== '1', 'Requires the isolated governance_server.py fixture')
test.setTimeout(120_000)
const apiUrl = 'http://127.0.0.1:12142'
const webUrl = 'http://127.0.0.1:13000'
const password = 'Governance-test-only-2026!'

async function identity(request: APIRequestContext, name: string) {
  const response = await request.post(`${apiUrl}/api/identity/session`, { data: { username: `governance-${name}`, password } })
  expect(response.ok()).toBeTruthy()
  return (await response.json()).tokens.access_token as string
}
async function login(page: Page, name: string) {
  await page.goto(`${webUrl}/auth/login`)
  await page.locator('input[autocomplete="username"]').fill(`governance-${name}`)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await expect(page).toHaveURL(/\/workspace\//, { timeout: 30_000 })
}

test('private sharing and no-project administrator takeover/delete cross the real platform gateway', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8')) as { project_id: string; users: Record<string, string> }
  const owner = await identity(request, 'owner')
  const peer = await identity(request, 'peer')
  const admin = await identity(request, 'superadmin')
  const headers = (token: string) => ({ authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id })
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, { headers: headers(owner), data: { metadata: { title: 'Governance private fixture', harness: 'platform-governance-browser' } } })
  expect(created.ok()).toBeTruthy()
  const threadId = (await created.json()).thread_id as string
  let deleted = false
  try {
    const path = `${apiUrl}/api/langgraph/threads/${threadId}`
    expect((await request.get(path, { headers: headers(peer) })).status()).toBe(403)
    expect((await request.get(path, { headers: headers(admin) })).status()).toBe(403)
    const share = await request.put(`${path}/shares`, { headers: headers(owner), data: { user_id: fixture.users.peer, actions: ['read'] } })
    expect(share.ok()).toBeTruthy()
    expect((await request.get(path, { headers: headers(peer) })).ok()).toBeTruthy()
    expect((await request.patch(path, { headers: headers(peer), data: { title: 'denied' } })).status()).toBe(403)
    expect((await request.put(`${path}/shares`, { headers: headers(owner), data: { user_id: fixture.users.peer, actions: [] } })).ok()).toBeTruthy()
    expect((await request.get(path, { headers: headers(peer) })).status()).toBe(403)

    await login(page, 'superadmin')
    await page.goto(`${webUrl}/workspace/thread-governance`)
    await page.getByRole('button', { name: '项目', exact: true }).click()
    await page.getByRole('button', { name: 'Governance E2E', exact: true }).click()
    await page.getByLabel('会话 ID').fill(threadId)
    await page.getByRole('button', { name: '定位会话', exact: true }).click()
    await expect(page.getByText('无法完成操作', { exact: true })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Governance private fixture' })).toBeHidden()
    await page.getByRole('button', { name: '临时访问', exact: true }).click()
    await page.getByLabel('工单或请求号').fill('E2E-PRIVATE-001')
    await page.getByLabel('具体原因').fill('用户明确请求排查本次专用测试会话')
    await page.getByRole('button', { name: '申请临时读取', exact: true }).click()
    await expect(page.getByText(/临时读取已授权/)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.getByText('无法完成操作', { exact: true })).toBeHidden()
    await expect(page.getByRole('heading', { name: 'Governance private fixture' })).toBeVisible()
    expect((await request.get(path, { headers: headers(admin) })).ok()).toBeTruthy()
    await page.screenshot({ path: '/tmp/governance-admin-desktop.png', fullPage: true })

    await page.getByRole('button', { name: '临时访问', exact: true }).click()
    await page.getByRole('button', { name: '立即结束临时访问', exact: true }).click()
    await expect(page.getByText('临时访问已结束。', { exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    expect((await request.get(path, { headers: headers(admin) })).status()).toBe(403)
    await expect(page.getByRole('heading', { name: 'Governance private fixture' })).toBeHidden()
    await page.getByRole('button', { name: '删除会话', exact: true }).click()
    await page.getByRole('button', { name: '确认删除', exact: true }).click()
    await expect(page.getByText('会话已删除。', { exact: true })).toBeVisible()
    deleted = true
  } finally {
    if (!deleted) {
      const cleanup = await fetch(`${apiUrl}/api/langgraph/threads/${threadId}`, { method: 'DELETE', headers: headers(admin) })
      expect(cleanup.ok).toBeTruthy()
    }
  }
})

test('mobile operator lands on governance, synchronizes catalog, and cannot enter private governance or execute', async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page, 'operator')
  await expect(page).toHaveURL(/\/workspace\/control-plane$/)
  await expect(page.getByText('全局目录同步', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '同步范围', exact: true }).click()
  await page.getByRole('button', { name: 'Governance E2E', exact: true }).click()
  await page.getByRole('button', { name: '同步 Graph 目录', exact: true }).click()
  await expect(page.getByText(/Graph全局目录已刷新/)).toBeVisible({ timeout: 30_000 })
  await page.screenshot({ path: '/tmp/governance-operator-mobile.png', fullPage: true })
  await page.goto(`${webUrl}/workspace/thread-governance`)
  await expect(page).toHaveURL(/access-unavailable/, { timeout: 30_000 })
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const operator = await identity(request, 'operator')
  const response = await request.post(`${apiUrl}/api/langgraph/threads`, { headers: { authorization: `Bearer ${operator}`, 'x-project-id': fixture.project_id }, data: {} })
  expect(response.status()).toBe(403)
})

test('user creation survives membership failure and retries without recreating the account', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const name = `new-${Date.now()}`
  await login(page, 'provisioner')
  await page.goto(`${webUrl}/workspace/users/new`)
  await page.getByPlaceholder('请输入用户名').fill(`governance-${name}`)
  await page.getByPlaceholder('请输入至少 8 位密码').fill(password)
  const createdResponse = page.waitForResponse(response => response.url().endsWith('/api/users') && response.request().method() === 'POST')
  await page.getByRole('button', { name: '创建用户', exact: true }).click()
  const created = await createdResponse
  expect(created.ok()).toBeTruthy()
  const user = await created.json()
  await expect(page.getByText('第二步：加入项目（可选）')).toBeVisible()
  await expect(page.locator('input[type="password"]')).toHaveCount(0)
  // The new account can log in before receiving any membership.
  const token = await identity(request, name)
  expect((await request.post(`${apiUrl}/api/langgraph/threads`, {
    headers: { authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id }, data: {}
  })).status()).toBe(403)
  await page.getByRole('button', { name: '项目', exact: true }).click()
  await page.getByRole('button', { name: 'Governance E2E', exact: true }).click()
  const membership = `**/api/projects/${fixture.project_id}/members/${user.id}`
  await page.route(membership, route => route.fulfill({ status: 503, contentType: 'application/json',
    body: JSON.stringify({ error: { code: 'TEST_UNAVAILABLE', message: 'Temporary membership outage' } }) }), { times: 1 })
  await page.getByRole('button', { name: '加入项目 / 重试绑定', exact: true }).click()
  await expect(page.getByText(/用户已保留，项目绑定失败/)).toBeVisible()
  const boundResponse = page.waitForResponse(response => response.url().endsWith(`/members/${user.id}`) && response.request().method() === 'PUT')
  await page.getByRole('button', { name: '加入项目 / 重试绑定', exact: true }).click()
  expect((await boundResponse).ok()).toBeTruthy()
  await expect(page.getByText('项目绑定成功', { exact: true })).toBeVisible()
  const headers = { authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id }
  const thread = await request.post(`${apiUrl}/api/langgraph/threads`, { headers, data: {} })
  expect(thread.ok()).toBeTruthy()
  const { thread_id: threadId } = await thread.json()
  expect((await request.delete(`${apiUrl}/api/langgraph/threads/${threadId}`, { headers })).ok()).toBeTruthy()
})

test('announcement editing keeps its scope and global governance excludes project notices', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const token = await identity(request, 'provisioner')
  const headers = { authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id }
  const title = `Global governance ${Date.now()}`
  const projectTitle = `Project-only governance ${Date.now()}`
  const global = await request.post(`${apiUrl}/api/announcements`, { headers, data: { title, body: 'Governance browser fixture', scope_type: 'global' } })
  const project = await request.post(`${apiUrl}/api/announcements`, { headers,
    data: { title: projectTitle, scope_type: 'project', scope_project_id: fixture.project_id } })
  expect(global.ok()).toBeTruthy()
  expect(project.ok()).toBeTruthy()
  const globalId = (await global.json()).id
  const projectId = (await project.json()).id
  try {
    await login(page, 'operator')
    await page.goto(`${webUrl}/workspace/announcements`)
    const row = page.getByRole('row').filter({ hasText: title })
    await expect(row).toBeVisible()
    await expect(page.getByText(projectTitle, { exact: true })).toHaveCount(0)
    await row.getByRole('button', { name: '更多操作' }).click()
    await page.getByRole('button', { name: '编辑公告', exact: true }).click()
    await expect(page.getByRole('button', { name: '范围', exact: true })).toBeDisabled()
    await expect(page.getByRole('button', { name: '项目', exact: true })).toBeDisabled()
    await page.getByLabel('标题', { exact: true }).fill(`${title} edited`)
    await page.getByRole('button', { name: '保存公告', exact: true }).click()
    await expect(page.getByRole('row').filter({ hasText: `${title} edited` })).toBeVisible()
    const operator = await identity(request, 'operator')
    expect((await request.patch(`${apiUrl}/api/announcements/${projectId}`, {
      headers: { authorization: `Bearer ${operator}`, 'x-project-id': fixture.project_id }, data: { title: 'denied' }
    })).status()).toBe(403)
    expect((await request.patch(`${apiUrl}/api/announcements/${globalId}`, {
      headers, data: { scope_type: 'project', scope_project_id: fixture.project_id }
    })).status()).toBe(400)
  } finally {
    for (const id of [globalId, projectId]) {
      expect((await fetch(`${apiUrl}/api/announcements/${id}`, { method: 'DELETE', headers })).ok).toBeTruthy()
    }
  }
})

test('operator cannot mutate a high-privilege service account through UI or API', async ({ page, request }) => {
  const admin = await identity(request, 'superadmin')
  const operator = await identity(request, 'operator')
  const name = `Governance protected ${Date.now()}`
  const response = await request.post(`${apiUrl}/api/service-accounts`, {
    headers: { authorization: `Bearer ${admin}` }, data: { name, platform_roles: ['platform_super_admin'] }
  })
  expect(response.ok()).toBeTruthy()
  const account = await response.json()
  // This account belongs to the temporary Platform DB destroyed by the fixture.
  await login(page, 'operator')
  await page.goto(`${webUrl}/workspace/service-accounts`)
  const card = page.locator('article').filter({ hasText: name })
  await expect(card).toBeVisible()
  await expect(card.getByText('高权限账号：仅平台管理员可编辑、停用或管理 Token')).toBeVisible()
  for (const action of ['编辑', '发 Token', '停用']) {
    await expect(card.getByRole('button', { name: action, exact: true })).toBeDisabled()
  }
  const headers = { authorization: `Bearer ${operator}` }
  expect((await request.patch(`${apiUrl}/api/service-accounts/${account.id}`, {
    headers, data: { status: 'disabled' }
  })).status()).toBe(403)
  expect((await request.post(`${apiUrl}/api/service-accounts/${account.id}/tokens`, {
    headers, data: { name: 'denied-token' }
  })).status()).toBe(403)
})

test('private child resources deny peers and sharing never grants terminal or full access', async ({ request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const owner = await identity(request, 'owner')
  const peer = await identity(request, 'peer')
  const headers = (token: string) => ({ authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id })
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, { headers: headers(owner),
    data: { metadata: { access_policy: 'full_access' } } })
  expect(created.ok()).toBeTruthy()
  const thread = await created.json()
  expect(thread.metadata.allowed_actions).toContain('terminal')
  expect(thread.metadata.allowed_actions).toContain('full_access')
  const path = `${apiUrl}/api/langgraph/threads/${thread.thread_id}`
  try {
    for (const child of ['/state', '/runs', '/messages', '/capabilities', '/workspace/tree',
      '/workspace/content?path=/workspace/private.txt', '/workspace/preview?path=/workspace/private.txt',
      '/workspace/zip', '/artifacts', '/images/content?path=/workspace/uploads/private.png',
      '/files/content?path=/workspace/uploads/private.pdf', '/terminals', '/dear/memory']) {
      expect((await request.get(`${path}${child}`, { headers: headers(peer) })).status(), child).toBe(403)
    }
    expect((await request.post(`${path}/runs/stream`, { headers: headers(peer), data: {} })).status()).toBe(403)
    expect((await request.put(`${path}/shares`, { headers: headers(owner),
      data: { user_id: fixture.users.peer, actions: ['read', 'comment', 'edit'] } })).ok()).toBeTruthy()
    const shared = await request.get(path, { headers: headers(peer) })
    expect(shared.ok()).toBeTruthy()
    expect((await shared.json()).metadata.allowed_actions.sort()).toEqual(['comment', 'edit', 'read'])
    expect((await request.patch(`${path}/access-policy`, { headers: headers(peer), data: { access_policy: 'full_access' } })).status()).toBe(403)
    expect((await request.post(`${path}/terminals`, { headers: headers(peer),
      data: { request_id: crypto.randomUUID(), acknowledge_execution: true } })).status()).toBe(403)
    expect((await request.delete(path, { headers: headers(peer) })).status()).toBe(403)
  } finally {
    expect((await fetch(path, { method: 'DELETE', headers: headers(owner) })).ok).toBeTruthy()
  }
})

test('service account needs an explicit project grant and project sharing, then revocation is immediate', async ({ request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const admin = await identity(request, 'superadmin')
  const owner = await identity(request, 'owner')
  const adminHeaders = { authorization: `Bearer ${admin}` }
  const ownerHeaders = { authorization: `Bearer ${owner}`, 'x-project-id': fixture.project_id }
  const account = await request.post(`${apiUrl}/api/service-accounts`, { headers: adminHeaders,
    data: { name: `Governance grant ${Date.now()}`, platform_roles: ['platform_viewer'] } })
  expect(account.ok()).toBeTruthy()
  const accountPath = `${apiUrl}/api/service-accounts/${(await account.json()).id}`
  const issued = await request.post(`${accountPath}/tokens`, { headers: adminHeaders, data: { name: 'fixture' } })
  expect(issued.ok()).toBeTruthy()
  const credentials = await issued.json()
  const serviceHeaders = { 'x-platform-api-key': credentials.plain_text_token, 'x-project-id': fixture.project_id }
  const created = await request.post(`${apiUrl}/api/langgraph/threads`, { headers: ownerHeaders, data: {} })
  expect(created.ok()).toBeTruthy()
  const path = `${apiUrl}/api/langgraph/threads/${(await created.json()).thread_id}`
  try {
    expect((await request.get(path, { headers: serviceHeaders })).status()).toBe(403)
    expect((await request.put(`${accountPath}/project-grants/${fixture.project_id}`, {
      headers: adminHeaders, data: { role: 'project_executor' }
    })).ok()).toBeTruthy()
    expect((await request.get(path, { headers: serviceHeaders })).status()).toBe(403)
    expect((await request.put(`${path}/shares`, { headers: ownerHeaders, data: { actions: ['read', 'comment'] } })).ok()).toBeTruthy()
    const shared = await request.get(path, { headers: serviceHeaders })
    expect(shared.ok(), `${shared.status()} ${await shared.text()}`).toBeTruthy()
    expect((await shared.json()).metadata.allowed_actions.sort()).toEqual(['comment', 'read'])
    expect((await request.delete(`${accountPath}/project-grants/${fixture.project_id}`, { headers: adminHeaders })).ok()).toBeTruthy()
    expect((await request.get(path, { headers: serviceHeaders })).status()).toBe(403)
    expect((await request.delete(`${accountPath}/tokens/${credentials.token.id}`, { headers: adminHeaders })).ok()).toBeTruthy()
    expect((await request.get(path, { headers: serviceHeaders })).status()).toBe(401)
  } finally {
    expect((await fetch(path, { method: 'DELETE', headers: ownerHeaders })).ok).toBeTruthy()
  }
})

test('platform viewer can read global model inventory but cannot create users or enter project governance', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  await login(page, 'viewer')
  await expect(page).toHaveURL(/\/workspace\/overview$/)
  await page.goto(`${webUrl}/workspace/models`)
  await expect(page.getByRole('heading', { name: '全局模型连接', exact: true })).toBeVisible()
  const viewer = await identity(request, 'viewer')
  const headers = { authorization: `Bearer ${viewer}` }
  expect((await request.get(`${apiUrl}/api/runtime/platform-models`, { headers })).ok()).toBeTruthy()
  expect((await request.post(`${apiUrl}/api/users`, { headers,
    data: { username: `denied-${Date.now()}`, password }
  })).status()).toBe(403)
  await page.goto(`${webUrl}/workspace/projects/${fixture.project_id}/thread-governance`)
  await expect(page).toHaveURL(/access-unavailable/, { timeout: 30_000 })
})

test('project editor can create private threads but cannot edit project security policy', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const provisioner = await identity(request, 'provisioner')
  const adminHeaders = { authorization: `Bearer ${provisioner}` }
  const name = `editor-${Date.now()}`
  const created = await request.post(`${apiUrl}/api/users`, { headers: adminHeaders,
    data: { username: `governance-${name}`, password } })
  expect(created.ok()).toBeTruthy()
  const user = await created.json()
  expect((await request.put(`${apiUrl}/api/projects/${fixture.project_id}/members/${user.id}`, {
    headers: adminHeaders, data: { role: 'project_editor' }
  })).ok()).toBeTruthy()
  await login(page, name)
  await page.goto(`${webUrl}/workspace/projects/${fixture.project_id}/thread-governance`)
  await expect(page).toHaveURL(/access-unavailable/, { timeout: 30_000 })
  const token = await identity(request, name)
  const headers = { authorization: `Bearer ${token}`, 'x-project-id': fixture.project_id }
  const access = await request.get(`${apiUrl}/api/projects/${fixture.project_id}/access`, { headers })
  expect(access.ok()).toBeTruthy()
  const permissions = (await access.json()).permissions
  expect(permissions).toContain('project.runtime.execute')
  expect(permissions).not.toContain('project.runtime.write')
  expect((await request.put(`${apiUrl}/api/projects/${fixture.project_id}/runtime-policies/graphs/00000000-0000-4000-8000-000000000001`, {
    headers, data: { is_enabled: true }
  })).status()).toBe(403)
  const thread = await request.post(`${apiUrl}/api/langgraph/threads`, { headers, data: {} })
  expect(thread.ok()).toBeTruthy()
  expect((await request.delete(`${apiUrl}/api/langgraph/threads/${(await thread.json()).thread_id}`, { headers })).ok()).toBeTruthy()
})

test('removing membership rejects new requests and clears both active browser tabs on focus', async ({ page, request }) => {
  const fixture = JSON.parse(readFileSync('/tmp/platform-governance-e2e.json', 'utf8'))
  const provisioner = await identity(request, 'provisioner')
  const peer = await identity(request, 'peer')
  const adminHeaders = { authorization: `Bearer ${provisioner}` }
  const peerHeaders = { authorization: `Bearer ${peer}`, 'x-project-id': fixture.project_id }
  const membership = `${apiUrl}/api/projects/${fixture.project_id}/members/${fixture.users.peer}`
  await login(page, 'peer')
  const other = await page.context().newPage()
  const url = `${webUrl}/workspace/projects/${fixture.project_id}/chat`
  try {
    await page.goto(url)
    await expect(page.getByRole('heading', { name: '请选择一个对话智能体' })).toBeVisible({ timeout: 30_000 })
    await other.goto(url)
    await expect(other.getByRole('heading', { name: '请选择一个对话智能体' })).toBeVisible({ timeout: 30_000 })
    await expect(page).toHaveURL(url)
    await expect(other).toHaveURL(url)
    expect((await request.delete(membership, { headers: adminHeaders })).ok()).toBeTruthy()
    expect((await request.post(`${apiUrl}/api/langgraph/threads`, { headers: peerHeaders, data: {} })).status()).toBe(403)
    for (const tab of [page, other]) {
      await tab.bringToFront()
      await tab.evaluate(() => window.dispatchEvent(new Event('focus')))
      await expect(tab.getByText(/^(当前页面权限已失效|无法访问此页面)$/)).toBeVisible({ timeout: 30_000 })
      await expect(tab.locator('.pw-chat-page-shell')).toHaveCount(0)
    }
  } finally {
    const restored = await fetch(membership, { method: 'PUT', headers: { ...adminHeaders, 'content-type': 'application/json' },
      body: JSON.stringify({ role: 'project_executor' }) })
    expect(restored.ok).toBeTruthy()
    await other.close()
  }
})
