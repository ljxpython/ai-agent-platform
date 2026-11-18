# 08｜Agent 只保留会话转评测集，清理旧评测入口与实现

> 更新：2026-11-18｜状态：部分完成（partial）。7项任务中5项已完成、2项部分完成。Web/API旧入口、旧Runtime评测助手及远端旧助手派发已清理；两个转换入口、批量交付、幂等及真实执行者权限已验证。08当时的跨机运行阻塞已由09在独立Worktree解决；本专题真实多页与全栈回退仍待验，联合验收尚未全部通过。
> 类型：沿用原项目的治理增补。涉及 Web/API/Runtime 与 EvalFlow 的接口退役、旧任务调度和维护权限，不能按单页删除处理。
> 授权：用户已同意清理方案、EvalFlow在sshmy1现场修改/验证与必要重载、准确远端origin放行、最小依赖修复，以及本机准确出口IP和回环反向隧道的开发连接修复。另已批准创建一个仅属评测项目的专用执行者测试账号。HTTP无TLS及本机API/隧道持续在线的要求已明确告知。用户重申既定原则：已生成题库作为独立资产，来源授权到期后仍可使用。未授权删除业务数据、Git提交/推送、数据库降级或无关生产变更。

## 用户以后怎样操作

用户在 Agent 平台完成业务对话，需要把它变成以后可以重复验证的案例时，只使用两个入口：

1. **转为评测集**：提交当前会话，或历史列表勾选的一批会话。
2. **从历史会话建评测集**：沿用当前项目和 Agent，按时间、执行状态查找有权访问的历史会话，选中后进入同一个提交弹窗。

提交前继续确认资料用途。平台采集获准的会话、运行与可用环境资料，脱敏后异步交付 EvalFlow；用户收到完成或失败通知，从通知进入对应评测集。普通成员只交付资料，AI 用途仍由有权人员确认。提交不会发布题库或运行被测 Agent。

后续建题、AI 咨询与修订、候选采纳、手工编辑、发布、运行、比较、重评和诊断全部在 EvalFlow。Agent 不再展示“评测与改进”“让 AI 帮我改进”“评价回答”、合成复现和巡检授权操作，也不新增替代工作台。

### 保持不变的边界

- 只退役代码与产品入口，不删除历史反馈、授权、题库、运行、Trace、审计记录或数据库迁移；保留现有数据保护机制。
- 项目/会话 ACL、脱敏、用途确认、命令签名、幂等、撤权、停止、执行证据与通知继续生效；两入口不绕过这些校验。
- 保留 Chat 的正常对话、历史管理、轨迹/日志与可观测入口；它们不是旧评测工作台。
- 沿用现有配置和组件，不新增权限体系、题库副本、转换协议或通用适配层。
- 原01–07的交付和验证保留当时范围。本专题实施前，旧入口实际上仍存在，不能写成已下线。

## 代码核查结论与清理顺序

当前两个保留入口都由 `apps/platform-web/src/modules/chat/pages/ChatPage.vue` 接入 `SendSessionMaterials.vue`；历史选择由 `PickSessionMaterials.vue` 完成。后端为 `POST /api/evaluation/materials/sessions` 和 `POST /api/evaluation/materials/send`。转换代码复用 `workbench.forward`、用途授权和 EvalFlow 的工作项，不依赖旧前端客户端 `services/evaluation/workbench.ts`。

退役前旧页面使用“批准即验证”的交互，而当前 EvalFlow 的 approve 只发布，run 才执行。旧页还把 published 当作进行中，并以 approve 携带 source_task_id 请求重评。本次已移除旧操作界面，没有升级这套旧流程。

按以下顺序实施：前端退场及旧地址提示 → 关闭旧公开新建/写入路径 → 保留接口回归 → 只读盘点旧任务与 EvalFlow 调度 → 满足条件后删除旧 Runtime 助手 → 联合验收。条件未满足的任务保留未完成状态，不能把隐藏按钮等同后端退役。

### A. 本次删除的12个前端文件

以下文件的生产调用集中在旧工作台或回答反馈子树。删除时一并移除 import、模板、状态和引用测试，不保留空壳。

| 完整路径 | 删除理由 |
|---|---|
| `apps/platform-web/src/modules/evaluation/EvaluationPage.vue` | 旧需求创建、工作项列表和巡检汇总 |
| `apps/platform-web/src/modules/evaluation/EvaluationDetail.vue` | 旧方案、授权、发布运行和结果操作界面 |
| `apps/platform-web/src/modules/evaluation/CasePreview.vue` | 只由旧详情页使用 |
| `apps/platform-web/src/modules/evaluation/useWorkItem.ts` | 旧工作项轮询和动作状态 |
| `apps/platform-web/src/modules/evaluation/useWorkItem.spec.ts` | 随被删除的轮询实现退役 |
| `apps/platform-web/src/modules/evaluation/proposalDiff.ts` | 只用于旧页版本差异 |
| `apps/platform-web/src/modules/evaluation/proposalDiff.spec.ts` | 随旧差异实现退役 |
| `apps/platform-web/src/services/evaluation/workbench.ts` | 旧前端类型、动作客户端和展示映射 |
| `apps/platform-web/src/modules/chat/components/MessageFeedback.vue` | 评价、改进入口与合成复现交互 |
| `apps/platform-web/src/modules/chat/components/MessageFeedback.spec.ts` | 随回答反馈界面退役 |
| `apps/platform-web/src/modules/chat/components/InspectionConsent.vue` | 回答内巡检用途授权 |
| `apps/platform-web/src/modules/chat/components/InspectionConsent.spec.ts` | 随巡检界面退役 |

同时修改 `apps/platform-web/src/router/routes.ts`，移除旧菜单及页面加载。保留原列表/详情 URL 的最小迁移提示，不再渲染旧表单或发送旧操作请求；由受控 capabilities 返回 EvalFlow 地址，用户点击进入列表或同 itemId 详情。未配置地址、无权限或旧项不可读时明确提示，不自动创建、转换或修改历史项，不从 query 接受任意外部跳转地址。

`ChatMessageList.vue` 删除 MessageFeedback 接线及仅供它使用的 capabilities 请求、状态和 HTTP import；不改消息渲染、推荐问题和运行状态。

### B. 保留并局部修改的前端代码

| 完整路径 | 处理 |
|---|---|
| `apps/platform-web/src/modules/evaluation/components/SendSessionMaterials.vue` 及其 `.spec.ts` | 保留提交、用途确认、原请求重试、202后台回执与通知语义 |
| `apps/platform-web/src/modules/evaluation/components/PickSessionMaterials.vue` | 保留选择、分页、时间/状态筛选与20会话上限；移除“我的反馈”控件、feedback状态/请求字段和好差评标签，补充组件测试 |
| `apps/platform-web/src/modules/chat/pages/ChatPage.vue` | 保留两个入口及统一弹窗；结合现有 capabilities.workbench 和项目权限判断可用性，功能未启用时给出明确状态 |
| `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.vue` 及其 `.spec.ts` | 保留两个动作与各自显示条件 |
| `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue` | 保留批量“转为评测集”；显示条件与顶栏一致，不能绕过能力或权限限制 |
| `apps/platform-web/src/modules/notifications/utils/notification-action.ts` 及其 `.spec.ts` | 保留跨端口 EvalFlow 通知跳转，不改成已移除的 Agent 旧详情页 |

### C. Agent API 应删除的旧公开入口，和需裁剪的实现

下表保留接口退役目标与保留边界，所列裁剪已实施；实际验证及仍未通过的条件见任务8.3。废弃请求明确拒绝，不静默执行新转换，也不返回伪成功。

| 文件与位置 | 清理目标 | 必须保留的边界 |
|---|---|---|
| `apps/platform-api/src/platform_api/modules/evaluation/workbench.py`：GET `/work-items`、GET `/workbench-summary`、GET `/work-items/{item_id}`、POST `/work-items` | 删除只服务旧页面的列表、汇总、读取代理和手写需求创建处理 | 保留 forward、enabled、签名授权及回源检查；materials直接调用forward创建和读取回执，不走这些HTTP入口 |
| 同文件：POST `/work-items/{item_id}/{action}` | 缩减为 EvalFlow 实际使用的 grant/revoke；移除旧页 generate/revise/edit/approve/run/compare/dispute 等代理分支及其助手启动 | `eval_platform/authoring_api.py` 仍通过此路径授予/撤销用途；其他评测动作由 EvalFlow 自己执行，仍须向平台取得签名 |
| `apps/platform-api/src/platform_api/modules/evaluation/router.py`：GET/POST `/threads/{thread_id}/messages/{message_id}/feedback`，POST `/exports`、POST `/exports/{export_id}/deliver`，POST `/inspection/exports`、GET `/inspection/context`、GET `/inspection/exports` | 退役回答反馈、手写合成复现和巡检新提交/展示接口 | 不顺带删除 internal/export、internal/authorizations、internal/projection、source_access、check_purpose 或历史撤权处理 |
| 同文件：GET `/capabilities` | 只保留两个转换入口及旧地址迁移仍需要的字段；移除旧页专用模型查询和已退役功能声明 | 复用现有 workbench/authoring_url，不通过新增名称制造第二套开关；项目成员和项目范围检查保持有效 |
| `apps/platform-api/src/platform_api/modules/evaluation/materials.py` | 去除 SessionQuery.feedback、feedback_by_thread及好差评聚合/返回；其余按现有协议保留 | snapshot、privacy、后台任务、receipt、finish_conversion、通知、用途确认、成员权限和原请求恢复均保留 |
| `apps/platform-api/src/platform_api/modules/evaluation/service.py`、`contracts.py` | 随上述公开入口删除 read_feedback/save_feedback/create_export/create_inspection_export/read_inspection_exports 等无剩余调用的处理及专用请求模型；inspection_agent等辅助函数逐项核对后删除 | latest、authorize、digest、audit、授权包读取/锁、源反馈核对、投影回执与历史撤权仍有调用，不能整文件删；ProjectionBody和AuthorizationBatchBody仍被服务间回调使用 |

静态核查范围是本仓生产代码/测试与相邻 EvalFlow 代码，不能据此断言部署端没有外部调用方。实施时核对实际路由消费者；发现额外有效消费者，记录到本任务并先处理消费者，再删接口。

后端辅助函数的精确边界（2026-11-18补充核查）：

- `service.py`的`read_feedback`、`save_feedback`、`create_export`、`inspection_agent`、`create_inspection_export`、`read_inspection_exports`随对应旧接口退役；`public_event`仅由旧反馈读写使用，确认这些调用全部移除后同删。对应`FeedbackBody`、`ExportBody`、`InspectionExportBody`删除，`ProjectionBody`和`AuthorizationBatchBody`保留。
- `service.save_receipt`在本仓生产代码中只由旧`router.deliver`调用，随旧投递接口移除并迁移必要测试夹具后可删。它不是新会话转换的回执实现：`materials.py`自行构造`material_submission.receipt`并经`finish_conversion`完成交付。保留`save_projection`及历史数据库中的receipt字段和数据。
- `workbench.record_action`仍由保留的`item_action`授权分支调用，不能因旧创建接口删除而清理；`forward`、`reject_client_source_snapshots`和用于EvalFlow命令签发的操作映射也保留。删除的是旧HTTP代理分支，不是EvalFlow对应动作所需的权限与签名能力。

### D. 明确不能删除的共享接口与数据

| 文件或接口 | 当前调用方与用途 |
|---|---|
| `workbench.py`：POST `/authoring/token`、`/internal/workbench/authorize`、`/internal/workbench/member`、`/internal/workbench/reviewer`、`/internal/workbench/source` | EvalFlow authoring_api、workbench_access、evaluation_assistant、live_approval、work_items和清理作业校验平台身份、命令、评审者及来源；source仍读取历史反馈修订 |
| `workbench_grants.py`、`delegation.py` | materials和EvalFlow的AI/回归两种用途授权、签名及实时项目权限；evaluation_assistant_model_route也参与新资料授权，不能因旧助手退役而删除 |
| `assistant_control.py`、`retention.py`，以及网关中的执行会话登记、维护身份和ACL回调 | 同时管理assistant_threads和execution_threads；后者是EvalFlow运行被测Agent所需，不是废弃助手专属代码 |
| `router.py`：GET `/internal/export`、POST `/internal/authorizations`、POST `/internal/projection`、POST `/exports/{export_id}/revoke` | workbench_access、authorization_batches、feedback_projection及旧授权仍使用；入口撤下不等于后台回调和历史授权失效 |
| `models.py`、平台迁移 `apps/platform-api/migrations/versions/20261113_0011_evaluation_feedback.py` | FeedbackEvent仍支持来源修订核对，EvaluationExport继续保存新旧用途和执行会话；保留迁移链 |
| `apps/runtime-service/src/runtime_service/observability/execution_evidence.py`、`evaluation_environment.py`、`mlflow_tracer.py`，以及 `apps/runtime-service/src/runtime_service/db/migrations/versions/0011_evaluation_execution.py` | 会话初态和执行证据、Session/Run/Trace、评测回归与留存；属于被测执行底座，不是旧出题助手 |
| IAM的project.evaluation.*权限与对应审计 | EvalFlow和两个保留入口仍使用，不随Web菜单移除 |

安全说明（2026-11-18澄清）：用户重申题库独立资产原则，远端Copilot专项D7也已明确保留永久题库资产保护。更早的到期封闭描述不能继续用于让已生成题库连带失效；此前将此列为政策待裁决是本轮判断错误，现已纠正。来源授权到期限制继续读取来源资料，不使独立题库自动失效；项目和题库自身权限仍须校验。本次没有新增原始会话快照的留存/清理规则，也不因保留题库放宽原始资料ACL。按此补V8.5到期回归，不能仅凭代码存在就认定实测通过。

### E. 满足退役条件后删除的旧 Runtime 评测助手

这些是旧05链路；EvalFlow自己的 `eval_platform/evaluation_assistant.py` 和 `eval_platform/agent/` 是当前出题能力，必须保留，不能因同名删除。

已按下述退役条件删除：

- `apps/runtime-service/src/runtime_service/graphs/evaluation_assistant.py`。
- `apps/runtime-service/src/runtime_service/services/evaluation_assistant/agent.py`、`workflow.py`、`prompts.py`、`tools.py`，以及只服务该包的空初始化文件（若存在）。
- `apps/runtime-service/tests/services/evaluation_assistant/test_workflow.py`。
- `apps/platform-api/src/platform_api/modules/evaluation/assistant_bridge.py`，及只验证其已退役行为的 `apps/platform-api/tests/test_evaluation_assistant_bridge.py`。

配套裁剪：Runtime `langgraph.json`图注册、`runtime/capabilities.py`中的EVALUATION_TOOLS和图清单、`tests/test_r0_baseline.py`、`observability/langfuse.py`和相应测试中的旧图专用分支；API `entrypoints/http/router.py`路由注册及`middleware/auth_context.py`中两个专属回调白名单。`workbench_grants.bind_assistant_thread`及旧图补元数据逻辑只有在无调用且不影响历史/执行保护时才移除。维护身份中的dearflow_agent与执行会话保护不得删除。

删除前必须同时具备以下证据，而非只搜索到前端不再引用：

1. 获准目标环境中旧authoring=false工作项、助手Run/中断/待处理回执已只读盘点；没有reserved/running/cancelling作业或未结束执行。用户源会话不为此被停止或删除。
2. EvalFlow `eval_platform/work_item_jobs.py::advance_assistants` 不再为旧工作项调用 `/api/evaluation/internal/workbench/advance`，也不再自动补发旧结果解释；退役前存在的两处派发已删除。该文件仍承担发布和运行调度，不能整体删除。
3. EvalFlow对旧工作项保留历史读取和授权管理，拒绝再启动依赖已退役图的生成/修订/解释；旧地址跳转不得把该依赖重新激活。不得自动将authoring=false改为true或复制旧资料。
4. 重启后旧作业不会恢复派发，历史结果仍可读；新authoring=true的出题、授权、执行、取消、撤权和维护回调均通过回归。

删除前已在获准环境完成只读盘点、关闭旧派发、拒绝旧写入，并在远端回归和重载后删除本仓旧助手。盘点时远端旧工作项和任务JSON均为0，Agent的7条export没有助手线程，Runtime旧图会话/Run均为0；旧助手定义历史记录保留。此为删除前时点结论，不表示当前远端没有本轮新建的authoring评测集。细节见[实施与验证记录](implementation/21-agent-evaluation-entry-cleanup.md)。

### F. 测试、配置与当前说明同步

- API `test_evaluation_feedback.py::setup` 被test_evaluation_workbench、inspection、assistant_control、assistant_bridge以及test_platform_assistant、test_platform_assistant_diagnostics导入。先把确实仍需的公共夹具迁入现有conftest或专用测试夹具，再删除已退役测试；平台助手测试不能跟着失效。
- 保留test_evaluation_materials及授权、撤权、迁移、维护身份、源反馈修订和跨项目拒绝覆盖。不要因某个HTTP入口退役而删除同文件的共享安全断言。
- `apps/platform-api/src/platform_api/config.py`保留workbench_enabled、assistant_model_route、project_id、receiver/web地址、后台凭据和source_token；feedback/synthetic_export/inspection相关设置只在残余回调与历史消费者退役后删。不得简单关闭feedback_enabled，它当前也保护历史revoke入口。
- `RUNTIME_EVALUATION_EVIDENCE_ENABLED`及执行证据/环境开关保留。`deploy/observability/examples/evalflow-inspection.*.yml`属于原暂缓巡检，不因Chat入口退役而删除。
- 实施时更新现行手册、FEATURES及CHANGELOG的用户可感知变化；旧05设计、验收和历史失败记录保留历史事实，不批量改写或移入archive。
- 本轮核查开始时UsageDashboardPage.vue、其spec及router/routes.ts已有未提交改动。两个Usage文件保持不变；routes.ts只调整本专题评测入口，保留其他工作的差异。

## 唯一任务进度

2026-11-18交付决定：用户确认09需求开发完成，并授权合入main与清理隔离环境。08未覆盖的真实多页、全栈回退继续在main按本任务原要求验证，未标记为已通过；09跨机/到期/审批证据仍有效，合成数据库已按授权删除。

Task8.1、8.2、8.4、8.5、8.6已完成；8.3、8.7部分完成，共5项done / 2项partial。09已在独立双Worktree完成跨机主动运行、审批及来源到期题库补证，主环境尚未升级；本专题真实多页与全栈回退仍待原验收，不能以代码清理或09通过代替08联合通过。题库独立保留原则已由用户重申，不再作为政策待决项。08实施证据集中在[21记录](implementation/21-agent-evaluation-entry-cleanup.md)，本节仍是08唯一任务进度源。

### Task 8.1：移除旧工作台与回答内评测操作

用户只从两个会话入口交付资料，不再进入另一套评测编辑和运行流程。

**状态：** 已完成（done）。**涉及位置：** A类12个文件、ChatMessageList、routes.ts及相关路由测试。

- [x] 删除A类文件及调用，移除菜单；旧列表/详情地址只提供明确迁移提示和受控EvalFlow链接。
- [x] 验证旧按钮不出现、不再轮询旧工作项，消息、推荐问题、权限守卫和非评测导航不受影响；无配置/无权限旧链接明确失败。

**开发与验证进度：** 12个文件及接线已删除，旧详情地址实测显示迁移说明和准确远端链接。聊天保留历史、推荐问题、复制和轨迹入口；新合成会话正常回答13，没有反馈/AI改进入口。相关前端9套51项、正常生产构建（含类型检查）和增量ESLint通过；保留原有用量看板路由差异。迁移页拒绝无效UUID、带凭据地址和客户端外链参数，能力及原权限守卫保留。

### Task 8.2：保留两个转换入口，去掉反馈筛选

用户从当前或历史会话出发都进入同一个资料确认流程，功能关闭和权限不足时不产生误导入口。

**状态：** 已完成（done）。**涉及位置：** B类组件与materials.py的会话筛选契约；可与8.1独立验收。

- [x] 保留当前/历史/批量转换与现有20条上限；移除前后端好差评筛选、查询与标签，沿用现有能力开关和权限。
- [x] 补历史选择组件测试，并验证时间/状态/分页、项目切换防串数据、普通成员/管理员用途差异、202通知与同请求重试。

**开发与验证进度：** 两入口共用原弹窗，能力/execute权限及20条上限一致；反馈筛选前后端已移除。组件覆盖时间、状态、分页和项目切换防迟到；真实历史入口、当前入口和双会话批量均交付远端，批量保留2段6消息。当前转换362.66ms返回202，新通知准确显示“资料已送达”并打开正确条目；同一请求恢复返回reused，条目、来源摘要和AI作业ID不变。新建的真实执行者只能交付自己的资料，不能自行授权AI，跨项目和私有会话拒绝。实际多页资料规模未补造，分页/20条边界证据来自组件与API测试，联合验收保留此限制。

### Task 8.3：退役旧公开接口，保留EvalFlow身份和授权

隐藏入口后，旧客户端不能继续通过已退役的公开API发起工作；EvalFlow仍能核实身份、处理用途和执行Agent。

**状态：** 部分完成（partial）。**涉及位置：** C、D类接口及service/contracts/delegation测试；依赖8.1、8.2，额外有效消费者及安全/契约差异另行确认。

- [x] 按C表删除旧公开处理与无调用辅助代码，将work-items动作代理缩减为grant/revoke；保持D表回源与维护功能。
- [ ] 通过API契约和跨仓调用测试：旧提交被明确拒绝，新转换/原请求恢复、EvalFlow登录/建题/授撤权/运行/审批正常，跨项目、篡改签名与来源失权仍拒绝。

**开发与验证进度：** 旧11路由及14种动作已拒绝；回源、身份签名、来源ACL、用途、历史撤权与执行维护保留。相关API大回归188项通过，最后通知/路由/远端origin调整后相关60项通过（范围重叠不相加）。准确origin、准确出口IP、禁止重定向和签名均已核对；真实错误签名拒绝。执行者交付后无AI作业/授权；私有源未分享时管理员也被拒绝，显式只读分享后管理员grant/revoke均200，再撤回分享。**后续补证：** [09专题](09-independent-deployment.md)已在独立双Worktree完成API跨机适配、真实运行/审批、到期资产使用及撤权拒绝；本段保留08现场授权/接口证据，主环境尚未升级新契约。08原联合验收的真实多页与全栈回退仍未完成。

### Task 8.4：核实旧助手是否具备退役条件

旧界面消失后，后台仍可能处理历史任务；删除图和回调前要确认没有遗留执行，并关闭旧调度的新派发。

**状态：** 已完成（done）。**涉及位置：** E类四项条件、EvalFlow work_item_jobs.py/work_items.py/authoring_api.py与只读盘点证据；旧派发退役所需的8.3实现已完成，跨机主动运行补验仍记8.3。

- [x] 在获准环境只读盘点旧工作项/任务/回执，记录范围和查询时点；使旧项在EvalFlow历史只读，保留授权管理并停止旧助手自动调度。
- [x] 验证刷新/重启不再派发旧图，旧结果可读且新authoring流程不受影响；未结任务单独处理，不直接删除或擅自取消。

**开发与验证进度：** 删除前盘点无旧任务/旧图Run，未停止用户源会话。远端跳过authoring=false调度，两处旧助手advance派发已删；旧项拒绝新写，历史read/list/summary及grant/revoke保留，authoring=true仍调用EvalFlow自己的出题Agent。首轮缺依赖/夹具失败已修复：按批准补齐缺失包，原有包仅click8.5.0调整为8.3.3，其余原包锁定。远端扩大回归585项通过；最终退役/准入/调度22项通过。服务已重载，真实新authoring出题及发布成功，停止测试操作回执为cancelled；没有删除工作项历史。当前没有旧样本可做历史浏览器复核，该部分以回归夹具验证。

### Task 8.5：删除已停止使用的Runtime评测助手

确认EvalFlow已独立承担出题后，删除Agent端重复出题图和桥接，不伤及评测执行会话的停止与撤权。

**状态：** 已完成（done）。**涉及位置：** E类文件与注册/测试；在8.4盘点、停派发、远端回归和重载后实施。

- [x] 删除旧图、工具、提示词、桥接与专属注册/白名单；只裁剪无剩余调用的旧图分支。
- [x] 验证运行时启动、图/工具catalog、历史读取，以及dearflow_agent受管执行、停止、撤权维护身份和执行取证；全仓无悬空import。

**开发与验证进度：** 旧Runtime图及4个实现文件、专属测试，API桥接及测试已删除；注册、工具清单、两个回调白名单和唯一旧桥接绑定辅助函数已裁剪。保留dearflow_agent维护身份、执行取证及历史安全分支。Runtime相关91项通过/1项Docker不可用跳过，新增catalog断言后的15项基线通过（不相加）。API/Worker已重载，正常目录刷新得到5个Graph/83个工具/5个可选Agent，无旧助手；历史定义未删。新管理员浏览器会话和执行者HTTP会话均实际运行成功，现有历史消息可读。

### Task 8.6：同步测试夹具、配置和现行说明

删除旧功能后，其他服务和平台助手的测试应继续运行，当前功能说明应与代码一致。

**状态：** 已完成（done）。**涉及位置：** F类文件、各服务现行文档、FEATURES/CHANGELOG/CONTEXT。

- [x] 迁移必要公共夹具，删除真正退役的测试和无消费者配置；保留共享权限、回调、迁移与维护安全测试。
- [x] 同步当前手册与用户变更说明，区分已删除、仍为历史兼容保留与尚未退役；历史交付证据不改写。

**开发与验证进度：** 共用夹具迁至evaluation_fixtures.py，历史记录直接构造，平台助手/诊断仍在188项回归中覆盖。没有删除模型、迁移或仍被回调使用的配置；仅新增默认空的准确origin受信配置。现行助手指南、项目摘要、FEATURES、CHANGELOG与两仓CONTEXT同步本轮状态，原01–07历史事实保留。无关4个产品文件哈希未变，routes.ts保留原用量看板差异。远端修改行Ruff为0条，文件全量仍有39条原位置诊断，未扩大为格式化清理。

### Task 8.7：验证两个入口到EvalFlow的完整链路

用户仍能从会话得到可用评测集，后续全部操作在EvalFlow完成；旧入口下线不能破坏正常聊天或历史数据。

**状态：** 部分完成（partial）。**涉及位置：** 本机Web/API/Runtime及sshmy1 EvalFlow；采用下方整体验收原要求。

- [ ] 完成对应单元、集成、真实浏览器、权限负例与应用回退验证，保存实际结果及限制。
- [x] 回读7项任务、README、功能总览和上下文，逐项说明完成或未覆盖范围；生产部署不作为本地验证的隐含动作。

**开发与验证进度：** 两入口、批量、通知、请求恢复、双身份权限、AI候选、采纳/手改保存和独立发布已实测。发布后未自动运行；显式运行被“缺少所属Runtime源码”阻止，本次操作已正常停止，无被测评测Run。普通聊天的两次新合成执行成功。隔离API当前→旧HEAD→当前启动/登录/保留路由和历史摘要一致，未接主库、未降级数据库；尚未完成Web/Runtime/EvalFlow全栈回退和有效回归运行。**后续：** [09专题](09-independent-deployment.md)已补独立Worktree跨机成功运行、到期资产、真实审批与停止证据；主环境未升级。真实多页及全栈V8.7仍待原范围验收，不能据09通过宣布08整体验收通过。

## 验证要求

### 阶段验证（Phase）

- 前端：旧操作/菜单消失，旧URL提示准确；两个入口、历史选择、批量选择、能力/权限显示、项目切换、失败态和通知链接有组件/路由测试。运行相关Vitest、类型检查、范围lint与生产构建。
- API：materials、用途授权/撤权、命令校验、来源核对、回执幂等和维护控制有测试；退役端点拒绝测试与现有共享安全测试同时存在。公共夹具调整后回归平台助手及其诊断测试，不能只跑evaluation文件。
- Runtime：如果实施8.5，回归catalog/启动基线、维护身份正负例、execution_evidence/evaluation_environment和正常Agent执行；仅删除出题图，不删除执行证据底座。
- EvalFlow：对authoring授权/回源、旧项历史只读、停止旧调度、出题候选、发布运行和取消回归；其测试遵守关联仓AGENTS，未执行的现场检查不能以本地静态结果代替。
- 每条证据记录命令、实际环境、退出结果和失败限制；单测中mock不替代真实服务集成结论。

**本轮Phase事实：** Web相关9套51项、正常构建及增量ESLint通过；API大回归188项、最后变更后60项通过；Runtime91项通过/1项因Docker不可用跳过，新catalog基线15项通过；远端扩大回归585项及最终相关22项通过，各范围有重叠，不相加。API/Runtime增量Ruff通过；远端修改行无诊断，文件全量仍39条既有诊断。真实模型与浏览器、远端源端准入、签名和回环回调均已使用获批合成样本验证；失败和未覆盖范围见[21记录](implementation/21-agent-evaluation-entry-cleanup.md)。未迁移或删除业务数据库。

### 整体验收（Final）

| 编号 | 真实操作与通过条件 | 最低证据 |
|---|---|---|
| V8.1 | 当前会话转为评测集，确认用途后202返回；完成通知进入正确EvalFlow条目；同请求恢复不重复创建 | 浏览器操作、脱敏请求/回执、条目与来源ID核对 |
| V8.2 | 从历史会话按时间/状态筛选、继续分页并批量提交；不存在好差评筛选，跨项目/无权会话不能提交 | 浏览器与API正负例、批量条目来源核对 |
| V8.3 | 普通成员只交付资料，管理者在EvalFlow确认AI用途；生成候选、采纳保存、发布和运行分别成功 | 不同权限身份的真实链路；发布前后被测Agent调用次数/Run核对 |
| V8.4 | 聊天/导航无旧操作，旧地址不白屏、不自动提交；旧项历史可读，旧公开写接口拒绝，新通知不指向旧页 | 路由/接口测试与浏览器截图；旧项缺失或拒绝时的明确提示 |
| V8.5 | 按用户2026-11-18重申的既定原则，来源授权到期不使已生成的独立题库失效；继续取源、停止和项目/资产权限仍按各自授权执行，维护权限、跨项目和错误签名保护保留 | 受控到期样本验证题库仍可用、无权取源仍拒绝；保留权限/停止回执，不以永久保留题库代替原始资料ACL |
| V8.6 | 旧助手退役条件具备后，重启不派发旧图；无未结旧任务，新转换与EvalFlow出题正常 | 8.4盘点与调度证据、重启/启动基线和调用记录；未满足不能标通过 |
| V8.7 | 应用回退构建保留当前迁移链，历史资料不丢失，保留接口可用；未改用户业务配置或权限 | 隔离环境回退与再升级记录；不执行数据库降级或生产回退 |

**当前联合验收结论：部分完成（partial），未通过全部Final。** 本节保持原通过条件，不用阶段测试数量替代完整链路：

| 编号 | 本轮实际结果与剩余条件 |
|---|---|
| V8.1 | 通过：当前转换202、通知正确远端条目、相同请求恢复reused，来源摘要/作业ID不变。 |
| V8.2 | 部分完成：历史入口及2段6消息批量实测通过，私有源和跨项目拒绝；分页/20条上限和项目切换有组件/API覆盖，尚无真实多页资料规模的浏览器连续翻页证据。 |
| V8.3 | 08现场的资料、用途、候选/发布证据保留；09已在独立双Worktree补真实跨机运行和普通执行者运行，主环境尚未升级。详见09的Task9.4/Final，不再将同机假设记为未实现的代码缺口。 |
| V8.4 | 通过：旧详情URL为受控迁移页，聊天/导航无旧操作，新通知不再误报AI完成；退役路由/动作和旧项读取有测试。目标环境删除前无旧工作项，未伪造旧样本浏览器证据。 |
| V8.5 | 09隔离补证通过：模拟一条源授权到期，取源403，题库读/编辑/发布/运行通过；普通执行者撤权后新运行403，正式停止回执stopped/true。08原grant/revoke、私有源/签名/跨项目证据保留；主环境未升级。 |
| V8.6 | 通过：旧任务/旧图Run盘点为0，停旧派发后重载，无旧图/工具目录；新转换和EvalFlow自己的AI出题成功。 |
| V8.7 | 部分完成：隔离API使用同一合成SQLite完成当前→旧HEAD→当前的真实应用加载、登录、能力200/保留路由422及历史摘要一致；无DB降级。跨机成功运行已由09补证；尚未完成全栈回退/再升级，不能等同完整恢复演练。 |

当前开发连接为准确远端`http://49.233.222.54:9128`，入站只追加准确出口`111.227.13.240`；资料回调通过远端`127.0.0.1:38375`的反向隧道连接本机API2142。保留签名和实时权限，不开放公网回调。HTTP没有TLS，出口IP变化或本机API/隧道离线会使链路失败。原主环境资料和权限未为通过测试而放宽；没有执行Git提交/推送或无关生产操作。

### 跨机读取原因与已确认的资产原则（2026-11-18澄清）

**跨机读取原因：** 远端`resource_snapshot`直接读取`agent_repo/apps/runtime-service/src/runtime_service`计算源码指纹，`deployment_manifests`还直接调用该目录下两个app的`.venv/bin/python`。配置的agent_repo为Mac绝对路径，现场确认该路径在sshmy1不存在。现有SSH隧道只转发HTTP，不共享文件系统，因此远端不能据此读取本机文件。这是旧实现的同机部署假设，不是签名或目录权限拦截。

**签名的定位：** 记录和比对版本，是为了确认本次实际运行的是哪版Agent，避免代码变更或进程未重启造成评测身份不一致。现有平台命令已使用短期、正文绑定的签名并实时检查成员权限；来源回调也已有服务认证。后续跨机适配应优先复用现有鉴权、构建清单和执行回执，通过API取得必要版本信息，不让EvalFlow依赖Mac目录。此前的“受控签名版本清单”只是传递可信版本信息的一种建议，不是读取源码所必需的新系统，也未作为必须另建的签名体系获批实施。具体跨机适配现已在[09独立Worktree](09-independent-deployment.md)完成技术验收，主环境未升级。

**题库独立保留已确认：** 用户明确重申“即使到期，题库还可以正常用，作为独立资产”。来源资料的临时授权与已生成题库的生命周期分开；不能因来源授权到期自动封闭或清理题库。独立资产继续受EvalFlow项目/资产权限及自身显式管理操作控制。原始会话快照的留存和访问继续按各自规则处理，本次澄清没有授权永久公开或任意清除原始资料；真实HTTP到期回归已由09在隔离专库模拟到期并完成，详见Task9.4；没有改变原始资料留存规则。

## 规划检查记录

2026-11-18：本轮只增加本专题并同步原项目README、FEATURES和CONTEXT。Python静态检查通过：7个任务编号唯一且保持待开始，12个前端删除候选均存在，32个完整显式代码路径存在，14条实施检查均未勾选；新增08导航链接可达，换行/行尾空白及围栏检查通过。`git diff --check`通过。README、任务与功能/上下文摘要已回读，均为规划而非产品交付。

核对开始时已有的两个UsageDashboard文件和routes.ts共3个产品文件，其SHA-256在本轮写文档前后相同；工作区后来出现的用量看板变更记录也不属于本专题。没有改动产品代码、数据、私有配置或关联EvalFlow仓库，没有执行Git提交/推送、服务启停或部署。

2026-11-18补充：用户同意清理方案后，再核对后端函数调用与两个转换接口。确认旧`save_receipt`与新转换回执实现独立，`public_event`仅供旧反馈使用，`record_action`仍服务保留的授权操作；EvalFlow仍有两处旧助手advance回调。仅补充删除边界和方案同意状态，7项任务仍未实施；未盘点运行数据库，不能宣称旧助手已具备退役条件。
