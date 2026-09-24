# 04 前端交接：Dear Agent 记忆页

## 目标、负责人和当前可用性

**后端与 Runtime 相关代码已完成本地实现与隔离 PG/真实 HTTP 验证；本篇为经过技术审查修正后的前端唯一实施规范，指导 `platform-web` 记忆页重构、分享隐私提示补齐、孤儿代码清理及单元/组件测试落地。**

这是一份可独立阅读的前端实施与交接说明。准确 JSON/类型/错误码以 [03 公开契约](03-platform-api-contract.md) 为准，设计理由和源码对照见 [01](01-source-and-boundaries.md)。

### 交接与实施状态表（不得将“拟开发”标成“已交付”）

| 能力 | 本轮状态 | 前端实施与联调验收要求 |
|---|---|---|
| 旧线程 GET/POST memory | 后端路由兼容保留；前端即将切离旧路由 | 前端全面切至无线程接口，不再调用旧线程路由 |
| 新无线程 GET/POST | 本地已实现；真实 HTTP→Runtime→隔离 PG 通过 | 前端 `memory.service.ts` 对接 `/api/langgraph/dear/memory` |
| MemoryView scope/status/limits/counts | 本地已实现；ready 与 disabled 有自动测试 | 前端完整处理 `ready` / `disabled` / `read-only` / `empty` 四态 |
| quote/source_kind/source_call_id | 投影已实现；主用户输入、本人同 run 队列、手动和工具来源可区分 | 候选与事实卡片展示原文引用、来源类型及会话跳转 |
| 提取状态及错误/维护原因 | 本地已实现；独立 MAOMAO 模型候选提取通过，过期 running 投影为 interrupted | 前端实现提取状态栏、`pause_reason` 提示与 `running` 静默轮询 |
| source/revision/epoch 一致性 | 隔离 PG 中 CAS、去重、取消回滚、并发 run 和逐来源 quote 已测 | 前端实现 `expected_revision` CAS、409 冲突保留草稿与 `scopeGeneration` 防竞态 |
| 导入去重计数/采纳替换 | 本地已实现，隔离 PG 测试通过 | 前端实现文件/文本双模导入预览、fresh GET 导出及候选替换已有事实 |
| 页面、分享提示、孤儿清理、测试 | **方案已审查确认，待执行代码实施** | 完成 `F01—F07` 实现与单测/E2E 验证证据 |

前端据当前 OpenAPI 和 03 的契约直接实施；后端本地验证见 [verification.md](verification.md)。

## 1. 用户要完成的事

页面位置保持 `/workspace/projects/:projectId/dear-agent-memory`（实际父路由前缀以 `routes.ts` 为准），路由名 `workspace-dear-agent-memory`。数据归属是**当前登录用户＋当前项目**，同项目 Dear 新会话共享，其他用户/项目不共享。

页面标题建议“我的记忆”，副标题“仅用于你在「项目名称」中的 Dear Agent 会话”。从旧页面彻底移除作为前提的“关联会话”选择器和“先创建研究会话才能启用记忆”。引用来源会话仍可查看，它不是存储容器。

两个主视图：已生效事实、待确认候选。手工新增直接生效；自动提取默认关闭，开启后只生成候选。候选必须有人采纳才进入后续记忆注入。即便采纳，记忆也不能改变工具权限或代表外部操作批准。

沿用当前权限体系，读取对应 `project.runtime.read`、本人记忆写入对应 `project.runtime.execute`，并结合服务端 `capabilities.can_write`（只读横幅必须准确提示 `project.runtime.execute` 或服务端只读限制，修正旧代码中误写为 `project.runtime.write` 的文案错误）；不得要求管理员角色。

共享会话不使用个人记忆：自动注入、记忆查询/管理工具、自动提取全部关闭；这不影响用户在无线程记忆页面管理自己的事实。分享私有会话时必须在共享弹窗（`ThreadAccessControl.vue` 的 `mode === 'share'` 安全说明区）明确提示：**“共享会话将自动停用个人记忆；但分享包含历史回答，回答中已经出现的个人信息仍对共享成员可见”**，不能承诺自动移除历史个人信息。

提取最多两次尝试，共用 180 秒模型预算，可能在答案输出后继续等待 run 完成；不提示“已在后台自动补偿”，不因答案已输出而判定候选处理已结束。自动召回存储故障时普通对话继续，但记忆页及显式记忆操作仍正常显示错误；不得以模型继续回答推断记忆已成功读取。

## 2. 我们已有哪些代码，你需要在哪里改

根目录：`apps/platform-web/`，以下为经代码库核查确认的真实改动路径：

```text
src/
├── router/routes.ts                                    # 保持 memory 页面路由，核对来源跳转workspace-dear-agent
├── modules/dear-agent/
│   ├── pages/DearAgentMemoryPage.vue                   # 核心改造：切无线程、MemoryView、状态栏、候选替换、导入导出
│   ├── pages/DearAgentMemoryPage.spec.ts               # 核心改造：覆盖 ready/disabled/409/竞态/候选替换/导入导出等交互测试
│   ├── composables/useDearGovernanceContext.ts         # 🗑️ 删除孤儿代码（全仓仅旧记忆页引用，Skills页早已切离）
│   └── composables/useDearGovernanceContext.spec.ts    # 🗑️ 随孤儿 composable 一并删除
├── modules/chat/components/
│   ├── ThreadAccessControl.vue                         # 补充 mode==='share' 时的个人记忆停用与历史回答隐私提示
│   └── ThreadAccessControl.spec.ts                     # 补充共享提示文案断言
├── services/dear-agent/
│   ├── memory.service.ts                               # 切 /api/langgraph/dear/memory，定义 MemoryView/MemoryCommand
│   └── memory.service.spec.ts                          # 新路径、payload（含 replace_fact_id）、真实嵌套错误包测试
├── services/http/client.ts                             # 复用登录/续期/请求封装
├── composables/useWorkspaceProjectContext.ts           # 替换 useDearGovernanceContext，直接获取当前项目上下文
├── composables/useAuthorization.ts                     # 现有权限展示（can('project.runtime.execute', projectId)）
├── utils/http-error.ts                                 # 复用现有嵌套 error.code/request_id 解析，补充 details 提取辅助
└── components/base/
    ├── BaseDialog.vue                                  # 替换手搓弹窗
    └── ConfirmDialog.vue                               # 替换 window.confirm 删除确认与清空确认
e2e/dear-agent-memory.spec.ts                           # 浏览器 E2E 验收测试
```

**代码库核查修正说明：**
1. `useDearGovernanceContext.ts` 经全仓检索确认，除旧 `DearAgentMemoryPage.vue` 外再无任何组件引用（`DearAgentSkillsPage.vue` 早已使用 `useWorkspaceProjectContext.ts`）。记忆页移除依赖后，必须将 `useDearGovernanceContext.ts` 及其 `.spec.ts` 一并删除，避免遗留孤儿死代码。
2. `utils/http-error.ts` 内部的 `extractEnvelopeFields` 与 `unwrapPlatformHttpError` **已经原生支持**解析 `{ request_id, error: { code, message } }` 嵌套结构。禁止在页面内裸写 `err.response?.data?.code` 或另起炉灶重复造解析器；直接在 `http-error.ts` 中导出同步错误提取函数（并补充 `error.details` 透传以支持 422 字段定位）供 `memory.service.ts` 和页面统一调用。

## 3. 前端可以借鉴 deer-flow 哪段

以下参考路径以本地 deer-flow 仓库根目录为起点。

| 参考代码 | 学习点 | 本页面如何使用 |
|---|---|---|
| `frontend/src/components/workspace/settings/memory-settings-page.tsx:MemorySettingsPage` | loading/error/empty 的分支；事实卡、来源与操作组 | Vue 模板分状态渲染，不移植 React 组件 |
| 同文件 `handleExportMemory` | Blob、下载文件名、`URL.revokeObjectURL` | 导出当前完整有效事实数组；先 fresh GET，不导出搜索过滤结果 |
| 同文件 `handleImportFileSelection/handleConfirmImport/isImportedMemory` | 文件解析→验证→预览确认后提交 | 换成本项目 `FactInput[]` 严格校验（文件选择 + 文本预览双支持） |
| 同文件 `handleSaveFact/openEditFactDialog` | 表单草稿和提交 pending | 加项目快照和 CAS 处理；不照搬 confidence 字段 |
| 同文件 `filteredFacts` 与 `normalizedQuery` | 统一搜索入口 | 本地 `facts` 与 `candidates` 同口径筛选，`counts` 保持服务器全量 |
| `frontend/src/core/memory/hooks.ts:useMemory/useUpdateMemoryFact` | 成功响应更新数据，分离加载与写入 | 继续用 Vue ref/service，更新当前 scope 的 snapshot；不新增 React Query |

deer-flow 的摘要栏目、置信度、覆盖导入不是本期页面需求；不要为填满布局添加这些空壳栏目。

## 4. 接口接入示意

响应类型与命令契约与 [03](03-platform-api-contract.md) 完全同步。新方法签名去掉 `threadId`，所有写操作底层共用 `changeMemory`，并提供语义化的辅助方法。

```typescript
export async function readMemory(projectId: string, signal?: AbortSignal): Promise<MemoryView> {
  const { data } = await platformHttpClient.get<MemoryView>(
    "/api/langgraph/dear/memory",
    { headers: { "x-project-id": projectId }, signal },
  );
  return data;
}

export async function changeMemory(projectId: string, command: MemoryCommandPayload): Promise<MemoryView> {
  const { data } = await platformHttpClient.post<MemoryView>(
    "/api/langgraph/dear/memory",
    command,
    { headers: { "x-project-id": projectId } },
  );
  return data;
}
```

浏览器不向后端提交 `user_id`/`tenant_id`/`source`/`quote`；展示用 `user_id` 来自响应，项目名称来自 `useWorkspaceProjectContext()`。GET 返回新 envelope 后使用 `view.document?.facts` 和 `view.document?.candidates`。

`expected_revision` 一律取 `view.document.revision`，不能用单条 `fact.revision` 或 `epoch`。完整 action JSON 已在 03 第 5 节列出（`save` 新增/编辑、`delete`、`accept` 直接采纳或带 `replace_fact_id` 替换、`reject`、`settings`、`restore`、`clear`）。

## 5. 状态矩阵与按钮规则

| 状态 | 页面显示 | 按钮/请求与静默轮询规则 |
|---|---|---|
| 初次 loading | 骨架/加载说明，不显示“0 条已生效” | 禁止提交，允许取消导航 |
| 无当前项目 | 选择项目提示 | 不请求 memory，不创建线程 |
| 401 | 现有登录失效流程 | 不重复局部重试 |
| 403 | 当前项目记忆不可访问 | 不显示旧数据，不保留可提交表单 |
| GET 5xx/网络失败 | 获取失败＋重试＋`request_id`（有则显示） | 不能替换成空数组；保留旧快照时必须标过期且禁止写 |
| `status=disabled` | 当前环境未启用长期记忆治理（`RUNTIME_DEAR_GOVERNANCE_ENABLED`） | 独立 disabled 视图说明；不展示“0 条事实”，隐藏或禁用写操作 |
| `ready` 空库 | 尚无记忆，可手动记录或开启候选 | 有写权限即可新增，不要求先创建会话 |
| `ready` 只读 | 能浏览和导出，写操作禁用并展示只读说明 | `canWrite = can('project.runtime.execute', projectId) && view.status === 'ready' && view.capabilities.can_write` |
| `automatic_candidates=false` | 自动候选关闭；已有事实仍可引用 | 开关启用只改变提取，不清事实 |
| `extraction.running` | 正在整理候选，已有事实仍可管理 | 可手动刷新；后台开启**静默轮询（`silentFetchMemory`）**：每 3 秒一次、最多 210 秒停止。**静默规则：**①不置主 `loading=true` 防止列表闪屏；②当 `actionLoading===true` 时跳过当次轮询；③不清空正在编辑的弹窗草稿和未解除的 409 冲突提示；④在 `onScopeDispose`、`onDeactivated` 及切项目时立即停止定时器 |
| `no_candidates` | 最近一次对话没有值得长期保存的候选内容 | 不显示成提取失败 |
| `failed` / `interrupted` | 最近一次候选整理未完成（含 `error_code` 说明）；现有事实不受影响 | 允许手动刷新，不提供“后台重试”接口，不承诺下次 run 自动补偿 |
| `pause_reason` 非空 | 自动候选因配额维护暂停（区分 `candidate_limit` / `source_limit` / `tombstone_limit`） | 人工 CRUD/清理仍可用；引导用户清理待审候选或旧记忆，不自动 clear |
| 搜索无匹配 | 没有匹配的事实/候选 | 清搜索恢复全量；本地同时过滤 `facts` 和 `candidates`，顶部统计卡片保持服务器 `counts` 全量 |

不存在 SSE `memory_status` 事件，不等待未实现事件。轮询只做读，停止轮询不取消 run，也不说明后台任务完成。

## 6. 每个交互的操作顺序

### 6.1 新增/编辑与日期时区规范

1. 打开表单时记录当前 `projectId` 与 `editingFact`（若有）。
2. **Unicode 字符计数**：必填 trim 后文本，长度校验统一使用 `Array.from(text.trim()).length`（上限 `limits.fact_text_chars` 即 1000），避免 JS UTF-16 `.length` 把 Emoji 算成 2 个字符导致前后端不一致。
3. **日期与时区处理（防跨时区与过期 400 陷阱）**：
   - 后端 `memory.py` 要求 `expires_at` 必须是带时区的 ISO-8601 字符串，且**严格晚于服务端当前时间 `now()`**（否则抛 `400 invalid_memory_fact`）。
   - **编辑回显**：将已有 `fact.expires_at` 转换为**浏览器本地时区**的 `YYYY-MM-DD` 填入 `<input type="date">`（严禁直接对 UTC ISO 字符串 `.slice(0, 10)`）。同时记录初始本地日期串 `initialExpiresDate`。
   - **提交转换**：若编辑时用户未修改到期日期（`formExpiresAt === initialExpiresDate`），**原样保留** `editingFact.expires_at` 的原始 ISO 字符串；若用户新增或修改了日期 `YYYY-MM-DD`，按**本地时区当日结束时间** `new Date(year, month - 1, day, 23, 59, 59, 999).toISOString()` 转换，并在表单上注明“按本地时区当日 23:59:59 到期”，同时 `<input type="date">` 设置 `min` 为本地今日日期。
4. 提交时禁用重复点击；成功用响应的 `MemoryView` 替换本地状态、关闭弹窗、提示成功；失败保留草稿。

### 6.2 候选审核、来源跳转与替换现有事实（`replace_fact_id`）

1. 每条候选显示：`text`、`category`、`quote`（原文证据；若 `quote` 为空则显示“历史记录缺少原文”，不伪造证据）、`created_at`、`expires_at`、`source_kind`（`management` 显示“手动记录”，`user_message` 显示“对话提取”，`tool` 显示“会话工具记录”，`legacy` 显示“历史记录”）。
2. **来源会话跳转**：当 `source_thread_id` 非空时提供“查看来源会话”按钮，通过 `router.push({ name: "workspace-dear-agent", params: { projectId: activeProjectId.value, threadId: source_thread_id } })` 命名路由导航，不手拼 URL，也不拼接未实现的 message 锚点。
3. **三动作审核（直接采纳 / 替换已有事实 / 拒绝）**：
   - **直接采纳**：调用 `acceptMemoryCandidate(projectId, expectedRevision, candidate.id)`。
   - **替换已有事实…**：当当前生效事实列表 `facts.length > 0` 时展示该按钮，点击后弹出/展开替换确认框，由用户明确选择要被替换的某条现有 `fact`，确认后调用 `acceptMemoryCandidate(projectId, expectedRevision, candidate.id, replaceFactId)`。
   - **拒绝**：调用 `rejectMemoryCandidate(projectId, expectedRevision, candidate.id)`。

### 6.3 删除/清空确认（统一使用标准 Dialog）

1. **删除单条事实**：废弃原生 `window.confirm`，使用 `ConfirmDialog` 或 `BaseDialog` 展示待删除事实的文本预览，确认后发送 `delete` 命令。
2. **清空记忆**：确认弹窗明确提示：“将删除你在当前项目中的全部生效事实和待确认候选，同时关闭自动候选推断；历史聊天记录不会被删除。”（严禁写成“清空项目所有人的记忆”，也不向用户暴露内部术语 `epoch`）。即便 `facts` 为 0 但 `candidates` 非空或 `automatic_candidates` 开启时，也应允许执行清空重置。

### 6.4 文件导入导出（双模导入预览 + Fresh GET 导出）

1. **导出 JSON**：
   - 点击“导出 JSON”按钮（具有 `can_read` 即可导出，只读用户也可导出），先调用一次 `readMemory(activeProjectId)` 获取最新全量快照（不导出本地搜索过滤后的子集）。
   - 将 `view.document.facts` 投影为便携数组 `[{ text, category, expires_at }]`，生成 `Blob` 下载为 `dear-memory-YYYYMMDD.json`，完成后立即调用 `URL.revokeObjectURL`。
2. **追加导入 JSON**：
   - 支持**选择 `.json` 文件**（隐藏 `<input type="file" accept=".json,application/json">`）并在导入弹窗中同时支持粘贴/查看 JSON 文本。
   - **前端严格前置校验**：
     - 字节体积不超过 `limits.request_bytes`（`1,500,000` UTF-8 bytes）；
     - 顶层必须是非空 JSON 数组，条数 `1..100`（且结合当前已有 `facts.length` 提示是否会超出 100 条容量上限）；
     - 逐项校验：`text` 必须为 string 且 trim 后 `1..1000` Unicode 字符；`category` 缺省为 `"preference"`，若提供则**必须严格等于 `"preference"` 或 `"fact"`**（严禁把非法分类静默转成 `"preference"`）；`expires_at` 缺省或 `null`，若提供则必须为带时区的合法 ISO 时间字符串且晚于当前时间。
   - **导入预览面板**：在弹窗内实时汇总并展示 **有效条数 / 本地与现有库或文件内重复条数 / 校验错误条数（精确定位到第 N 条及错误原因）**，明确标注“追加导入，不覆盖现有事实”。
   - 存在任何校验错误或有效条数为 0 时禁止点击提交；提交成功后，严格依据后端返回的 `view.mutation.added` 和 `view.mutation.skipped` 显示成功提示（如：`成功追加 X 条事实，跳过 Y 条重复项`）。

### 6.5 冲突与错误取值

1. 统一使用 `utils/http-error.ts` 提取 `code`（对应 `err.response?.data?.error?.code`）、`message`、`requestId` 和 `details`（422 字段校验详情）。
2. **409 `memory_revision_conflict`**：
   - 保留用户当前打开的弹窗草稿（不关闭弹窗、不清空输入）；
   - 设置独立的冲突警告状态 `conflictWarning`（“⚠️ 数据已被其他操作更新，已为您同步最新列表，请核对草稿后再次点击保存”）；
   - 自动调用一次刷新拉取最新 `MemoryView`（更新 `expected_revision`），且此次刷新**不得清除 `conflictWarning`**；若刷新本身也失败，则禁用提交按钮并提供重试刷新入口，严禁拿旧 `revision` 再次提交。
3. **409 其他业务码**：
   - `memory_duplicate_fact`：提示与现有事实重复，引导直接编辑已有条目；
   - `memory_capacity_exceeded`：提示已达 100 条上限，请先清理旧事实或候选；
   - `memory_expired`：提示该候选已过期，并刷新列表；
   - `memory_maintenance_required`：提示自动提取配额已满，请先清理待确认候选或清空重置。
4. **写请求断网/503/504**：文案显示为“操作结果尚未确认，请刷新核对”，不自动重放写请求。

## 7. 项目切换与响应竞态约定

每次切换 `activeProjectId` 时递增页面级 `scopeGeneration`，立即通过 `AbortController` 中止上一次未完成的 GET 请求，停止后台静默轮询定时器，清空旧项目的 `memoryView` 快照、错误提示、冲突警告及所有打开的弹窗草稿，并立即发起新项目的 `fetchMemory()`。

请求发起时捕获当时的 `reqProjectId` 与 `reqGeneration`；**无论是 GET、静默轮询还是 POST 写操作**，响应返回时只有满足 `reqGeneration === scopeGeneration.value && reqProjectId === activeProjectId.value` 才允许写入界面状态。若项目 A 的 POST 发出后用户切到了项目 B，A 的响应会被前端安全丢弃，不会污染项目 B 的视图。

不新增按项目持久化的浏览器事实缓存，不将记忆/`quote` 写入 `localStorage`。

## 8. Mock 场景与组件测试交接

单元测试与组件测试统一使用 03 的 `MemoryView` envelope 和真实 `{ request_id, error: { code, message, details } }` 错误包形状。

| 测试场景 | 输入变化 | 断言要求 |
|---|---|---|
| `ready_empty` | `revision=0`、无事实 | 新增按钮可用、无会话下拉框、无需 `createInitialThread` |
| `ready_readonly` | `capabilities.can_write=false` | 所有写按钮与自动候选开关均禁用，只读横幅显示正确权限说明，导出仍可用 |
| `disabled` | `status="disabled", document=null` | 显示未启用记忆治理独立说明，不出现“0 条事实”假空库 |
| `candidate_with_quote_and_replace` | 含 `quote`、`source_thread_id` 的候选及已有事实 | 显示原文引用、来源跳转；支持直接采纳、选择已有事实替换（传 `replace_fact_id`）、拒绝 |
| `conflict_nested_error` | HTTP 409 `error.code="memory_revision_conflict"` | 自动拉取最新 GET、弹窗草稿保留、冲突提示不被刷新冲掉、无自动重发 POST |
| `project_switch_out_of_order` | 项目 A/B GET 或 POST 反序 resolve | B 页面只显示 B 数据，旧项目晚到响应被丢弃 |
| `storage_error` | HTTP 503 `error.code="memory_storage_unavailable"` | 显示带 `request_id` 的错误与重试按钮，不渲染假空库 |
| `restore_duplicates_and_validation` | 非法分类/非字符串拦截；成功返回 `added=1, skipped=2` | 非法文件阻止提交并报出具体条目错误；成功时按服务端 `added/skipped` 提示 |
| `thread_share_privacy_notice` | `ThreadAccessControl.vue` 打开 `share` 模式 | 显示“共享会话自动停用个人记忆，但历史回答中已生成的个人信息仍对共享成员可见” |

## 9. 前端开发任务与验证门禁

- [x] **F01**：升级 `utils/http-error.ts`（补充 `details` 与同步解析导出）和 `services/dear-agent/memory.service.ts`（无线程 `/api/langgraph/dear/memory`、`MemoryView`、`replace_fact_id`），完成 `memory.service.spec.ts`。
- [x] **F02**：重构 `DearAgentMemoryPage.vue` 上下文（移除 `useDearGovernanceContext` 依赖并删除该孤儿文件，接入 `useWorkspaceProjectContext`）、实现 `ready`/`disabled`/只读/提取状态栏/`pause_reason`、`scopeGeneration` 防竞态与 `running` 静默轮询。
- [x] **F03**：实现事实新增/编辑弹窗（`Array.from` 字符计数、本地时区 `YYYY-MM-DD` 回显与 `23:59:59.999` ISO 转换、未改日期原样保留、409 冲突保留草稿与持久提示）。
- [x] **F04**：实现候选卡片（展示 `quote`、缺失原文降级文案、`source_kind`、命名路由跳转来源会话、直接采纳 / 替换已有事实 `replace_fact_id` / 拒绝）。
- [x] **F05**：实现 fresh GET 导出 JSON 与文件/文本双模追加导入（前置校验、重复与错误条目预览、服务端 `added/skipped` 计数展示）。
- [x] **F06**：使用标准弹窗替换原生 `confirm`，补齐 `ThreadAccessControl.vue` 共享会话隐私提示，完成 `DearAgentMemoryPage.spec.ts` 与 `ThreadAccessControl.spec.ts`。
- [x] **F07**：执行前端全套单测、类型检查与 Lint 门禁（16 条单测、typecheck、eslint 全部通过）。

前端验证命令（在仓库根执行）：

```bash
pnpm --dir "apps/platform-web" test:run "src/services/dear-agent/memory.service.spec.ts" "src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts" "src/modules/chat/components/ThreadAccessControl.spec.ts" --maxWorkers=1 --minWorkers=1
pnpm --dir "apps/platform-web" typecheck
pnpm --dir "apps/platform-web" exec eslint "src/modules/dear-agent/pages/DearAgentMemoryPage.vue" "src/services/dear-agent/memory.service.ts" "src/modules/chat/components/ThreadAccessControl.vue" "src/utils/http-error.ts"
```

## 10. 双方交接清单与状态

| 项目 | 当前值 |
|---|---|
| 后端版本与测试环境 | 本地工作区代码；Runtime 隔离 PG、Platform 真实 HTTP、独立 MAOMAO 模型测试已通过 |
| OpenAPI 与真实响应证据 | 本地 `response_model`/OpenAPI、409/422/413 管理 HTTP、503/504 adapter 证据见 `verification.md` |
| 前端方案状态 | 2026-09-24 已完成审查修正并落地实施 |
| 前端实现状态 | **已完成（`F01—F07` 代码、孤儿清理、16 条单测、typecheck、eslint 全部通过）** |

## 11. 历史排查归档说明（无需记忆页处理）

早期聊天页曾出现的 `Unsupported run.start fields: multitaskStrategy`（400 错误）已由 `src/modules/chat/run-actions.ts:platformCommand` 在转发 `run.start` 前剥离解决，不属于个人记忆模块范围，前端实施 `DearAgentMemoryPage` 时无需处理。
