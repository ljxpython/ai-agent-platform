# 子专题03：工具界面美化 + 工具授权权限逻辑核查与补全

## 目标
1. 美化工具管理界面（目前在 `RuntimeModelsPage.vue` 的 tools tab）
2. 核查工具授权（enable/disable）权限逻辑是否正确只允许管理员操作

---

## 现状分析

### 工具界面现状（`RuntimeModelsPage.vue` - tools tab）

工具列表 tab（`tab === 'tools'`）和模型列表共享同一个页面，**没有专用的工具管理页**。需要检查工具列表的渲染逻辑。

工具相关的数据结构（`RuntimeToolPolicyItem`）：
```typescript
{
  catalog_id: string
  tool_key: string
  name: string
  source: string
  description: string
  sync_status: string
  last_synced_at: datetime | null
  policy: {
    is_enabled: bool
    display_order: int | null
    note: str | null
    updated_at: datetime | null
  }
}
```

**问题：工具列表缺少以下展示元素：**
- 工具状态可视化（is_enabled pill）
- tool_key 的 badge 样式
- description 截断展示
- sync_status 状态颜色区分
- 授权/撤权的操作按钮（toggle）

### 工具授权权限逻辑核查

**后端（`RuntimePolicyOverlayService`）：**

```python
def _require_project_access(self, *, actor, project_id, write: bool) -> UUID:
    permission = (
        PermissionCode.PROJECT_RUNTIME_WRITE  # 写操作
        if write
        else PermissionCode.PROJECT_RUNTIME_READ  # 读操作
    )
    self._policy_engine.require(actor=actor, authorization=AuthorizationRequest(...))
```

`upsert_tool_policy` 调用：`self._require_project_access(actor, project_id, write=True)`
→ 需要 `PROJECT_RUNTIME_WRITE` 权限

查看 `PermissionCode`：

```python
# platform-api/modules/iam/...
PROJECT_RUNTIME_WRITE = "project.runtime.write"
PROJECT_RUNTIME_READ = "project.runtime.read"
```

**前端（`RuntimeModelsPage.vue`）：**

```typescript
const canManage = computed(() => can("project.runtime.write"))
```

✅ **前后端权限码对齐**：`project.runtime.write` 已正确使用。

**关键问题：谁有 `project.runtime.write` 权限？**

需要查看 IAM 角色定义——这个权限是否只分配给了管理员（admin）角色：

- 如果项目成员（member）也有这个权限，那工具授权就不是"只有管理员才能操作"
- 需要查看 IAM 的角色权限矩阵

### IAM 角色权限核查结论（已查）

查看 `apps/platform-api/src/platform_api/modules/iam/application/policies.py`：

```python
# PROJECT_RUNTIME_WRITE 当前分配：
PermissionCode.PROJECT_RUNTIME_WRITE: frozenset(
    {ProjectRole.ADMIN, ProjectRole.EDITOR, ProjectRole.EXECUTOR}  # ⚠️ EXECUTOR 不应有写权限！
)

# 对比参考：
# PROJECT_ASSISTANT_WRITE: {ADMIN, EDITOR}
# PROJECT_MEMBER_WRITE: {ADMIN}
```

**⚠️ 问题发现：`PROJECT_RUNTIME_WRITE` 错误地包含了 `EXECUTOR` 角色！**

这意味着项目内任何能执行对话的用户（EXECUTOR）都可以修改工具授权策略，这**违反了"只有管理员才能触发和更改工具授权"的要求**。

**建议修复方案（需评审确认）：**
- 方案 A：`PROJECT_RUNTIME_WRITE` 缩减为 `{ADMIN, EDITOR}` —— 编辑者也应该能管理运行时配置，与 ASSISTANT_WRITE 对齐
- 方案 B：`PROJECT_RUNTIME_WRITE` 缩减为 `{ADMIN}` —— 只有项目管理员能改工具/模型授权
- 方案 C：拆分权限码：读写授权策略用新的 `project.runtime.policy.write`（仅 ADMIN），现有 `project.runtime.write` 收紧到 ADMIN+EDITOR

老王倾向**方案 A**，与 `PROJECT_ASSISTANT_WRITE` 设计对齐，EXECUTOR 只能读不能写配置。

### 工具授权是否真正生效的链路

```
前端 updateRuntimeToolPolicy(project, catalogId, {is_enabled: false})
  → PUT /api/projects/{project_id}/runtime-policies/tools/{catalog_id}
  → RuntimePolicyOverlayService.upsert_tool_policy()
  → 写入 DB tool_policies 表

运行时执行时：
  RuntimePolicyOverlayService.build_delegation_policy()
  → 查 tool_policies: 如果 is_enabled=false，该 tool 从 allowed_tool_names 移除
  → 注入给 runtime-service 的 delegation token
  
runtime-service:
  → 收到 delegation 里的 allowed_tool_names
  → 只允许这些 tool 被调用
```

✅ **工具授权链路完整**：禁用工具后，runtime-service 收到的 delegation token 里就没有该工具，执行时无法调用。

---

## 方案设计

### 工具界面美化

工具列表需要的改造（在 `RuntimeModelsPage.vue` 的 tools 渲染部分）：

#### 1. 卡片式工具列表

每个工具一张卡片，包含：
```
┌─────────────────────────────────────────────┐
│ [tool-key badge]  工具名称          [状态 pill]│
│ source: xxx                                  │
│ description 文字（最多2行，超出截断）          │
│ 最后同步：2026-09-18  sync_status: ready      │
│                           [授权] / [撤权]按钮 │
└─────────────────────────────────────────────┘
```

#### 2. 状态颜色区分

- `sync_status === 'ready'` → success 绿
- `sync_status === 'syncing'` → warning 黄
- `sync_status === 'error'` → danger 红

- `is_enabled === true` → "已授权"（绿色 pill）
- `is_enabled === false` → "已禁用"（灰色 pill）

#### 3. 授权切换操作

只有 `canManage`（project.runtime.write）的用户才显示操作按钮，切换时调用 `updateRuntimeToolPolicy`。

#### 4. 工具刷新按钮

刷新工具列表（从 runtime-service 同步），已有 `POST /api/runtime/tools/refresh` 接口，前端需要连接到刷新按钮。

### IAM 权限核查结论（实现前补充）

需要在开发前确认：`project.runtime.write` 是否仅限于项目管理员角色。如果普通成员也有，则需要讨论是否需要引入更细粒度的权限码（`project.runtime.policy.write`）。

---

## 待决策问题

> **Q1：工具管理是否需要从 RuntimeModelsPage 里拆出来，独立成 RuntimeToolsPage？**
>
> 当前两者都在一个页面的不同 tab，随着功能增多可能变重。建议评估：
> - 保留现有 tab 结构（简单，不破坏路由）
> - 拆成独立页面（更清晰，但改路由/菜单）

> **Q2：`project.runtime.write` 是哪些角色拥有？仅管理员（admin）还是成员（member）也有？**
>
> 这决定了工具授权操作的访问范围是否符合"只有管理员才可以触发和更改"的要求。
> 如果成员也有该权限，需要讨论是否收紧：改用 `platform.runtime.write` 或新增细粒度权限码。

> **Q3：工具刷新操作需要权限控制吗？目前 refresh 接口只检查 project.runtime.read 还是 write？**
>
> 需要核查后端 `refresh_runtime_tools` 里的权限逻辑，确保刷新操作不被普通用户随意触发。

---

## 任务拆分

- [x] Task 1：查 IAM 角色权限矩阵，发现并收紧 `PROJECT_RUNTIME_WRITE`（剔除 EXECUTOR，仅限 ADMIN + EDITOR）
- [x] Task 2：前端 `runtime.service.ts` 补充 `refreshRuntimeTools` API
- [x] Task 3：美化工具列表（卡片式 + 状态 pill + 操作按钮）— **文件：** `RuntimeModelsPage.vue`
- [x] Task 4：连接刷新工具按钮（调用 refresh 接口）— **文件：** `RuntimeModelsPage.vue`

---

## 验证要求与记录

### 验证要求
- [x] 工具列表以卡片形式展示，状态清晰
- [x] `project.runtime.write` 角色的用户能看到授权/撤权按钮
- [x] 无该权限的用户按钮不可见/不可操作
- [x] 工具刷新按钮正常触发同步
- [x] IAM policy 单元测试验证权限生效

### 验证记录
- 2026-09-18: 后端 `test_iam_policy_engine.py` 通过，前端卡片化重构及构建通过。

## 状态
done
