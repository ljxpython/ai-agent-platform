# 03 菜单、页面、动作与权限刷新

## 目标

让用户能看到、能进入、能操作的范围与服务端授权一致，并处理无项目、切换、撤权和多标签页。依赖 02 的动作矩阵；不重新设计 UI 视觉体系。

## 方案设计

### 3.1 当前机制与推荐改动

菜单已经通过 `useNavigation()` 读取路由元数据，应继续复用。需要收敛的是 `guards.ts` 与 `useAuthorization.ts` 的 scope/all/any 判断，以及页面内部动作与数据加载规则，不建立独立菜单权限数据库。

建议由后端提供有效权限：项目沿用 `/api/projects/{project_id}/access`；平台可在 `/api/identity/me` 中增加只读权限集合（字段名待契约评审）。前端不根据角色名重新推导平台权限；后端每次操作仍独立授权，权限响应不能成为客户端持有的授权凭证。

角色控制动作资格；涉及具体资源时需要 owner/visibility 等安全展示字段或后端计算的对象 actions。项目级权限集合不能回答“能否删这条私有 Thread”。若采用 05 的隔离，需补对象动作响应，不能让前端自行猜管理员例外。

### 3.2 页面—动作—数据范围清单

下表覆盖当前 `apps/platform-web/src/router/routes.ts` 中的业务页面组；不是声称每个按钮已经动态验收。

| 页面/路由组 | 读取来源/现有权限 | 需要区分的动作 | 推荐边界 |
|---|---|---|---|
| overview | Agent、Thread，分别判断 assistant/runtime read | 打开会话、快捷创建 | 无权限卡片不发请求；无项目显示可操作空态 |
| projects / projects/new | `/api/projects`；创建为平台权限 | 创建、查看元数据、归档、恢复 | 治理项目列表与可工作项目区分 |
| projects/:projectId | 平台项目读 OR 项目成员读 | 接管、恢复管理员、成员、审计 | 能看详情不等于能看成员或对话 |
| projects/:projectId/members | project.member.read | 添加、改角色、移除 | project.member.write；最后管理员保护 |
| agents / agents/new / agents/:agentId | project.assistant.read/write | 新建、编辑、停用、删除 | executor 可读不能改；关联下拉依赖最小目录字段 |
| models (全局: `/workspace/models`，项目: `projects/:projectId/models`) | 平台读 `platform.model.read` / 项目读 `project.runtime.read` | 全局公共连接创建/改密/启停、项目私有连接 (BYOK) 创建/改密、项目选用与默认项、工具限制 | 全局公共连接由平台运维维护；项目私有连接 (BYOK) 由项目管理员在项目内自主录入与管理；前端复用 ProviderStationCard 统一视觉规范并按 scope 精准控制操作与脱敏展示 |
| graphs | 当前 project.runtime.read | 目录刷新、项目 Graph 限制 | 共享目录刷新与项目范围策略分别授权 |
| chat / dear-agent | 当前 project.runtime.read | 发消息、继续/审批、停止、删除、分叉、上传、终端、模式选择 | 02 动作权限 + 05 资源范围 |
| dear-agent-skills | 当前 project.runtime.read | 上传、编辑、启停、删除 | 复用后端 capabilities，明确项目/个人/系统来源边界 |
| dear-agent-artifacts | Thread/成果入口 | 预览、单文件下载、zip | 继承 Thread 权限；不能只保护成果列表 |
| dear-agent-memory | 当前 Thread 代理入口 | 创建、编辑、删除、导入/导出 | 按现有主体 scope；新无线程接口归记忆专项 |
| users / users/new / users/:userId | platform.user.read/create | 资料、状态、角色、密码分别授权 | 目标是超级管理员时增加保护 |
| announcements | 平台/项目 announcement.write 任一 | 列表、发布、编辑、删、变更归属 | 区分全局管理、项目管理和所有用户公告 feed |
| audit | 平台/项目 audit.read 任一 | scope 过滤与详情 | 筛选条件不改变主体的有效授权范围 |
| service-accounts | platform.service_account.read | 账号状态、平台角色、token、项目 grant | 高权限对象保护；grant 不与账号资料编辑捆绑 |
| control-plane | platform.config.read | 聚合资源卡片和链接 | 卡片依赖接口分别判断；一个权限不能代表全部子模块 |
| platform-config | platform.config.read | feature flags 写入 | platform.config.write，服务端独立判定 |
| system-governance | platform.config.read | 探针和 metrics | 公开健康检查不等于公开治理指标 |
| me / security | 本人身份 | 本人资料与密码 | 不授予平台用户管理权限；敏感响应不缓存到公共状态 |
| access-unavailable / not-found | 认证后的状态页 | 返回可访问页面 | 避免重定向死循环；不暴露无权资源详情 |

### 3.3 项目上下文的两个问题

1. `ProjectsService.list_projects()` 给平台治理角色全部项目，普通用户只返回其项目。`workspace.hydrateContext()` 默认取列表第一项；该项目可能只有元数据可见、没有实际使用权限。建议明确“治理列表”和“进入工作区”的资格，不能偷偷给管理员加成员角色解决空页面。
2. `listProjects()` 默认只拿前 100 条，`currentProject` 从这个列表查找。直接 URL 打开后续项目时，应按 ID 加载必要元数据和权限，或给工作区选择器分页搜索，不能把“不在第一页”解释为“无权限”。此项需要回归复现后确定最小修复。

### 3.4 权限生效与竞态示例

场景：李四在标签页 A 打开模型配置；管理员在 B 将其降为 executor。A 的旧按钮可能还在，但新保存请求必须被后端拒绝。前端收到具体授权拒绝后更新权限、清理失权内容，不自动重发保存。

推荐刷新时机：登录/退出、切换项目、本人权限变更完成、页面重新激活时立即刷新、收到明确权限失效响应；对持续前台页面每 60 秒刷新一次权限快照。60 秒只影响体验层的状态收敛，不替代每次 API 请求的即时后端判权；高风险提交仍以服务端实时结果为准。使用已有 sessionEpoch/accessEpoch 防止旧请求回写；必要时加入一次去重刷新，而不是每个按钮发请求。

同浏览器标签页可通过 storage 或 BroadcastChannel 通知“权限需刷新”，通知内容不是权限真相。另一设备的撤权不能靠这个通知保证；后端新请求仍按数据库判定。持续前台页面按 D10 每 60 秒刷新权限快照。

401、账号停用、项目权限不足和资源不存在应分别处理；不能把所有 403 都当退出登录，也不能把“资源已删”当角色变更。已显示、已下载的数据无法通过撤权追回。

Axios 与 Chat 官方 SDK/fetch/SSE 都是请求路径，不能只在 `client.ts` 加拦截器就宣布覆盖。已建立流是否主动断开、断开后 Run 是否继续，见 07。

### 3.5 RBAC 体验缺口与开户闭环

#### 无解释置灰

当前用户看到 Chat 输入框或“新对话”按钮不可用时，必须能回答“为什么、缺什么、下一步去哪”。推荐按状态提供明确文案：

| 状态 | 页面行为 | 示例文案/动作 |
|---|---|---|
| 未登录/会话失效 | 跳转登录并保留 returnTo | “登录后才能进入工作区” |
| 无项目成员资格 | 保留平台治理入口；Chat 空态 | “当前账号未加入此项目；切换项目 / 联系项目管理员” |
| 项目只读 | 允许读；写控件禁用并解释 | “当前项目为只读，无法发起对话；联系项目管理员” |
| executor 可执行但不能治理 | 输入/运行可用；模型、策略、终端按独立权限处理 | “可以运行已配置 Agent；不能修改模型和项目策略” |
| 账号停用或权限刚撤销 | 清理敏感页面状态并刷新上下文 | “权限已变化，请重新加载工作区” |
| Agent/Graph 当前不可用 | 显示资源状态和切换/联系路径 | “当前 Agent 已停用或未授权，请选择其他 Agent” |

Tooltip 不是唯一方案：禁用状态旁边需要可见说明或 Banner；移动端没有 hover 时必须有文本。`disabled` 只阻止交互，不能代替服务端授权。没有申请 API 时，不显示假的“申请加入”按钮，先提供真实的联系/切换路径。

#### 用户开户与项目授权

当前 `UserCreatePage.vue` 已提示“项目级权限仍需在项目成员页单独分配”，但创建成功后直接回到用户列表；原复盘指出的割裂仍然存在于操作闭环，而不是完全没有提示。推荐增加可选的“关联项目”步骤或创建完成交接：

- 创建 Test 时可选项目 A 和 `project_executor`；提交时后端依次创建用户、按调用者权限执行成员绑定，并返回每一步结果。
- 没有选项目时，用户仍可登录平台治理页；工作区显示无项目空态和下一步，而不是满屏无原因置灰。
- 超级管理员能不能跨项目批量绑定，取决于 D32 的显式权限；不能因为能创建用户就绕过 `project.member.write`。
- 用户创建成功但成员绑定失败时，不能静默吞错。推荐用户保留、绑定标记失败并提供重试；若选择整体回滚，必须证明事务边界和失败恢复，不能让前端猜。
- 批量开户、邀请链接和项目成员页复用同一后端授权服务，前端不直接写角色字段。

#### 运维默认入口、健康拨测与公共沙箱

平台运维默认首页可优先进入治理/健康视图；路由重定向只是体验，后端仍按权限保护探针和业务接口。健康拨测只有在能限制 Agent/Graph、数据、工具、额度归属和审计时才进入本期；不能拿普通 Chat 作为“运维拨测”。

公共沙箱不是默认解决方案。若建设，需要讨论默认加入、执行角色、模型费用、工具/终端、数据清理、对话可见性、退出和滥用限额；任何一项没有答案就应后置。无项目空态和明确引导成本更低。

#### D35：健康拨测到底测什么

“健康拨测”不是让运维拿自己的身份随便发一条业务对话，而是用受控的合成请求验证平台链路。可以分成两层：

1. **控制面健康检查：** 数据库、Platform API、Runtime Gateway、目录/队列、模型供应商连通性和关键配置是否可用；返回状态、延迟、错误码和 request id，不读取业务内容。
2. **受限能力探测（条件能力）：** 使用预先批准的 Agent/Graph、固定合成输入、固定模型和工具白名单，验证鉴权、模型调用、流式回执和基础执行链路；必须有独立探测主体、额度、超时、数据清理和审计，不能访问真实项目 Thread、个人记忆、文件或终端。

当前项目已有控制面和网关链路，但尚未证明存在安全的合成执行资源、费用归属和工具隔离。因此本期建议只复用已有系统探针/控制面状态，**不建设受限 Agent 拨测，也不把普通 Chat 当拨测**。只有出现明确的生产 SLO、上线前自动验收或故障定位需求，并完成资源白名单和审计设计后，才重新打开 D35。

#### 已修复文案回归

决策文档提到邮箱缺失曾显示“暂不可用”。当前 `UserMenu.vue` 已显示“未绑定邮箱”，本专项不重复修改；回归测试必须区分邮箱未绑定、账号停用、无项目、只读和无执行权限，防止以后统一 fallback 又把用户误导成账号失效。

### 3.6 讨论项

| 编号 | 问题 | 推荐 | 状态 |
|---|---|---|---|
| D09 | 全局模型管理是否从项目页面拆出 | 独立平台入口或明确平台 tab，复用组件；项目页只展示可选用能力 | 已确认 |
| D10 | 撤权后前端多久刷新 | 新请求立即受控；重新激活/切换/拒绝时立即刷新；持续前台页面每 60 秒刷新权限快照 | 已确认 |
| D11 | 无权按钮隐藏还是禁用 | 无关治理动作隐藏；用户可理解且可申请的动作禁用并说明原因 | 已确认 |
| D12 | 无项目用户落到哪里 | 总览空态提示申请加入；平台管理员仍可进入治理页 | 已确认 |
| D30 | 无项目/只读时控件如何解释 | 可见文案 + Banner + 切换/联系动作；移动端不能依赖 tooltip | 已确认 |
| D31 | 创建用户时是否允许初始化项目成员 | 可选第二步或完成后交接；不默认强制加入 | 已确认 |
| D32 | 用户创建与项目绑定权限 | 创建用户和写项目成员是两个权限；跨项目绑定需显式授权 | 已确认 |
| D33 | 用户创建成功、项目绑定失败如何处理 | 保留用户并标记绑定失败、可重试；事务结果必须明确 | 已确认原则 |
| D34 | 运维默认首页 | 治理/健康视图；保留显式进入业务项目的路径 | 已确认 |
| D35 | 是否做健康拨测 | 本期只保留控制面健康状态；受限 Agent 拨测后置，不能使用普通 Chat 代替 | 已确认本期后置 |
| D36 | 是否建设公共沙箱 | 不建设；使用无项目空态、开户交接和明确联系路径解决 onboarding | 已确认：本期不做 |

## 任务拆分

### Task C1：权限读取契约与上下文
- **改动内容：** 输出平台有效权限，收敛前端 evaluator、无项目和直接 URL 上下文。
- **代码位置：** `apps/platform-api/src/platform_api/modules/identity/schemas.py`、`service.py`；`apps/platform-web/src/services/identity/identity.service.ts`、`types/management.ts`、`services/auth/permissions.ts`、`router/guards.ts`、`composables/useAuthorization.ts`、`composables/useNavigation.ts`、`stores/workspace.ts`。
- **预期结果：** 前端不维护另一份平台角色权限映射；菜单/URL 相同 scope 下行为一致。
- **验证项：** `apps/platform-web/src/router/guards.spec.ts`、`routes.spec.ts`、`services/auth/permissions.spec.ts`、`stores/workspace.spec.ts`；补普通用户、仅平台角色、跨项目 URL、100 条以后项目场景。
- **状态：** `[x]` done，2026-09-22。profile permissions、60 秒/可见性/focus/403 刷新与失权清理已实现；布局定向单测及双标签真实撤成员链路通过（`/tmp/governance-focus-unit.log`、`/tmp/governance-tabs-browser-3.log`）。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 单测及跨文件真实浏览器链路已验证
  - [x] 本章任务状态已更新
  - [x] CONTEXT 已更新

### Task C2：页面动作与失权清理
- **改动内容：** 逐组映射上表页面动作、字段、依赖请求；补身份刷新与 Chat 请求错误路径。
- **代码位置：** `apps/platform-web/src/modules/` 下上述页面；`stores/auth.ts`、`stores/workspace.ts`、`services/http/client.ts`、`modules/chat/composables/useChatSession.ts`、`modules/dear-agent/composables/useDearAgentSession.ts`。
- **预期结果：** executor 正常执行、无治理按钮；撤权后内容失效；切换不串数据。
- **验证项：** 相关页面组件测试 + auth/workspace 测试；E2E 验证多标签页、直接 API 拒绝、旧响应不回写、无自动写重试。
- **状态：** `[x]` done，2026-09-22。平台模型入口、Thread 对象动作与共享/接管、两套会话失权断流及旧响应保护已实现；组件/会话测试和专项真实浏览器链路通过；独立管理员入口按原因/工单接管、结束、删除已验。随项目执行 Final，不代表独立发布。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 单测/契约及浏览器证据已执行
  - [x] 本章任务状态已更新
  - [x] CONTEXT 已更新

### Task C3：权限透明化与运维体验
- **改动内容：** 为无项目、只读、无执行权限、资源停用、撤权和账号停用提供可见解释、切换/联系路径；运维默认进入治理/健康视图。
- **代码位置：** `apps/platform-web/src/modules/chat/pages/ChatPage.vue`、`modules/overview/pages/OverviewPage.vue`、`layouts/WorkspaceLayout.vue`、`router/routes.ts`、`components/layout/UserMenu.vue`；后端返回的项目状态/权限字段。
- **预期结果：** 不再出现无原因的置灰；运维不会被误导为账号失效；直接 URL 仍由守卫和后端拒绝。
- **验证项：** 组件测试覆盖身份/项目/资源四类状态；Playwright 覆盖运维登录、无项目/只读项目、移动端无 hover、权限撤销后重访。
- **状态：** `[x]` done，2026-09-22。无项目运维默认治理首页及独立目录同步、无权说明和只读入口已实现；控制面组件 2 项、390×844 移动端真实目录同步/拒绝执行及 viewer 模型只读浏览器链路通过。D35 拨测后置，D36 不建设公共沙箱。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 组件与移动/桌面真实链路已验证
  - [x] 本章任务状态已更新
  - [x] CONTEXT 已更新

### Task C4：用户开户与项目成员初始化
- **改动内容：** 设计用户创建后的可选项目绑定/完成交接，复用项目成员授权服务，明确跨项目授权、失败事务、审计和重复提交。
- **代码位置：** `apps/platform-web/src/modules/users/pages/UserCreatePage.vue`、用户 service/contracts/router、项目成员 service/router；不在前端直接写角色。
- **预期结果：** 新用户可明确知道自己有哪些项目；绑定失败不会静默产生“平台幽灵”。
- **验证项：** 创建不绑定、绑定一个项目、权限不足、绑定失败、重复提交、绑定审计；后端仍拒绝跨项目越权。
- **状态：** `[x]` done，2026-09-22。可选成员绑定和独立重试已实现；组件及真实浏览器开户→无项目拒绝执行→单次绑定故障→独立重试→原令牌立即可执行通过（`/tmp/governance-onboarding.log`，1 passed）。绑定故障为浏览器注入 503，创建、重试和授权走真实 API。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 组件与开户链路验证已执行
  - [x] 本章任务状态已更新
  - [x] CONTEXT 已更新

### Task C5：受限健康拨测（条件任务）
- **改动内容：** 本期不建设 Agent/Graph 受限拨测，仅确认已有控制面探针的权限和展示；未来只有在 D35 重新批准且完成费用、数据、工具、清理和审计设计后实现。D36 公共沙箱明确 deferred。
- **代码位置：** Platform 健康入口、受控网关接口和前端治理视图；不得直接开放普通 Chat 全局执行。
- **预期结果：** 当前运维可查看受保护的系统健康状态；未来若启用拨测，运维能验证指定能力，但不获得隐式项目内容权限或无限额度。
- **验证项：** 资源白名单、无业务数据、工具/终端限制、审计、费用归属和回滚。
- **状态：** `[ ]` 本期 deferred；仅保留控制面健康状态核对。

## 验证要求与记录

### Phase 验证记录

C1—C4：早期前端 295 passed / 1 skipped，typecheck/build 通过；WorkspaceLayout 与 UserCreatePage 有刷新、失权清理、绑定失败重试测试。F2 的 Chat ACL 改动另有 12 项定向测试通过（2026-09-22）。最新已实现范围联合回归为 83 个文件、307 项通过、1 项跳过（不计通过），耗时 224.64 秒；最新 typecheck 通过，证据 `/tmp/governance-implemented-web-regression.log`、`/tmp/governance-latest-types.log`。

续实施 Phase（2026-09-22）：共享面板和两套会话 composable 定向 12 项通过（`pnpm exec vitest run src/modules/chat/components/ThreadAccessControl.spec.ts src/modules/chat/composables/useChatSession.spec.ts`，日志 `/tmp/governance-refresh-both.log`）；覆盖两套会话持续前台撤权后隐藏内容/断流、离开项目成员仅可撤销、共享读取失败不能写旧授权。此前两套页面组合测试 16 项通过，两组有重叠。`vue-tsc --noEmit` 通过；不作为浏览器 E2E 或 Final。

2026-09-22 C3 目录入口：`pnpm exec vitest run src/modules/control-plane/pages/ControlPlanePage.spec.ts`，2 项通过；明确选择同步项目后调用既有目录接口，当前业务工作区保持未选择，平台只读者隐藏写动作。日志 `/tmp/governance-catalog-ui.log`；类型检查通过。

Phase 已通过专项 9 项真实链路及另行追加的双标签撤权 1 项（26.5 秒，`/tmp/governance-tabs-browser-3.log`）：成员撤销后新请求立即 403，两页激活后隐藏聊天内容。为此补齐 `WorkspaceLayout.vue` 的 window focus 监听及卸载；对应单测 1 项通过。专项涵盖无项目运维、只读者、编辑者、执行者、管理员、开户失败重试，仍不能把分批 Phase 结果写成整组 Final。

### Final 验证记录

已完成，跨专题 Final 统一见 [07](07-implementation-and-verification.md#final-验证记录)。

## 状态

done：C1—C4 实现及联合 Final 完成，见 07。多身份、移动端及双标签撤权均已有真实浏览器证据；D35 本期 deferred。
