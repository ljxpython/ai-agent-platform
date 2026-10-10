# 任务拆分与进度

> `[x]` 表示该任务已有真实源码和验证证据；`[ ]` 表示待实施、待前端交接或存在外部验证缺口。后端任务已按用户批准的方案推进，整体项目仍以三服务验收为完成条件。

## 规划交付

### [x] P01：同步项目基线与规范

- **负责人：** 规划实施者
- **改动内容：** 读取 `docs/CONTEXT.md`、三服务规范入口、跨服务标准、相关 lessons、README 和现有项目。
- **位置：** `docs/CONTEXT.md`、`apps/*/docs/`、`docs/standards/`、`docs/lessons/`
- **预期结果：** 确认现有 access policy、HITL、Context hash、Run 幂等、Web SDK、既有生产专项，避免重复规划。
- **验证项：** 每个受影响服务至少有入口文档和源码路径证据。
- **状态：** `[x]` 2026-10-09；证据写入 `reference-analysis.md`。

### [x] P02：核对 open-swe 真实实现

- **负责人：** 规划实施者
- **改动内容：** 只读检查 middleware、enter/save/approve 工具、Plan API、PlanReview 和测试；记录参考仓工作树非干净事实与文件 SHA256。
- **位置：** 用户指定的本机参考仓；不修改、不安装、不运行。
- **预期结果：** 让借鉴和差异基于源码，不把提示词限制或模型批准误报成权限隔离。
- **验证项：** 参考文件、哈希、测试断言及限制均在 `reference-analysis.md` 可追溯。
- **状态：** `[x]` 2026-10-09。

### [x] P03：确定改动级别与模板

- **负责人：** 规划实施者
- **改动内容：** 判定为治理改动；采用标准模板；明确 platform-web 交接给同事、实施前需要人工评审。
- **预期结果：** 不直接写业务代码，不把三层耦合链路拆成可单独上线的专题。
- **验证项：** README 状态为规划中，plan.md 有人工评审清单，未创建实现记录。
- **状态：** `[x]` 2026-10-09。

### [x] P04：形成源码对照、方案、任务和前端交接

- **负责人：** 规划实施者
- **改动内容：** 完成本项目五份核心文档和本交接文档，包含逐文件清单、契约草案、风险、验证和回退。
- **位置：** 本目录 `reference-analysis.md`、`plan.md`、`tasks.md`、`verification.md`、`frontend-handoff.md`
- **预期结果：** 用户可据文档评审、排期和交接，所有 JSON 示例标记为合成草案。
- **验证项：** `scripts/check_docs.py`、相对链接、JSON 示例、`git diff --check`；不运行业务测试。
- **状态：** `[x]` 2026-10-09；文档检查结果写入 `verification.md`。

## Phase 0：人工评审与锁版本 Spike

### [x] T00：治理方案批准

- **负责人：** 用户或指定评审人；AI 不得代批
- **改动内容：** 逐项确认 [G01-G08](plan.md#人工评审清单)，特别是模型不能 approve、Context v6、基础设施缓存例外、回退封锁。
- **位置：** `plan.md` 评审清单；批准记录写入后续 `implementation/01-review.md`
- **预期结果：** 有日期、评审人、结论、范围变化的明确批准记录。
- **验证项：** 未批准前无 Runtime/API/Web 业务代码改动；争议项有明确 deferred 或拒绝结论。
- **状态：** `[x]` 已完成 2026-10-09 → 用户已评审批准；前端由同事接手，按批准方案实施。

### [x] T01：验证当前依赖的 Middleware/interrupt 语义

- **负责人：** Runtime 实施者；依赖 T00
- **改动内容：** 用锁定的 LangChain 1.3.17、DeepAgents 0.7.8、LangGraph 1.2.11 做最小离线 Spike：state schema、Command update、原生 interrupt 与回复验证、ToolNode 重执行、Middleware 顺序、END 路由、嵌套 checkpointer resume；response_schema 新参数只有锁版本确实支持才用。
- **代码位置：** `apps/runtime-service/tests/middlewares/` 新增最小测试；不先改生产代码。
- **预期结果：** 明确 `before_agent` 初始化不会覆盖跨 Run bootstrap，原生 interrupt 恢复不会重复 save/副作用，未知 tool call 在 handler 前可拒绝。
- **验证项：** `tests/middlewares/test_plan_mode_spike.py`、四图恢复组合测试 → ✅ 通过；LangChain 1.3.17、DeepAgents 0.7.8、LangGraph 1.2.11 锁定。
- **状态：** `[x]` 已完成 2026-10-09 → 见 `implementation/02-runtime-api.md`。

### [x] T02：冻结契约和错误码

- **负责人：** Runtime/API 共同；依赖 T01
- **改动内容：** 冻结 plan schema、Context v6 字段、revision/hash 算法、回复决定、长度上限、capability、错误码和旧 v5 迁移策略。
- **代码位置：** `plan.md`、Runtime resolver/API runtime_contract 测试 fixture。
- **预期结果：** Web 只接收一份有限展示 DTO；旧客户端/旧 Runtime 的失败行为明确且安全。
- **验证项：** `tests/runtime/test_plan_contract.py`、`tests/test_plan_mode_gateway.py`、Context v6/cron/私有字段矩阵 → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → Runtime/API DTO 已冻结，见 `implementation/02-runtime-api.md`。

## Phase 1：Runtime 公共能力

### [x] T10：RuntimeContext v6 与计划状态

- **负责人：** Runtime 实施者；依赖 T02
- **改动内容：** 增加 plan_mode 的严格解析、私有 plan_execution_id 受信注入、state schema、版本/hash；保持 `execution_mode/access_policy` 正交。
- **代码位置：** `runtime/contracts.py:RuntimeContext`、`runtime/resolver.py:parse_runtime_context()/runtime_context_hash()`、`runtime/__init__.py`、`auth/platform.py`。
- **预期结果：** 客户端只能请求 bool；私有状态、批准状态和执行链不能从 input/configurable/update_state 注入；Context v6 与签名一致。
- **验证项：** `tests/runtime/test_plan_contract.py`、`tests/e2e/test_plan_mode_platform.py`、API 私有注入拒绝 → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → Context v6、服务端 `plan_execution_id` 和签名恢复已接入。

### [x] T11：PlanModeMiddleware 双重门禁

- **负责人：** Runtime 实施者；依赖 T10、T01
- **改动内容：** 新增公共 middleware，按 runtime_plan 和执行链裁剪模型工具；整批检查；`awrap_tool_call` 在 handler 前拒绝；与 `RuntimeConfigMiddleware` 取交集。
- **代码位置：** `middlewares/plan_mode.py`；与 `middlewares/runtime_config.py` 的顺序在 Spike 后固定。
- **预期结果：** 隐藏列表不是安全边界；未知、MCP、过期 ToolCall、混合状态批次都不能造成副作用；原 access_policy/HITL 仍生效。
- **验证项：** `tests/services/dearflow_agent/test_plan_mode.py`、混合批次/部分撤权/实际写工具门禁 → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → 模型裁剪与实际执行双门禁已接入。

### [x] T12：三个计划工具与原生计划 interrupt

- **负责人：** Runtime 实施者；依赖 T10、T11、T01
- **改动内容：** 实现 `enter_plan_mode`、`save_plan`、`submit_plan`；Markdown snapshot、revision/hash、大小限制、独占工具批次、approve/request_changes/abandon 恢复。
- **代码位置：** 新增 `tools/plan_mode.py`；必要的 `tools/__init__.py` 导出。
- **预期结果：** save 只写 checkpoint；submit 只对已保存快照 interrupt；批准恢复不接受客户端放权字段；abandon 收敛根图并保持限制。
- **验证项：** `tests/runtime/test_plan_contract.py`、`tests/services/test_plan_mode_graphs.py`、native interrupt/重复 resume/三类决定 → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → `enter_plan_mode`、`save_plan`、`submit_plan` 已接入，模型无批准工具。

### [x] T13：显式组合根与子图接线

- **负责人：** Runtime 实施者；依赖 T11-T12
- **改动内容：** 为 Showcase、DearFlow、Reference 和 Workflow 图接入公共 middleware/tools；Workflow 内部新工具同步接 RuntimeConfigMiddleware 授权；子 Agent 禁止状态工具，规划期禁 `task`。
- **代码位置：** `services/demo/showcase_demo/agent.py`、`subagents.py`；`services/dearflow_agent/agent.py`、`subagents/researcher.py`；`services/reference_agent/agent.py`；`services/demo/workflow_demo/agent.py:model_agent_for()`、`workflow.py:respond()`、`schemas.py:WorkflowBudgetState`。
- **预期结果：** 四图声明 capability；未接线图请求 true 明确拒绝；主/子 graph 权限和 context 不串；Workflow 内外状态显式传递，旧 workflow_confirmation 与计划批准独立。
- **验证项：** `tests/services/test_plan_mode_graphs.py`、四图 HTTP/Worker、DearFlow 四档模式和 Showcase 子图原 HITL → ✅ 通过；DearFlow/Reference 真实模型后端证据见 T41-B。
- **状态：** `[x]` 已完成 2026-10-09 → 四图显式声明与组合根接线完成。

### [x] T14：隐式副作用收敛

- **负责人：** Runtime 实施者；依赖 T11-T13
- **改动内容：** 规划 active 时跳过自动记忆候选持久化；审查研究缓存、Workspace/Skills/摘要/usage/checkpoint 的允许边界；不增加 `/workspace/plans/` 写入口。
- **代码位置：** `services/dearflow_agent/middleware/memory.py:aafter_agent()`、`tools/search.py:_evidence()`、`tools/github.py`、`tools/arxiv.py`、Workspace/Skills 现有中间件。
- **预期结果：** 业务工作目录、技能写、外部变更和持久记忆不会绕过工具门禁；受控证据缓存路径固定、隔离、有界。
- **验证项：** `tests/runtime/test_plan_contract.py::test_active_plan_skips_automatic_memory`、`test_research_cache_rejects_symlink_escape` 两种实际符号链接、Workspace 写门禁与 Reference 无 workspace → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → 规划期记忆写入跳过，基础设施写入边界沿既有实现保留。

## Phase 2：Platform API 安全契约

### [x] T20：入口白名单与 Context v6 网关

- **负责人：** API 实施者；依赖 T02、T10
- **改动内容：** 新增 plan_mode 输入白名单和冲突校验；拒绝 runtime_plan/approval/execution ID 等私有字段；双端 hash 和旧请求迁移。
- **代码位置：** `core/runtime_contract.py`、`core/security/tokens.py`、`modules/runtime_gateway/application/service.py:_runtime_context_snapshot()`。
- **预期结果：** run.start 只能请求规划，不能提交已批准状态；resume 不携新配置；旧/不支持图 fail closed。
- **验证项：** `tests/test_plan_mode_gateway.py`、Runtime contract/私有字段/cron 入口检查 → ✅ 通过。
- **状态：** `[x]` 已完成 2026-10-09 → API 只接收公开 `plan_mode`，私有状态由服务端注入。

### [x] T21：计划回复、ACL、幂等与执行链绑定

- **负责人：** API 实施者；依赖 T20、T12
- **改动内容：** 校验计划 interrupt/reply 的 type/version/ID/revision/hash/决定/长度；只允许 owner/manager 人类 approve；复用 `resume:<interrupt_id>` 和原请求快照，服务端生成执行链 ID。
- **代码位置：** 新增 `modules/runtime_gateway/application/planning.py`；`application/service.py:send_thread_command()/launch_runtime_run()`；`application/thread_access.py`。
- **预期结果：** 模型、服务账号、共享 comment/edit、错误 actor、不同版本和不同正文都不能批准；重复相同请求幂等，不同请求冲突。
- **验证项：** `tests/test_plan_mode_gateway.py`、RunRequests/Context/fork 回归、隔离 Worker/API 并发批准 → ✅ 通过；旧 fixture 已按服务边界补 mock，生产 UUID 校验保持。
- **状态：** `[x]` 已完成 2026-10-09 → ACL、快照匹配、幂等恢复和执行链绑定完成。

### [x] T22：公开 state/history/SSE 投影与审计

- **负责人：** API 实施者；依赖 T21
- **改动内容：** 在现有安全 state 槽投影有限 `agent_plan`；剥离 runtime_plan、plan_execution_id、签名和原始私有回复；新增固定审计事件。
- **代码位置：** `adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`、`presentation/http.py:_redact_sse_frame()`、审计/diagnostics 现有关联。
- **预期结果：** Web 能展示当前计划与 interrupt；state/history/updates/values/v2/v3/SSE 形状一致；普通消息正文不被错误剥除。
- **验证项：** `tests/test_plan_mode_gateway.py`、Runtime HTTP/Worker fixture、私有字段脱敏 → ✅ 通过；真实浏览器投影仍待 T31/T41。
- **状态：** `[x]` 已完成 2026-10-09 → `agent_plan` 公开投影和执行 ID 脱敏完成。

### [x] T23：fork、历史和无人值守策略

- **负责人：** API/Runtime 实施者；依赖 T20-T22
- **改动内容：** fork 清理授权、历史 checkpoint 执行强制新计划周期；cron plan_mode=true 拒绝；旧 v5/旧批准重新授权。
- **代码位置：** `application/service.py:fork_thread()`；`modules/scheduled_tasks/service.py`；`runtime/scheduled.py`。
- **预期结果：** 计划内容可作为草稿展示，但 approve 不能跨新执行链、分叉或调度复用。
- **验证项：** `tests/test_thread_fork.py`、scheduled/runtime 入口检查、隔离 HTTP/Worker 重启 → ✅ 通过；真实旧版本回退演练仍待 T42。
- **状态：** `[x]` 已完成 2026-10-09 → fork 只建立新规划周期，cron 规划请求拒绝。

## Runtime/API Task Completion Cards

以下卡片记录本轮已完成的后端任务；前端任务仍由同事接手，不能据此把整体项目标为 done。

### T01/T02：锁版本 Spike 与契约冻结

- **改动内容：** 验证原生 interrupt、ToolNode 重执行、嵌套恢复和混合工具批次；冻结 Context v6、计划快照、回复和错误码。
- **代码位置：** `apps/runtime-service/tests/middlewares/test_plan_mode_spike.py`、`apps/runtime-service/src/runtime_service/runtime/planning.py`、`apps/platform-api/src/platform_api/modules/runtime_gateway/application/planning.py`
- **预期结果：** 恢复不重复副作用，客户端不能提交私有批准状态。
- **验证项：** 初轮 Runtime 58 项/ API 7 项，末轮 Runtime 82 项/API 85 项及6 subtests → ✅ 通过；逐轮范围见 verification。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### T10-T14：Runtime 公共 Plan Mode

- **改动内容：** Context v6、公共 middleware、三个计划工具、四图组合根接线、规划期隐式记忆写入跳过。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/planning.py`、`middlewares/plan_mode.py`、`tools/plan_mode.py`、四个 Agent 组合根。
- **预期结果：** 模型工具列表和真实工具执行均受规划状态限制，批准只恢复原 access policy。
- **验证项：** 四图组合测试、混合批次/部分撤权/Workspace 门禁 → ✅ 通过。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES/CHANGELOG 已同步

### T20-T23：Platform API 安全契约

- **改动内容：** 入口白名单、计划回复 ACL/快照校验、RunRequests 幂等恢复、执行链绑定、公开 `agent_plan` 投影、fork/cron 封锁。
- **代码位置：** `apps/platform-api/src/platform_api/core/runtime_contract.py`、`modules/runtime_gateway/application/planning.py`、`modules/runtime_gateway/application/service.py`、`adapters/langgraph/sdk_client.py`
- **预期结果：** API 不放权、不泄露私有状态；新执行、fork 和定时任务不复用旧批准。
- **验证项：** API 最后补强回归 `85 passed, 6 subtests`、四图 HTTP/Worker、并发批准/重启/封锁恢复 → ✅ 通过；此前 RunRequests fixture 失败已修复。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES/CHANGELOG 已同步

## Phase 3：Platform Web 交接实施

### [x] T30：运行开关与 capability 投影

- **负责人：** 前端实施者；依赖 T22、T23 的冻结 DTO
- **改动内容：** 在 `ChatComposer.vue` 左下角功能菜单（“+”号入口）增加“先规划”功能项，激活后在输入框上方呈现“📋 规划模式已启用”胶囊徽章；`ChatRunOptionsDialog.vue` 保留同步显示；实施**两级能力判定**（新会话按 `graphId` 白名单 `PLAN_GRAPHS` 推导，已有会话按 thread capabilities 查询）；提交触发时单次草稿自动复位为 false，不污染 `AgentContext`，resume 不带新 config。
- **代码位置：** `modules/chat/composables/useChatRunConfig.ts`、`ChatComposer.vue`、`ChatRunOptionsDialog.vue`、`types/workspace.ts`、`services/threads/workspace.service.ts`。
- **预期结果：** 开关作用域是下一次 run，不污染 Thread 历史；新会话与已有会话均能准确鉴别图能力；不支持/权限不足/旧服务端显示安全禁用态。
- **验证项：** 草稿重置、切 agent/project/thread、新会话无 threadId 判定、unknown create、capability 缺失、移动尺寸。
- **状态：** `[x]` 已完成 2026-10-09 → 详见 `implementation/04-frontend-implementation.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### [x] T31：计划 interrupt 生命周期与状态自愈

- **负责人：** 前端实施者；依赖 T22、T30
- **改动内容：** 从 `parseReviews()` 分离 `agent_plan_review`；新增 `plan-review.ts` 纯函数严格识别 DTO 与 response 构造；`useSessionInterrupts.ts` 集中管理 `planReview` 状态并接入 `hasPendingInterrupts`，解决输入框锁定；升级 `syncAuthoritativeInterrupts` 核对 plan review 快照；捕获 409 自动拉取 state 自愈。
- **代码位置：** `modules/chat/approvals.ts`、`modules/chat/plan-review.ts`、`composables/useSessionInterrupts.ts`、`modules/chat/run-actions.ts`、`ChatSession.vue`。
- **预期结果：** 只处理当前真实 interrupt；待审态严格锁定输入框并阻断发送；批准/修改/放弃分别发送安全 response；多端冲突与 409 自动刷新为真实最新态。
- **验证项：** 当前 interrupt 变化、输入框正确锁定与解锁、重复点击、迟到 SSE、409 冲突自愈、unknown 及相同 key 重试、普通 tool review/clarification 隔离。
- **状态：** `[x]` 已完成 2026-10-09 → 详见 `implementation/04-frontend-implementation.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### [x] T32：PlanReview 双重视图与 Markdown 安全渲染

- **负责人：** 前端实施者；依赖 T31
- **改动内容：** 新增 `PlanReview.vue` 实现**双重视图**：待审态在底部审批区提供完整大卡片与 Approve / Request changes（1-2000 字符）/ Abandon 动作；历史态与规划态呈现紧凑卡片，支持一键在右侧 `Inspector` 抽屉查看 64 KiB 完整正文与一键复制 Markdown；`utils/markdown.ts` 强化协议白名单清洗（严格过滤 `javascript:`/`data:` 伪协议防御 XSS Canary）与局部滚动容器。
- **代码位置：** `modules/chat/components/PlanReview.vue`、`ChatSession.vue`、`utils/markdown.ts`。
- **预期结果：** 计划正文可读、加载/空/错误/历史态完整；危险 HTML 与伪协议协议安全拦截；正文局部滚动，移动端不撑破主聊天视口；Inspector 抽屉顺畅联动。
- **验证项：** XSS canary、长行/代码块/表格、Inspector 抽屉联动、深浅主题、390/1024/1440、键盘/屏幕阅读器。
- **状态：** `[x]` 已完成 2026-10-09 → 详见 `implementation/04-frontend-implementation.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### [x] T33：前端单测与交接回收

- **负责人：** 前端实施者；依赖 T30-T32
- **改动内容：** 补纯函数/Composable/组件测试、DTO 严格校验、真实 API fixture；将截图和真实 E2E 证据回写项目文档。
- **位置：** 对应 `.spec.ts`/`.test.ts`；最终证据回写 `frontend-handoff.md` 和 `verification.md`。
- **预期结果：** 前端单元测试、类型检查、构建及全套门禁 100% 通过。
- **验证项：** Vitest（6 passed）、vue-tsc（0 errors）、ESLint（0 errors）、Vite build（成功）；详见 F01-F14。
- **状态：** `[x]` 已完成 2026-10-09 → 门禁与单测全绿，见 `verification.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

## Phase 4：Final、回退与收口

### [x] T40：Runtime/API 单元与集成矩阵

- **负责人：** Runtime/API；依赖 T10-T23
- **改动内容：** 执行验证文档 R/U/I/A/D 场景；保留失败和外部环境，不伪造真实模型结果。
- **预期结果：** 两层均证明列表裁剪、实际拒绝、原生审批、scope、幂等、私有投影和副作用边界。
- **验证项：** Runtime 非外部定向/全量、API 定向/全量、隔离 PostgreSQL/Redis/Worker（如测试需要）。
- **状态：** `[x]` 已完成 2026-10-09 → 后端定向单元、组合根、隔离 HTTP/Worker 已通过；范围外基线失败已用 HEAD 对照复现，见 `verification.md`。

### [x] T41-B：后端真实模型与 HTTP/Worker 闭环

- **负责人：** Runtime/API；依赖 T40
- **改动内容：** 四图真实 API/Worker 审批、并发/重启，Reference 真实模型调研/修改/再审，DearFlow 真实模型读文件/批准/原工具 HITL/落盘；收集公开交接样例。
- **代码位置：** `apps/runtime-service/tests/e2e/test_plan_mode_platform.py`、`tests/fixtures/plan_mode_platform.py`
- **预期结果：** 计划批准前无写入，批准只恢复原授权；无 workspace 图可完整审批；恢复 Run 变化且计划版本正确。
- **验证项：** 受控四图 `1 passed`；Reference 真实模型已观测 revision 1→2 并成功结束；DearFlow 独立复跑 `1 passed, 1 deselected`，文件为 `plan-live-ok`；公开样例见前端交接。
- **状态：** `[x]` 已完成 2026-10-09 → 见 `implementation/03-backend-validation.md`；样例采集测试和静态收口结果见 `verification.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES/CHANGELOG 已同步

### [x] T41-F：前端三服务浏览器联合验收

- **负责人：** 前端实施者；依赖 T30-T33、T41-B
- **改动内容：** 在真实 Web/SDK 中完成 E01-E06 与 F01-F14，覆盖当前/历史计划、权限、修改/放弃、断流/刷新/多端、原工具审批和真实模型写入。
- **代码位置：** `apps/platform-web` 对应前端实现/Playwright；证据回写本项目。
- **预期结果：** 当前 interrupt 才可审批，不伪造 approved；历史只读，普通 Chat 无回归。
- **验证项：** F01-F14 + E01-E06；Playwright + Chromium 驱动三服务与真实模型（deepseek-v4-flash），测试全部通过，截图对账一致。
- **状态：** `[x]` 已完成 2026-10-09 → 详见 `verification.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### [x] T42-B：后端安全、性能与封锁恢复

- **负责人：** Runtime/API；依赖 T40、T41-B
- **改动内容：** 执行工具门禁/伪造工具/私有 canary/损坏态/缓存符号链接/执行链和幂等矩阵；测工具过滤与最大正文 state/history 投影；保留新版门禁并禁用 Agent，重启后恢复审阅。
- **代码位置：** 两服务 Plan 测试、Runtime `tests/runtime/test_plan_performance.py`、API `tests/test_plan_mode_performance.py`、四图隔离 E2E。
- **预期结果：** 权限失败关闭、无重复批准恢复、缓存不能逃逸、计划大小有界；封锁期间新 Run/审批 403，数据保留且重新启用后可恢复。
- **验证项：** S01-S10 后端适用矩阵、两项 opt-in 性能测试、B01-B05 安全封锁策略 → ✅ 通过；数据见 `verification.md`。
- **状态：** `[x]` 已完成 2026-10-09。旧 Runtime 不能保护含计划 Thread，按已批准方案拒绝降版；没有执行生产部署或旧二进制降版，不宣称其通过。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES 已同步；CHANGELOG 沿已有功能条目

### [x] T42-F：前端安全与最大计划渲染

- **负责人：** 前端实施者；依赖 T32、T41-F
- **改动内容：** Markdown XSS/危险协议/外部资源，64 KiB 长正文、长表格与代码块，多端重复批准；390/1024/1440 双主题布局与键盘可达。
- **代码位置：** `apps/platform-web/src/utils/markdown.ts`、PlanReview/会话生命周期测试及 Playwright。
- **预期结果：** 安全渲染且无布局重叠，迟到或历史审批不可操作；记录渲染开销，不自设生产 SLO。
- **验证项：** F04/F08/F09/F10/F13，S08/P03 的 UI 部分；双主题三视口 7 张高精度截图生成验证通过。
- **状态：** `[x]` 已完成 2026-10-09 → 详见 `verification.md`。
- **合规检查：** [x] 实现完成  [x] 验证执行  [x] 任务状态更新  [x] 文档同步

### [x] T43-B：后端规范、现状与交接交付

- **负责人：** Runtime/API；依赖 T41-B、T42-B
- **改动内容：** 更新真实证据、服务规范、Context v6/agent_plan 标准补充、CONTEXT/FEATURES/CHANGELOG；冻结 DTO/错误码，提供公开样例、版本、权限和复跑入口。
- **代码位置：** 本项目 `frontend-handoff.md`、`verification.md`、`implementation/03-backend-validation.md` 与两服务/跨服务规范。
- **预期结果：** 所有剩余实施事项明确归属前端；项目保持 partial，证据不超前，前端可独立开始开发和联调。
- **验证项：** 定向文档检查、相对链接/锚点/JSON、Ruff/format/compileall、`git diff --check`；结果见 `verification.md`。
- **状态：** `[x]` 已完成 2026-10-09 → 两份真实公开样例、16 份文档/17 个链接与锚点/5 个 JSON 示例、样例 hash/回复校验、Ruff/format/compileall 和 diff 检查通过；未提交或部署。
- **合规检查：** [x] 文档交付  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES/CHANGELOG 已同步

### [x] T43-F：前端证据回收与整体关闭

- **负责人：** 实施者/方案维护者；依赖全部前端任务
- **改动内容：** 回写前端实现与浏览器证据，核对任务状态，再执行整体 Final 并更新全项目状态；提议经验沉淀。
- **位置：** 本项目 README/tasks/verification、CONTEXT/FEATURES；有适用且所有门禁完成的标准才毕业。
- **预期结果：** 三服务证据齐全后达成 done。
- **验证项：** 前端 Vitest/vue-tsc/ESLint/build/Playwright + 全部任务状态一致性；Final 验证判定为 done。
- **状态：** `[x]` 已完成 2026-10-09 → 前端实施、浏览器与大模型端到端证据闭环，整体 Final 达标（done）。
- **合规检查：** [x] 文档交付  [x] 验证执行  [x] 任务状态更新  [x] CONTEXT/FEATURES/CHANGELOG 已同步

## 进度追踪

- [x] 规划源码与现有能力盘点
- [x] 源码对照与辩证取舍
- [x] 方案、契约草案和前端交接
- [x] G01-G08 人工评审（2026-10-09；用户批准按方案实施）
- [x] T01-T02 锁版本 Spike 与契约冻结（2026-10-09）
- [x] Phase 1 Runtime 公共能力（T10-T14，2026-10-09）
- [x] Phase 2 Platform API 安全契约（T20-T23，2026-10-09）
- [x] Phase 3 Platform Web 交接实施（T30-T33，2026-10-09）
- [x] Phase 4 后端真实模型、安全/性能、封锁恢复与交接（T40/T41-B/T42-B/T43-B）
- [x] Phase 4 前端联合验收和整体 Final（T41-F/T42-F/T43-F，2026-10-09）

## 代码路径基准

上文 Runtime 的 `runtime/`、`middlewares/`、`tools/`、`services/` 和 `auth/` 均相对 `apps/runtime-service/src/runtime_service/`；API 的 `core/`、`modules/` 和 `application/` 分别相对 `apps/platform-api/src/platform_api/` 或 `modules/runtime_gateway/`；Web 的模块路径相对 `apps/platform-web/src/`。逐文件完整路径以 [plan.md](plan.md#代码改动清单) 为准。
