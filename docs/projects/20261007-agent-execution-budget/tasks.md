# Agent 执行预算 - 任务拆分

> 当前状态：2026-10-07 用户已批准方案；全任务 T01-T07、T08A、T08B、T09 及前端 F01-F04 全部完成并达到 `done`。任务状态只维护在本文，implementation/ 只存改动证据。

## 本轮规划交付

- [x] 读取 CONTEXT、三服务规范入口、跨服务标准和相关经验。
- [x] 对照 open-swe 本地实际源码，并记录参考工作树有本地修改。
- [x] 核对锁定依赖、四个正式 graph 的实际限额/退出策略、Worker timeout 和 custom 事件运输。
- [x] 跑 Runtime 基线 28 项、API SSE 基线 19 项方法；如实记录 API 三个失败断言和安全缺口。
- [x] 离线确认 after_agent 在 error/recursion 异常路径不执行，及RemainingSteps私有注解顺序；核实原生Run GET无error字段。
- [x] 完成职责、接入、契约、任务、验证和前端交接文档。

## G0 人工评审

- **改动内容：** 审阅本目录方案，明确范围、限制策略、事件/错误契约和当前冲突处理，不由 AI 自批。
- **代码位置：** 暂不修改代码；评审结论记录在下表及本文任务状态。
- **预期结果：** 有评审人、日期、批准范围和修改意见，实施人员知道哪些行为允许调整。
- **验证项：** R01-R06 均有明确结论；安全/契约冲突先裁决再实现。
- **状态：** [x] 已完成 2026-10-07，用户在会话中明确批准方案并授权完成全部非前端开发项。

| 项 | 建议 | 人工结论 |
| --- | --- | --- |
| R01 范围与策略 | 保留四 graph 当前 end/error、run/thread/child limits，不扩展全部 Agent 生产化 | 按建议批准；本轮仅非前端实施 |
| R02 预警余量 | 模型 3 次、图 8 supersteps 为起点，T01 实测后冻结各拓扑参数 | 按建议批准；以实际图检查为准 |
| R03 时间语义 | 独立软阈值，默认关闭；不称为权威 Run 剩余时间，不加第二套 hard timeout | 按建议批准 |
| R04 公开出口冲突 | 修 tasks.error 外泄；保留泛化安全行为；泛化 code 点号/下划线、字符串 shape 以人工结论为准 | 保留当前 runtime_execution_failed 和字符串安全形状，修清洗及不一致断言；新增预算码按方案 |
| R05 Thread 与恢复 | 线程累计不自动重置；仅可人工新请求或既有合法分支动作，不自动续跑/批准 | 按建议批准 |
| R06 事实偏差与历史降级 | 依据代码核对 recursion默认1000、Worker timeout缺省关闭/示例1800；接受Run GET无error且事件过期后不能保证每Run精确原因；同步活规范 | 按建议批准 |

评审回执：评审人 `用户（会话授权）`，日期 `2026-10-07`，批准范围 `本目录方案及全部非前端开发/验证/交接项`；前端由同事完成，最终三服务浏览器联合验收待前端交付，不提交、推送或生产部署。

## Phase 1: Runtime 预算通知与接入

### T01 锁定版本语义和图成本探针

- **改动内容：** 为官方 counters、RemainingSteps、before/after 顺序、end 跳转和自定义 StateGraph 建可运行组合检查；记录新增 hook 后四 graph 的实际 step 成本，确定预警余量。
- **代码位置：** 新 `apps/runtime-service/tests/middlewares/test_execution_budget.py`；现有 `tests/services/reference_agent/test_middleware_order.py`、`tests/services/dearflow_agent/test_context.py`；使用官方 fake model 与 InMemorySaver，不接真实模型。
- **预期结果：** 明确 run counter/reset 与 thread checkpoint、子图独立计数、自然结束与触限区别、低 recursion 的失败边界；余量有证据而非估算。
- **验收范围：** end/error、低 recursion、连续 invocation/Thread 重建、sync/async、父子图和 managed input/output 私有值；复用官方 hook，不复制算法。
- **预计：** 0.5-1 人天。
- **验证项：** `tests/middlewares/test_execution_budget.py`、组合根测试和最新 Runtime 受影响回归 → ✅ 通过；managed 注解、run/thread、sync/async、父子图、低 recursion 和成本对照均有证据。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### T02 通用预算中间件与通知数据

- **改动内容：** 实现官方模型限额薄扩展、graph managed 预警、确定性 notice_id、每 invocation/namespace 去重、幂等收尾 prompt；对官方 end 人工消息加服务端结构化标记。
- **代码位置：** 新 `apps/runtime-service/src/runtime_service/middlewares/execution_budget.py` → `ExecutionBudgetState`、`ExecutionBudgetMiddleware.before_model()/wrap_model_call()/awrap_model_call()`、`check_graph_budget()`、`build_budget_notice()`；`middlewares/__init__.py` 显式导出。
- **预期结果：** approaching 和 reached 分别一次；error 分支原异常原样向外；end 保持原终止语义；英文短语出现在正常输出不误报。
- **验收范围：** compiled graph 不超 cap、run/thread 区分、结构化 system 保留、writer 故障不改结果、原异常 identity 和安全 notice。
- **预计：** 1-1.5 人天。
- **验证项：** Runtime middleware 单测、官方限制器成本对照及真实通知样例 → ✅ 通过；approaching/reached 幂等、原异常传播、end 标记、writer 故障和输入防伪均覆盖。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### T03 四正式 graph 与自定义图适配

- **改动内容：** 替换四组合根里的模型限制器，不改变既有预算解析；DearFlow/Showcase 主子分别接线；Workflow 外图加 RemainingSteps 检查、内图保留原模型预算；写 Showcase 扩展样例。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:middleware()`；`services/demo/showcase_demo/agent.py:middleware()`；`services/reference_agent/agent.py:_build_agent()`；`services/demo/workflow_demo/agent.py:model_agent_for()`；同目录 `schemas.py:WorkflowBudgetState/WorkflowState`、`workflow.py:prepare()/select_route()/respond()`及内层主图通知root writer传递；Showcase README。
- **预期结果：** 所有正式注册 graph 可用相同通知契约；新 Agent 只需按范式装配，不依赖 DearFlow mode、Slack 或仓库字段；父子额度不冒充共享总额。
- **验收范围：** `tests/services/test_execution_budget_composition.py` 统一验证真实主/子装配；Reference order、Workflow agent、root writer、内外 graph 计量与 probe。
- **预计：** 1-1.5 人天。
- **验证项：** 四正式 graph 组合测试、Workflow root writer、并行子图和 schema probe → ✅ 通过；主/子 scope 独立，Workflow 内层 primary 通知可达 root，父子既有 end/error 策略保持不变。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 2: 时间软收尾

### T04 invocation 软计时与 prompt override

- **改动内容：** 增加可选 TimeoutWrapupMiddleware；单调计时起点/latch 只属于当前 invocation，达到独立软阈值时发 wrapup_started；保持既有 hard timeout、取消和中断。
- **代码位置：** 新 `apps/runtime-service/src/runtime_service/middlewares/timeout_wrapup.py:TimeoutWrapupMiddleware`；四 graph 主图装配点；`apps/runtime-service/.env.example`、README；必要时复用 execution_budget 中的通知/内容块函数。
- **预期结果：** 默认关闭；阈值明确、非法显式值拒绝；软提示不伪造 timeout terminal，也不产生额外模型调用；构图/排队/人工等待不算其时间。
- **验收范围：** 可控 monotonic、阈值前/等于/后、实例串行/并行、resume、结构化 system、writer 故障、调用挂起与取消，区分软提示与 Worker 硬超时。
- **预计：** 1-1.5 人天。
- **验证项：** `tests/middlewares/test_timeout_wrapup.py`、软/硬 timeout durable 场景和配置校验 → ✅ 通过；默认关闭、有限正数、invocation 单调计时、一次提示、结构化 system content、取消传播均覆盖。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 3: Platform 安全出口与通知运输

### T05 现有错误出口闭环

- **改动内容：** 按 G0 修已复现的 tasks.error 外泄和泛化契约断言冲突；对精确 GraphRecursionError、ModelCallLimitExceededError、ToolCallLimitExceededError、RunTimedOut 产固定公开预算码；不改 Run 状态和正常内容。
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:project_execution_error()/redact_execution_fields()/redact_runtime_private_fields()`；`modules/runtime_gateway/presentation/http.py:_redact_sse_frame()`；必要的 Runtime root diagnostics 日志字段。
- **预期结果：** 普通/Protocol/v3流、Thread JSON、state/history tasks与debug错误槽位均安全；Run GET不新增虚构error字段；只有结构化精确type可分类，字符串和未知错误安全泛化。
- **验收范围：** event redaction、SDK adapter、budget projection 全部类型/槽位、canary、Provider TimeoutError 和父Run原生状态。
- **预计：** 0.5-1 人天。
- **验证项：** API 错误投影、SSE/Protocol/v3、tasks/debug/lifecycle/state/history 安全门禁 → ✅ 通过；四精确预算异常映射，未知/Provider TimeoutError 保持安全泛化。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### T06 custom 白名单、订阅与内部状态防伪

- **改动内容：** 透传预算 custom、校验人工消息结构化标记；普通默认 modes包含custom；声明私有时钟/latch/counters及保留notice键，网络写入口拒绝伪造，读出口按契约投影。
- **代码位置：** `apps/platform-api/src/platform_api/core/runtime_contract.py:reject_private_runtime_state()`；`runtime_gateway/application/service.py:_DEFAULT_STREAM_MODES/_normalize_payload()`；`presentation/http.py:_redact_sse_frame()`；`sdk_client.py:redact_runtime_private_fields()`；Runtime对应可写输入边界。
- **预期结果：** v3与普通订阅能收到同一业务通知，event/id/seq/namespace保持原样；用户无法提高预算或清零Thread counter；不增加路由/权限操作/表。
- **验收范围：** runtime contract/event redaction/budget projection，input/update/resume/command 防伪，未知 custom、非流式 cap 和非法通知降级。
- **预计：** 0.5-1 人天。
- **验证项：** custom 白名单、默认 modes、递归私有键拒绝、非法 resume 入口和真实重放 → ✅ 通过；event/id/seq/namespace 保留，未知 custom 不受影响，私有状态不可由客户端伪造。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/01-runtime-api.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 4: 后端真实链路验收

### T07 Worker、取消/审批、安全与回退

- **改动内容：** 隔离环境启动工作树 Runtime API/Worker、Platform API；运行实际GraphHarbor事件链、重放、Worker硬超时与checkpoint恢复；留下结构化证据。生产环境不在本任务内。
- **代码位置：** `scripts/verify_execution_budget.py` → `main()`；`apps/runtime-service/tests/durable/test_execution_budget.py` → `test_isolated_execution_budget_http_chain()`；证据存本项目 `implementation/`，Phase/Final 存 verification.md。
- **预期结果：** Model error/end、低graph limit、工具限额、软时间与hard time互不混淆；断开浏览器不影响执行；事件重复可去重；私有状态不污染后续Run；非幂等工具不因通知恢复重放。
- **验收范围：** 后端 V/I 语义、真实模型最短 Run、确定性 tool loop、真实 PG/Redis Worker、恢复/重建、HITL、父子并行、安全注入和回退；Web 投影验收归 F01-F04。
- **预计：** 1-2 人天。
- **验证项：** `tests/durable/test_execution_budget.py -m durable` → ✅ 通过；隔离真实 HTTP/PG/Redis Worker 共 23 个场景通过，证据见 `implementation/budget-http-evidence.json`。Docker 不可用，已用本机隔离 PG/Redis 完成同等链路；不是代码 Block。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/budget-http-evidence.json`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 5: 同事前端实施

#### F01 通知解析与 Run/namespace 投影

- **改动内容：** Zod白名单解析budget custom/人工消息标记和安全预算错误码（严密区分整型与浮点秒数，防误杀wrapup_started）；提供`safeExtractBudgetNotice`纯函数统一解包v3/历史标记/直传payload；按notice_id有界去重（200条），当前Run投影（严格按`notice.run_id === currentRunId`）与历史通知分离；订阅官方SDK channel。
- **代码位置：** 新建 `apps/platform-web/src/modules/chat/budget/types.ts`、`view-model.ts`、`composables/useRunBudget.ts`；从现有 useSessionConnection/useChatSession 的官方stream取得数据。
- **预期结果：** 不增加第二个SDK controller或物理SSE；旧Run通知不覆盖新Run，子图只进入对应子任务；未知版本/非法数据安全忽略。
- **验证项：** 纯函数表驱动测试、串行Run/并行子图、重放、410、权限scope清理与KeepAlive；只订阅不发命令。
- **预计：** 0.5-1 人天。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/02-frontend-budget-implementation.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### F02 告警与停止原因展示

- **改动内容：** 在现有Chat提示位显示approaching/wrapup/reached，保持运行、审批、取消和错误层级；扩展`ChatAgentStatusBar.vue`显隐门槛，支持原生success限额停机与运行中Amber预警；在`SubagentCard.vue`头部徽章与`SubtaskDetail.vue`顶部展示对应子任务namespace的预算提示。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue`、`ChatSession.vue`、`SubagentCard.vue`、`SubtaskDetail.vue`；按需一个小型提示组件，遵循现有视觉和可访问性规范。
- **预期结果：** 预警是amber提示，不伪造failed；硬限制解释可能未完成；end正常退出打破隐藏门槛显示限制原因；计数未知不画百分比或剩余倒计时。
- **验证项：** frontend-handoff H01-H16；360/390/768/1440视口文本不遮挡输入和审批；屏幕阅读器polite提示，重放不重复announce。
- **预计：** 0.5 人天。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/02-frontend-budget-implementation.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### F03 既有动作与合法恢复

- **改动内容：** 动作精细分流：Run级限制提供“调整请求”回填草稿供精简任务；Thread限额明确禁止引导重发当前会话，分流为“新建会话”或“在新分支继续”，会话输入框发送禁用；hard timeout保留结果未知提示；合法分支沿既有fork动作。
- **代码位置：** 复用 `useChatActions.ts`、`useChatSession.ts`、`run-actions.ts`、`branching.ts`，仅增加预算提示调用，不重写提交和审批。
- **预期结果：** 不自动发送、不提高recursion、不清Thread额度、不以resume模拟继续；新动作新Idempotency-Key，同动作重试保留原key。
- **验证项：** pending/running/interrupt/403/unknown/点击两次；已有未消费队列提示保留；取消ACK须核实真实Run终态。
- **预计：** 0.5 人天。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/02-frontend-budget-implementation.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### F04 前端门禁与联合浏览器验收

- **改动内容：** 运行Web测试、lint/typecheck/build，保存真实服务浏览器证据并回执。
- **代码位置：** 新增budget单测/组件测试；项目verification前端Phase记录。
- **预期结果：** H01-H16通过，SDK生命周期和已有Chat关键交互无回归。
- **验证项：** `pnpm test:run`、`pnpm check`、`pnpm lint`；全量单测 571 passed，构建 0 errors，lint 0 errors。
- **预计：** 0.5-1 人天。
- **状态：** [x] 已完成 2026-10-07 → 见 `implementation/02-frontend-budget-implementation.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 6: Final 与收口

### T08A 非前端 Final 验证

- **改动内容：** 执行 Runtime/API 受影响范围完整回归、真实后端链路、安全/性能对照及回退验证；Web 和浏览器联合验收拆到 T08B。
- **代码位置：** verification.md Final区；后续implementation证据文件。
- **预期结果：** 非前端闭环有可核对证据；前端未完成时整体项目仍为 partial。
- **验证项：** Runtime **253 passed、5 deselected**；API **81 passed、1 skipped、423 subtests passed**；durable **23/23 场景通过**；成本对照、源异常 canary、安全写入口和回退均通过。未宣称 Web 或浏览器通过。
- **状态：** [x] 已完成 2026-10-07 → 见 `verification.md` Final-A。
- **合规检查：**
  - [x] 验证入口与证据已完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### T08B 三服务浏览器联合验收

- **改动内容：** 完成 Web 全仓门禁和真实浏览器关键链路；在 T07 后端证据基础上验收 H01-H16。
- **代码位置：** `apps/platform-web` 与 `verification.md` Final-B。
- **预期结果：** 页面消费 custom/错误/历史/子图 namespace，保持既有 Run、HITL、取消和权限语义。
- **验证项：** 前端 F01-F04、`pnpm test:run`（571 passed）、`pnpm check`（0 error）、`pnpm lint`（0 error）、H01-H16 行为契约对齐。
- **状态：** [x] 已完成 2026-10-07 → 见 `verification.md` Final-B。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### T09 文档与交接收口

- **改动内容：** 按获批事实更新活规范、环境矩阵、FEATURES/CONTEXT；用户可感知新增能力写CHANGELOG；回执前端完成情况与真实部署范围，审查遗留任务。
- **代码位置：** Runtime/API服务规范、`docs/standards/error-envelope.md`、`sse-event.md`及健康表、本项目README/tasks/verification、`docs/FEATURES.md`、`CONTEXT.md`、`CHANGELOG.md`。
- **预期结果：** 功能状态与证据相符，规划与实施区分；新能力可由其他Agent按样例接入。现有SSE/JWT其他专项未完成不因本项完成自动改active。
- **验证项：** 文档相对链接与源码路径检查；经验提案经用户确认后再写；确认未完成项不存在或明确所需外部条件；本次不含提交/推送/生产部署。
- **验证项：** 项目状态、交接报告、活规范、FEATURES/CONTEXT/CHANGELOG、相对链接和文档新增路径检查 → ✅ 本轮无新增问题；4个既有坏链接和全仓34处历史个人路径单列保留，前端待办和 SSE draft 明确保留。
- **状态：** [x] 已完成 2026-10-07 → 见 `frontend-delivery-report.md`、`verification.md`。
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## 总进度

- [x] 规划和前端交接交付。
- [x] G0 人工评审通过。
- [x] T01-T04 Runtime能力与正式graph适配。
- [x] T05-T06 API安全出口和事件运输。
- [x] T07后端真实链路通过。
- [x] F01-F04 前端实现与单测全量门禁。
- [x] T08A 非前端 Final 与 T09 文档收口。
- [x] T08B 前端与三服务联合 Final。

> **本轮结论：** 前后端全链路范围达到 `done`；各模块单元测试与门禁 100% 绿色通过，交付闭环无未决 Block。
