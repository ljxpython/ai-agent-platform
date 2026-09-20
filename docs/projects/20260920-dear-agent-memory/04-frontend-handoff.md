# 04 前端交接：Dear Agent 记忆页

## 目标、负责人和当前可用性

**前端开发与浏览器验收由接手同事负责；本任务不实现 platform-web 页面、组件或前端测试。我们负责提供后端、Runtime、契约、联调支持与交接材料。**

这是一份可独立阅读的交接说明。准确 JSON/类型/错误码以 [03 公开契约](03-platform-api-contract.md) 为准，设计理由和源码对照见 [01](01-source-and-boundaries.md)。

### 交接状态表（不得将“拟开发”标成“已交付”）

| 能力 | 本轮状态 | 后端正式交接时补什么 |
|---|---|---|
| 旧线程 GET/POST memory | 代码已有；本轮未运行真实服务复验 | 可用环境、测试账号权限、实际响应 |
| 新无线程 GET/POST | 尚未开发 | 发布版本、OpenAPI URL/摘录、各 action 实测 |
| MemoryView scope/status/limits/counts | 尚未开发 | ready/disabled/read-only/empty 四组真实包 |
| quote/source_kind/source_call_id | 部分源字段已有；完整投影未开发 | 用户消息、手动、工具、历史四种示例 |
| 提取状态及错误/维护原因 | 尚未开发 | never/running/no_candidates/failed/interrupted 示例 |
| source/revision/epoch 一致性 | 已有基础实现，增强未开发 | 隔离、并发、删除防复活测试证据 |
| 导入去重计数/采纳替换 | 尚未开发 | mutation 实际返回；非法/重复/容量示例 |
| 页面、文件交互、组件测试 | **交给前端同事，未实施** | 前端负责人填写提交/测试/浏览器证据 |

在 B06 完成前，前端可以按草案制作 Mock，但不能用 Mock 成功宣称后端已可用。

## 1. 用户要完成的事

页面位置保持 `/workspace/projects/:projectId/dear-agent-memory`（实际父路由前缀以 routes.ts 为准），路由名 `workspace-dear-agent-memory`。数据归属是**当前登录用户＋当前项目**，同项目 Dear 新会话共享，其他用户/项目不共享。

页面标题建议“我的记忆”，副标题“仅用于你在「项目名称」中的 Dear Agent 会话”。从旧页面移除作为前提的“关联会话”选择器和“先创建研究会话才能启用记忆”。引用来源会话仍可查看，它不是存储容器。

两个主视图：已生效事实、待确认候选。手工新增直接生效；自动提取默认关闭，开启后只生成候选。候选必须有人采纳才进入后续记忆注入。即便采纳，记忆也不能改变工具权限或代表外部操作批准。

## 2. 我们已有哪些代码，你需要在哪里改

根目录：`apps/platform-web/`，以下均是已有路径；修改由前端同事执行。

```text
src/
├── router/routes.ts                          # 保持 memory 页面路由，核对来源跳转
├── modules/dear-agent/
│   ├── pages/DearAgentMemoryPage.vue          # 主要接入页面
│   ├── pages/DearAgentMemoryPage.spec.ts      # 补业务交互测试
│   └── composables/useDearGovernanceContext.ts # memory 不再用它找线程
├── services/dear-agent/
│   ├── memory.service.ts                     # 全部 HTTP 都在这里，不在页面裸 fetch
│   └── memory.service.spec.ts                # 新路径、payload、真实错误包测试
├── services/http/client.ts                   # 复用登录/续期/请求封装
├── composables/useWorkspaceProjectContext.ts # 当前项目
├── composables/useAuthorization.ts           # 现有权限展示
├── utils/http-error.ts                       # 现有工具不完整解析 error 对象，勿假设已支持
└── components/base/
    ├── BaseDialog.vue
    ├── ConfirmDialog.vue
    └── BaseDrawer.vue
e2e/dear-agent-memory.spec.ts                 # 拟新增，由前端同事负责
```

`useDearGovernanceContext` 如仍被别处使用不要删；仅移除记忆页依赖。当前 Skills 页面已无线程接入，可参照 `DearAgentSkillsPage.vue` 的项目上下文、基础弹窗组合，但不能顺带照搬它的竞态缺口。

## 3. 前端可以借鉴 deer-flow 哪段

参考根 `deer-flow/`。

| 参考代码 | 学习点 | 本页面如何使用 |
|---|---|---|
| `frontend/src/components/workspace/settings/memory-settings-page.tsx:MemorySettingsPage` | loading/error/empty 的分支；事实卡、来源与操作组 | Vue 模板分状态渲染，不移植 React 组件 |
| 同文件 `handleExportMemory` | Blob、下载文件名、URL.revokeObjectURL | 导出当前完整有效事实数组；先 fresh GET，不导出搜索结果 |
| 同文件 `handleImportFileSelection/handleConfirmImport/isImportedMemory` | 文件解析→验证→确认后提交 | 换成本项目 FactInput[] 验证；不能直接用 Deer UserMemory 校验 |
| 同文件 `handleSaveFact/openEditFactDialog` | 表单草稿和提交 pending | 加项目快照和 CAS 处理；不照搬 confidence 字段 |
| 同文件 `filteredFacts` 与 `normalizedQuery` | 统一搜索入口 | 本地 facts/candidates 同口径筛选，counts 保持服务器全量 |
| `frontend/src/core/memory/hooks.ts:useMemory/useUpdateMemoryFact` | 成功响应更新数据，分离加载与写入 | 继续用 Vue ref/service，更新当前 scope 的 snapshot；不新增 React Query |

deer-flow 的摘要栏目、置信度、覆盖导入不是本期页面需求；不要为填满布局添加这些空壳栏目。

## 4. 接口接入示意

**以下代码只作为交接写法，尚未修改仓库；响应类型从 03 同步。** 推荐新方法签名去掉 threadId，所有写操作共用 changeMemory，不为每个按钮复制 HTTP。

```typescript
export async function readMemory(projectId: string, signal?: AbortSignal): Promise<MemoryView> {
  const { data } = await platformHttpClient.get<MemoryView>(
    "/api/langgraph/dear/memory",
    { headers: { "x-project-id": projectId }, signal },
  );
  return data;
}

export async function changeMemory(projectId: string, command: MemoryCommand): Promise<MemoryView> {
  const { data } = await platformHttpClient.post<MemoryView>(
    "/api/langgraph/dear/memory", command,
    { headers: { "x-project-id": projectId } },
  );
  return data;
}
```

浏览器不向后端提交 user_id/tenant_id/source/quote；展示用 user_id 来自响应，项目名称来自现有项目上下文。GET 返回新 envelope 后使用 `view.document?.facts`，不是继续读 `response.facts`。

expected_revision 一律取 `view.document.revision`，不能用单条 fact.revision 或 epoch。完整 action JSON 已在 03 第 5 节列出，新增、编辑、删除、采纳、替换、拒绝、设置、恢复、清空都有示例。

## 5. 状态矩阵与按钮规则

| 状态 | 页面显示 | 按钮/请求 |
|---|---|---|
| 初次 loading | 骨架/加载说明，不显示“0 条已生效” | 禁止提交，允许取消导航 |
| 无当前项目 | 选择项目提示 | 不请求 memory，不创建线程 |
| 401 | 现有登录失效流程 | 不重复局部重试 |
| 403 | 当前项目记忆不可访问 | 不显示旧数据，不保留可提交表单 |
| GET 5xx/网络失败 | 获取失败＋重试＋request_id（有则显示） | 不能替换成空数组；保留旧快照时必须标过期且禁止写 |
| status=disabled | 当前环境未启用记忆 | 只显示说明；没有“开启服务器能力”按钮 |
| ready 空库 | 尚无记忆，可手动记录或开启候选 | 有写权限即可新增，不要求会话 |
| ready 只读 | 能浏览和导出，写操作禁用 | canWrite=本地权限 AND response.can_write |
| automatic_candidates=false | 自动候选关闭；已有事实仍可引用 | 开关启用只改变提取，不清事实 |
| extraction.running | 正在整理候选，已有事实仍可管理 | 可手动刷新；最多每 3 秒刷新一次、60 秒停止；离页/切项目停止 |
| no_candidates | 本次没有值得长期保存的内容 | 不显示成提取失败 |
| failed/interrupted | 本次未完成；现有事实不受影响 | 允许刷新，不提供不存在的“后台重试”接口 |
| pause_reason 非空 | 自动候选因维护暂停 | 人工 CRUD 仍可用；按文档引导维护，不自动 clear |
| 搜索无匹配 | 没有匹配的事实/候选 | 清搜索恢复全量；不修改全量 counts |

不存在 SSE memory_status 事件，不等待未实现事件。轮询只做读，停止轮询不取消 run，也不说明后台任务完成。新的 API 若只部分部署返回 404，应显示版本不匹配，不偷偷退回旧 thread 接口并创建会话。

## 6. 每个交互的操作顺序

### 6.1 新增/编辑

打开表单保存 scope 和 initial revision；必填 trim text、分类两种、可选本地日期。JS 字符计数避免将 UTF-16 length 当全部 Unicode 字符数，可用 `Array.from(text).length` 作提示，后端最终校验。编辑已有到期时间未更改时原样保留；改日期按本地当日结束转 ISO，展示用户时区说明。

提交禁用重复点击；成功替换 snapshot、关弹窗、显示成功。失败保留草稿。`can_write` 是展示辅助，提交遇 403 仍必须立即处理。

### 6.2 候选审核与来源

每条显示 text、category、quote、创建时间、到期时间、来源类型。quote 缺失显示“历史记录缺少原文”，不能生成假证据。提供采纳、拒绝；需要替换时由用户明确选当前 fact 后二次确认，提交 replace_fact_id。

source_kind=management 显示“手动记录”，tool 显示“会话工具记录”；只有可靠 source_thread_id 才可跳转。用已有 Dear 聊天路由生成链接；有 source_message_id 但页面没有消息定位能力时只打开线程，不拼未经实现的锚点，也不承诺精确定位。权限失效/线程删除时提示不可访问，不能因此删除记忆。

现有命名路由为 `workspace-dear-agent`，params为 `{projectId, threadId}`；对应子路径 `projects/:projectId/dear-agent/:threadId?`，优先用router命名导航，避免手拼父路由前缀。URL参数本身不证明权限，目标页请求仍走Platform授权。

### 6.3 删除/清空

删除确认展示当前事实预览。清空确认写清“删除当前用户在当前项目中的全部事实和候选，同时关闭自动候选；历史聊天不会被删除”。严禁写成“清空项目所有人的记忆”。服务端负责 epoch，UI 无需显示该术语。

### 6.4 文件导入导出

导出 fresh GET 的完整有效 facts，投影成 text/category/expires_at 数组；文件名建议 `dear-memory-YYYYMMDD.json`，不包含用户名/敏感项目名。只读有 can_read 也能导出。完成释放 object URL。

导入文件先按 request_bytes 校验、JSON.parse，再逐项验证，不强制 String、不把未知分类改成 preference；预览有效/重复/错误数量和“追加、不覆盖”。有错误则本次不能提交；重复提示仅供参考，最终按后端 mutation.added/skipped 显示。空数组拒绝，100 条上限，超容量提示先管理现有事实；导入正文不进入日志。

### 6.5 冲突与错误取值

正确位置为 `err.response?.data?.error?.code`，message/request_id 同样按 03 包结构读。现有 `utils/http-error.ts` 只识别顶层字符串，不能直接认为它能读嵌套对象；复用其基础 HTTP 处理时补小范围类型安全解析，不为记忆单独建一个全站错误框架。

409 conflict：保留原草稿→拉最新全量→显示“数据已更新，请核对后保存”→用户再次点击才写。fetchMemory 不能清掉独立的冲突提示。GET 刷新也失败时禁用提交，并允许重试读取；不能拿旧 revision 假装已刷新。

写请求断网：文案为“结果尚未确认，请刷新核对”，不是“保存失败，自动重试”。重复删除的 404 可以刷新确认，但不能将所有 404 一律当成功。

## 7. 项目切换与响应竞态约定

每次切 scope 增加本地 generation，中止前一次 GET，清除 snapshot、错误、旧弹窗和轮询。请求开始捕获 projectId/generation；**GET 和 POST 的结果**只有与当前 generation 相同才可落入界面。

AbortController 无法保证服务器停止已经接收的 POST；A 项目写入已经发出后切 B，A 可能成功，前端只保证不把 A 响应显示到 B、不把 A 草稿再次发送到 B。切换提示“已提交操作可能仍在原项目完成”，不能谎称已撤销。

不新增按项目持久化的浏览器事实缓存，不将记忆/quote 写 localStorage。响应用户变更由已有 HTTP session generation 保护，页面 scope generation 再保护项目变更。

## 8. Mock 场景与组件测试交接

Mock 应使用 03 的 envelope 和真实 `{error:{code}}` 形状，不再用顶层 code。建议用工厂从 ready 示例派生，避免四处复制不合法 fixture。

| fixture/测试建议名 | 输入变化 | 断言 |
|---|---|---|
| ready_empty | revision=0、无事实 | 新增可用、无需 createSession |
| ready_readonly | can_write=false | 所有写按钮与提交均禁止，导出仍可用 |
| disabled | document/counts/extraction=null | 不能出现“事实 0 条”暗示已读库 |
| candidate_with_quote | 一条 user_message 候选 | 原文与来源显示、未采纳不出现在 facts |
| conflict_nested_error | HTTP409 error.code=memory_revision_conflict | 新 GET 被调用、草稿保留、提示持久、无自动 POST |
| project_switch_out_of_order | A/B GET 反序 resolve | B 页面只出现 B 数据；A mutation 也同样测 |
| storage_error | HTTP503 error.code=memory_storage_unavailable | 重试按钮、没有假空库/假成功 |
| restore_duplicates | mutation added=1/skipped=2 | 显示服务端计数；不按原数组长度报成功 |
| invalid_import | 非法分类/非字符串/超量/过期 | 阻止提交并定位条目 |
| source_unavailable | 来源线程404/403 | 解释来源受限，不泄露其他会话 |

## 9. 前端同事的开发任务与验收

- [ ] F01：切新 service/type，读嵌套错误包；service 请求测试。
- [ ] F02：无线程页面上下文、状态矩阵、权限和 scope generation；无会话/反序响应测试。
- [ ] F03：事实表单、日期、CAS 草稿与冲突提示；保存失败及断网未知结果测试。
- [ ] F04：候选原文、来源、替换/采纳/拒绝；源不可访问测试。
- [ ] F05：导出、文件追加导入、预览、计数；往返和非法文件测试。
- [ ] F06：BaseDialog/ConfirmDialog、键盘焦点、switch label/aria-checked、窄屏与长文本。
- [ ] F07：真实 API 的浏览器 E2E，配合后端完成新会话模型引用、删除和隔离验收。

前端执行（在仓库根）：

```bash
pnpm --dir "apps/platform-web" test:run "src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts" "src/services/dear-agent/memory.service.spec.ts" --maxWorkers=1 --minWorkers=1
pnpm --dir "apps/platform-web" typecheck
pnpm --dir "apps/platform-web" exec eslint "src/modules/dear-agent/pages/DearAgentMemoryPage.vue" "src/services/dear-agent/memory.service.ts"
pnpm --dir "apps/platform-web" test:e2e "e2e/dear-agent-memory.spec.ts" --project=chromium --workers=1
```

最后一条需前端实现对应文件、启动测试栈、准备测试身份后才可运行。浏览器业务 E2E 禁止 mock memory HTTP；纯视觉/组件测试可以 mock。

## 10. 双方交接清单与状态

后端提供：B06 全部材料、变更版本、联调环境、非生产测试账号/项目、开关状态、OpenAPI、上述 fixture、错误样例、测试报告、已知限制（无 run 外后台恢复/无全局记忆/旧路由仍保留）。凭据通过现有安全渠道交接，不写文档。

前端接手时填写：负责人、开工日期、采用契约版本；完成后填实际 API 版本、测试命令/结果、浏览器证据、未完成项。字段不填就不能写“已交接完成”。

| 项目 | 当前值 |
|---|---|
| 后端版本与测试环境 | 待实施后填写 |
| OpenAPI 与真实响应证据 | 待 B01/B05/B06 |
| 后端可交接状态 | 未完成 |
| 前端接手人/接收日期 | 待指定 |
| 前端实现状态 | 未开始，由其他同事完成 |
| 联合验收 | 未执行 |

本轮完成的是交接文档设计，不是接口交付或页面交付；首轮旧页面 15 个 mock 测试通过记录见 verification.md，不适用于新接口验收。
