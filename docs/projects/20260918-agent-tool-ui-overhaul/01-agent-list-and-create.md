# 子专题01：Agent 管理列表页美化 + 创建 Agent 功能

## 目标
1. 修复 Agent 管理列表页（`AgentsPage.vue`）的 UI 问题（搜索按钮导致字体竖排等）
2. 补全"创建 Agent"入口（当前只有查看，没有创建操作）

---

## 现状分析

### 前端现状（`apps/platform-web/src/modules/agents/pages/AgentsPage.vue`）

**问题1：搜索按钮 layout 破坏**

```html
<input v-model="query" class="pw-input" placeholder="搜索名称"><BaseButton type="submit">搜索</BaseButton>
```

`<input>` 和 `<BaseButton>` 写在同一行没有空白分隔，`flex gap-3` 本身没问题，但 `pw-input` 宽度占满导致按钮被挤到很小，文字竖排。修复方案：`<input>` 加 `class="flex-1"` 限制扩展，或者给 input wrap 单独容器。

**问题2：没有创建 Agent 的入口**

- `PageHeader description` 写的是"自动展示已授权的智能体，无需手动创建"——这与实际能力不符
- 后端 `POST /api/projects/{project_id}/agents` 已存在，`CreateAssistantCommand` 支持 `graph_id`/`name`/`description`/`context`
- 前端 `AgentEditorPage.vue` 已有 `original` 为 null 时的"新建"分支逻辑（`graphId.value = graphs.value[0]?.graph_id ?? ""`），但 **save() 里 `if (agent) { ... }` 这个 if 没有 else 分支**，新建时保存逻辑根本不执行

**问题3：列表页表格风格平淡**

- 没有 avatar/图标区分 agent，没有状态 pill，操作列只有一个按钮
- 缺少"创建"按钮入口（PageHeader actions 区域空白）

### 后端现状（`platform-api`）

`POST /api/projects/{project_id}/agents` 接口完整，已有：
- 权限校验：`PROJECT_ASSISTANT_WRITE`
- 参数验证：`graph_id`/`name`/`description`/`context`
- `createAgent` 前端 service 里**没有对应的 `createAgent` 函数**，只有 `listAgents`/`getAgent`/`updateAgent`

---

## 方案设计

### 前端改动

#### 1. `AgentsPage.vue` 修复 + 美化
- 修复搜索区：input 加 `flex-1`，让按钮保持固定宽
- 增加 `PageHeader` actions slot：添加"创建 Agent"按钮（`can('project.assistant.write')` 控制显隐）
- 表格升级：
  - 名称列加 agent 头像字母圆圈（取 name 首字母）
  - 状态列换用 `StatusPill` 组件（active=success, disabled=warning）
  - 操作列：新增"编辑配置"按钮跳转到 editor 页

#### 2. `AgentEditorPage.vue` 补完新建逻辑
- `save()` 的 else 分支：调用 `createAgent(project, { graphId, name, description, context: nextContext })`
- 新建成功后跳转到详情页 `router.push(agentId)`
- PageHeader 标题：`original?.name || '新建 Agent'`
- Graph 选择：新建时可编辑（当前 `:disabled="!!original"` 是对的，不改）

#### 3. `agents.service.ts` 新增 `createAgent`
```typescript
export async function createAgent(projectId: string, input: CreateAgentInput): Promise<Agent> {
  const { data } = await platformHttpClient.post<Agent>(
    `/api/projects/${encodeURIComponent(projectId)}/agents`,
    input,
    scoped(projectId)
  )
  return data
}
```

---

## 任务拆分

- [x] Task 1：`agents.service.ts` 新增 `createAgent` 函数 + 类型 `CreateAgentInput` — **文件：** `src/services/agents/agents.service.ts`, `types.ts`
- [x] Task 2：`AgentsPage.vue` 修复搜索布局 + 表格升级 + 添加"创建"入口 — **文件：** `AgentsPage.vue`
- [x] Task 3：`AgentEditorPage.vue` 补全 `save()` 新建分支 — **文件：** `AgentEditorPage.vue`

---

## 验证要求与记录

### 验证要求
- [x] 搜索按钮文字不再竖排（input 添加 flex-1）
- [x] 有权限用户能看到"创建 Agent"按钮（基于 `can('project.assistant.write')`）
- [x] 创建表单必填校验正常（名称、Graph）
- [x] 创建成功后跳转到详情页
- [x] 无 `project.assistant.write` 权限的用户看不到创建入口

### 验证记录
- 2026-09-18: vitest 单元测试通过，TypeScript 编译通过，路由加载正常。

## 状态
done
