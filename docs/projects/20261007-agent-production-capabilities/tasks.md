# Agent 运行准备幂等与有界重试 - 任务拆分

## 进度规则

本文件是唯一进度来源。`[x]` 表示真实完成，`[ ]` 表示未做；规划完成不把实现任务勾选。前端交给同事不等于任务完成，联合 Final 需要同事的实际验证证据。实施记录后续写入本目录 `implementation/`，不根据该目录数量推断进度。

2026-10-07 用户批准方案并授权完成所有非前端开发与验证。T10 前端实现及其浏览器验收交同事，不属于本轮开发范围；本轮完成交接报告。整专项 Final 仍须合并同事证据，本轮单独记录非前端交付的验证结论。

## 已完成的规划工作

- [x] P01：读取 CONTEXT、三服务入口/规范、相关经验和跨服务标准；核对本机 open-swe/当前代码与依赖版本。
- [x] P02：追踪 prepare、task、模型、提交幂等、Worker 重排和 cron 的真实边界，修正同事方案中的 dispatch/on_failure 假设。
- [x] P03：形成三层职责、文件级计划、前端交接和完整验证矩阵。
- [x] P04：执行现有相关基线测试，37 passed；锁定版 ToolRetry 非匹配异常绕过 on_failure 的运行探针见 verification.md。

## G0：人工方案评审

- [x] **改动内容：** 评审 prepare identity/私有标记、资源恢复、副作用窗口；评审模型/task 重试负责人和 1 次重试上限、deadline、只读角色集合、Worker 终止边界、诊断 DTO；确认本期不开发自主唤醒。
- **代码位置：** 本项目 `plan.md`、`frontend-handoff.md`；此项不写业务代码。
- **预期结果：** 明确获批范围，Runtime/后端可实施；前端由同事认领。不得由 AI 自批。
- **验证项：** 下表填入真实记录；任何范围调整同步方案、任务和交接。

| 批准人 | 日期 | 批准范围 | 修改/后置项 |
| --- | --- | --- | --- |
| 用户（会话中明确批准） | 2026-10-07 | 已规划的 Runtime/Platform API 非前端任务与验证 | 前端 T10 由同事完成；本轮提供实际交接报告；无生产发布或 Git 提交授权 |

## Phase 1：prepare 生命周期与信任边界

### T01：公共 prepare state 与 latch

- [x] 已完成 2026-10-07；真实 create_agent/checkpointer 5 项通过，覆盖无新消息的新 Run、组件合并、config/revision/namespace/fork 身份和资源修复。
- **改动内容：** 新增有界私有 marker、可信 Run/namespace 读取和 canonical fingerprint；成功后提交，失败/无可信身份不缓存；每次 hook 的授权/资源检查在 latch 外；不复制 static prompt 或凭据。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/middlewares/run_prepare.py` → `RunPrepareState`、`RunPrepareMiddleware.abefore_agent()`，通过该模块公开导出和直接导入接入；复用 `runtime/resolver.py` 的 config_hash 和 `middlewares/message_queue.py` 的 Run ID 读取惯例。
- **预期结果：** 同 Run/配置/namespace 的已完成组件可复用；新 Run、revision/config 变化重新 prepare；父子组件互不覆盖；state 不按 Run 无限增长。
- **验证项：** 新增 `apps/runtime-service/tests/middlewares/test_run_prepare.py`：真实 `create_agent`+checkpointer 验证 latch、失败不标记、namespace 分离、同 Run factory 重建、新 Run 无新消息、旧 checkpoint 无字段、映射保留/上限；禁止只 mock hook 就认定恢复完成。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。细节见 `implementation/01-runtime-reliability.md`，证据见 verification T01。

### T02：工作区消费者接线及资源检查

- [x] 已完成 2026-10-07；两 workspace 复用公共 prepare，目录/marker/symlink 检查与幂等创建通过；真实 Worker 两个崩溃窗口、Skills 跨进程恢复通过。
- **改动内容：** 两处 WorkspaceMiddleware 复用公共 latch；backend 加必需目录/marker 存在检查。missing 可以用原幂等 prepare 修复，篡改/symlink/scope 错误继续终止；prepare 内部文件创建语义保留。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py` → `_ThreadWorkspaceBackend.prepare()`、`is_prepared()`、`WorkspaceMiddleware`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` → `DearWorkspaceBackend`、`WorkspaceMiddleware`；两处 `agent.py` 传固定 component/revision 和 resolved config_hash，before-agent 复用公共实现。
- **预期结果：** 两个真实 Agent 使用同一通用机制；factory/Backend 每次可重建而资源不重复初始化，不覆盖用户修改；probe 不创建资源。
- **验证项：** 扩展现有 `tests/services/showcase_demo/test_backend.py`、`test_agent.py`，DearFlow `test_agent.py`/`test_restart.py`；覆盖副作用成功后、checkpoint 前失败再次执行，不重复/覆盖 seed 文件；缺根修复与路径篡改必须分开断言；现有 Skills `test_skill_restart.py`、Memory 和 MessageQueue 回归。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T02/T11。

### T03：保留字段拒绝注入与公开剥离

- [x] 已完成 2026-10-07；共享保留字段拒绝输入/Protocol/state 注入，HTTP/SSE/state/history 安全投影通过；普通 ToolMessage artifact 保真已修复并回归。
- **改动内容：** 复用既有 `PRIVATE_RUNTIME_STATE_KEYS` 加 `runtime_prepare`；既有 sanitizer 剥离其公开输出。检查 Run/stream/Protocol run.start/state-edit/fork/cron 所有消费者，不散落写 guard。
- **代码位置：** `apps/platform-api/src/platform_api/core/runtime_contract.py` → `PRIVATE_RUNTIME_STATE_KEYS`、`reject_private_runtime_state()`；`apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` → `redact_runtime_private_fields()`；既有 `application/service.py` 的 `_normalize_payload()`、`update_thread_state()`、Protocol 路径回归。
- **预期结果：** 客户端无法伪造已准备状态；state/history/checkpoints/SSE 看不到私有 marker；不改正常 messages、tool args 或公开 Run 状态。
- **验证项：** `apps/platform-api/tests/test_runtime_delegation.py`、`test_run_requests.py`、`test_runtime_gateway_sdk_adapters.py`、`test_run_diagnostics.py`；嵌套注入、普通/Protocol/SSE 入口均拒绝，未知字段安全剥离，message 正文保真。SDK 中直接调用 Runtime input 的边界同步确认。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T03，直接 Runtime 仍是受信平台委托边界，不开放绕过网关的用户输入。

## Phase 2：有界重试与安全失败

### T04：typed retry predicate 和终止错误

- [x] 已完成 2026-10-07；typed 白名单、安全终止封装、自身 deadline 标准化通过；真实 provider timeout 不重排 Run，PG 错误仍恢复。
- **改动内容：** 只接受 typed provider/transport 瞬时失败与已评审 HTTP 白名单；运行显示分类仍复用现有 classifier。新增安全 `RuntimeExecutionError`，隔离模型 deadline/连接错误耗尽与 Worker 基础设施重排。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/middlewares/retry.py` → `is_transient_model_error()`；`apps/runtime-service/src/runtime_service/runtime/errors.py` → `RuntimeExecutionError`；`middlewares/model_call_timeout.py` → `ModelCallTimeoutMiddleware.awrap_model_call()` 仅将自身到期变为标准 ModelTimeoutError；`observability/errors.py` 补 typed 显示映射，不能放宽 unknown 文本重试。
- **预期结果：** 429、允许的 5xx/transport/deadline 可重试；401/403/400/context、409/425、未知缺陷、中断/取消不重试；RuntimeExecutionError 外层类型不会让 Worker 重排。
- **验证项：** 新增 `apps/runtime-service/tests/middlewares/test_retry.py` 的参数矩阵：标准 ModelError 与 SDK 类型、可靠 status、response.status、异常 cause、伪同名/文本、缺 status、控制流；断言 RuntimeExecutionError 的 code 与不含 secret 的字符串。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T04/T11。

### T05：复用官方 retry 的薄扩展与预算

- [x] 已完成 2026-10-07；官方 retry 薄扩展及真实 v3 三种 delta、首错/二次出流失败、取消、sync/async、并行子图预算隔离通过。
- **改动内容：** `RuntimeModelRetryMiddleware`/`DelegatedTaskRetryMiddleware` 调用官方 retry 实现；最多 2 次 attempt，记录真实调用计数；task 按 graph 只读角色筛选。先做当前 callbacks/stream 的可运行小实验，绑定每调用 emitted 标志；content/reasoning/tool delta 对外发出后禁止模型/task retry，未知角色/未经验证路径直接透传；sync/async 一致，生产以 async 为主。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/retry.py` → 两个 middleware 的 `wrap_model_call()`/`awrap_model_call()`、`wrap_tool_call()`/`awrap_tool_call()`；`runtime/errors.py` 的终止错误仅作用于已确认模型边界。
- **预期结果：** 不复制 retry loop；取消停止 sleep/handler；非匹配异常仍传播；耗尽不会伪造 AIMessage 成功；只读 task 的安全失败可反馈给父模型。
- **验证项：** `tests/middlewares/test_retry.py` 用确定性 handler 测首错后成功、耗尽、未知错误一次即终止、取消退避、不同 role 同名 graph 隔离、sync/async parity；真实 v3 流首次尝试在 content/reasoning/tool delta 后失败断言 attempts=1，第二次尝试才出流失败断言 attempts=2、outcome=failed，均没有拼接/重复；并行子图 emitted 标志隔离，计数与消息配对正确。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T05/T11。

### T06：生产主/子图接线和单一负责人

- [x] 已完成 2026-10-07；DearFlow/Showcase 主/子图单一负责人，真实只读任务最多 2 次、写子图只重试当前模型；真实客户端 SDK 参数与辅助模型/动态 builder 分离通过。
- **改动内容：** DearFlow/Showcase 执行模型和动态 builder 显式 SDK max_retries=0；主图模型和写操作子图单次模型重试；DearFlow `researcher()` 实际只读 `general-purpose`、Showcase `research` 由父 task 重试，子模型不再重试。不同 graph 不能复用同名角色权限假设。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` → `_build_agent()`、`middleware()`；`services/dearflow_agent/subagents/researcher.py` → 角色声明核对，不无故改名；`services/demo/showcase_demo/agent.py` → `_build_agent()`、`middleware()`；`services/demo/showcase_demo/subagents.py` → `build_subagents()` 按角色选择模型 retry 负责人；Reference `agent.py` 仅按有证据的需要消除重复，不重写其测试适配。
- **预期结果：** 无已公开 delta 的只读 task 模型错误物理尝试最多 2 次；主/写角色模型调用最多 2 次且已执行工具不重复。Reference 和独立 one-shot/图片调用不受全局改动。DearFlow 记忆/技能共享对象按方案保留辅助模型，单独验证原预算；不能靠 model_copy 修改 client。
- **验证项：** 现有 Reference `test_middleware_order.py`；Showcase `test_agent.py`、DearFlow `test_agent.py`/`test_subagents.py` 扩展；直接调用各角色并注入两次 provider 错误，确认角色实际工具列表、SDK 参数、父子重试顺序、attempt 总数；写角色先完成工具再遇 429，写入计数必须保持 1。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。Reference 保持现有接线，证据见 verification T06。

### T07：task 可恢复错误与 middleware 顺序

- [x] 已完成 2026-10-07；只读 task context/prompt 与 transient 安全反馈通过；写角色 context 错误传播且写入一次，权限/未知/控制流不吞掉。
- **改动内容：** 仅已声明只读角色的 `task` context/prompt 可修复 provider 错误通过现有 `ToolErrorMiddleware` 返回安全错误；`on_tool_error` 复用组合根同一只读集合筛选 request，写/未声明角色失败传播。task transient 耗尽仅在已筛选只读角色内反馈。已公开 delta 导致禁止重试时，薄扩展精确处理只读 task 的已确认 transient，返回 failed 而非 exhausted；不能指望官方 on_failure 执行。通用 readonly exhaustion 回调只能返回已批准有界 code；其他错误继续抛出。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/errors.py` → `tool_error_content()`/`on_tool_error()` 的精确 task 分支；`middlewares/retry.py` → task failure callback；组合根接线顺序。
- **预期结果：** 只读角色 provider 上下文太长可以由父 Agent 调整 delegation；写角色、403/权限、缺根、未知程序错不被模型“忽略继续”；ToolMessage 保留 `name=task`、原 tool_call_id、`status=error` 和既有结构化错误字段。
- **验证项：** 扩展 `tests/tools/test_tool_errors.py`、Showcase/DearFlow `test_tool_errors.py`：标准与未经证明的 invalid_prompt、unknown、cause、secret canary；重点验证 `retry_on=False` 时 retry 不执行 on_failure，但外层 ToolError 能接住获批只读角色的可修复错误；写角色完成工具后发生 context 错误仍终止、写入次数 1；task 生命周期/历史失败展示保持真实。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T07。

## Phase 3：诊断与前端交接落地

### T08：Runtime 有界 prepare/retry 诊断

- [x] 已完成 2026-10-07；两个有界事件/诊断数组、安全投影、去重/截断、disabled/不可用与观测失败不影响执行通过。
- **改动内容：** 记录准备复用/修复、重试负责人/次数/结果的安全 metadata；查询输出两个可选数组，不扩展 SSE；沿用查询上限和 unavailable/partial。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/diagnostics.py` → `safe_fields()`；`observability/query.py` → `_EVENTS`、`empty_diagnostics()`、`_project()`；`run_prepare.py`/`retry.py` 调现有 log/Langfuse API。
- **预期结果：** 观测不可用不影响 Agent；同一 Run/namespace 关联正确；两条事件最多 20 条、输出有界；旧记录缺字段不表示零次失败。
- **验证项：** `tests/observability/test_diagnostics.py`、`tests/observability/test_run_diagnostics.py` 扩展；事件范围、负数/NaN/超长、secret canary、截断、重复 observation、Langfuse disabled/timeout/429 和恢复重建。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。HTTP 诊断经过真实 Langfuse SDK 和本地受控观测端点；非现役 Langfuse部署，见 verification T08。

### T09：Platform diagnostics 可选契约

- [x] 已完成 2026-10-07；v1 两组 optional DTO、旧响应兼容、strict bounds/unknown strip/权限/no-store 通过；实际 HTTP 响应和 OpenAPI 已抓取供同事使用。
- **改动内容：** 增加 strict、有界 `preparations`/`retries` DTO；旧 v1 缺字段默认空数组，非法新数据安全拒绝，不反射 body；维持 diagnostics-read/no-store/Run 状态。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` → 新摘要 DTO 和 `RuntimeDiagnostics`；现有 diagnostics 查询/路由通常只回归；`apps/platform-api/tests/test_run_diagnostics.py`。
- **预期结果：** API 保持现有 GET，不新增 retry endpoint/operation；上游失败尝试不改变最终 run_status；不把 provider_auth_failed 当平台登录失效。
- **验证项：** 旧/新 payload、scope/项目/Thread/Run 拒绝、可选字段、strict bounds/unknown strip、查询可用性/耗时和 HTTP 错误、无新消息/模型调用；同步交接 DTO/OpenAPI 样例。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。证据见 verification T09 和前端交接。

### T10：前端同事实施与浏览器验收

- [x] 代码实施、自动化门禁及 Playwright + Chromium 全链路端到端闭环验证已全部完成 2026-10-08。
  - 核心架构实施：扩展 types/view-model，拆分 RunPreparationsSection 与 RunRetriesSection 专职展示子组件并接入 RunDiagnostics；49 项定向单测全绿、vue-tsc 0 错误、eslint 0 错误、pnpm build 成功；见 [02-frontend-resilience-diagnostics.md](implementation/02-frontend-resilience-diagnostics.md)。
  - 全链路三服务与真实模型端到端自动化测试：使用 Playwright 驱动真实 Chromium，覆盖登录 -> 工作区 -> 进入项目 Chat -> 选定 reference_agent -> 发送真实模型问答（deepseek-v4.1-flash）产生流式响应 -> 切换至轨迹排障视图 -> 展开运行诊断面板并测试诊断重新拉取与刷新。
  - F01-F10 专项浏览器视觉与安全验收：F01 旧版 DTO 兼容隐藏、F02/F03 准备与调用重试（主 Run 成功时 Amber 琥珀色降级，严禁标红）、F04/F05 子任务角色与重试耗尽展示、F09 敏感 canary/未知字段剥离与防注入、F10 移动端 390x844 响应式布局全部断言通过。所有过程保留完整高保真截图证据（见 `tests/e2e_screenshots/`）。
- **改动内容：** 扩展 RunDiagnostics schema/view-model，拆分专职展示子组件呈现准备结果及受管调用重试尝试；实现 strict integer attempts、role 正则安全防注入、子项 default(null) 容错、旧响应默认空数组兼容、主 Run 成功时内部重试失败降级为 Amber 琥珀色警示防误报、空数组完全隐藏无冗余占位卡片；维持 useRunDiagnostics 原生防竞态。
- **代码位置：** `apps/platform-web/src/modules/chat/diagnostics/{types.ts,view-model.ts}`、`apps/platform-web/src/modules/chat/components/trajectory/{RunDiagnostics.vue,RunPreparationsSection.vue,RunRetriesSection.vue}` 及对应 spec；E2E 自动化测试脚本 `tests/e2e_resilience_test.py`。
- **预期结果：** 主 Run 成功但有失败尝试时正常显示 Amber 警示；空准备/重试数据时区域隐藏；未知/canary 字段自动 strip 剔除；停止和审批无新增自动重发。
- **验证项：** 定向单测 6 套件 49 项全部通过；`pnpm typecheck` 0 errors；`pnpm lint` 0 errors；`pnpm build` 生产打包成功；Playwright + Chromium 全链路自动化端到端测试 100% 通过；真实模型流式对话与诊断刷新验证成功。
- **合规检查：** [x] 代码实现完成；[x] 验证项已执行；[x] tasks.md 状态已更新；[x] implementation 记录已归档；[x] E2E 截图证据已留存。

## Phase 4：故障与最终验收

### T11：隔离 Worker/HTTP 故障注入

- [x] 已完成 2026-10-07；本机 PostgreSQL 17/Redis 8 + 独立 API/Worker/HTTP provider 实测两 crash 窗口、PG 故障、模型/task预算、并行部分流、取消/审批/Run deadline、安全出口和回退通过。按用户要求不使用 Docker。
- **改动内容：** 按 verification.md 集成/I01-I11 和 E2E 场景运行独立 API/Worker、PG/Redis 隔离资源，真实模型的受控故障服务不含生产凭据。记录两个 prepare crash 窗口、模型/task/Worker 重试次数、部分流保护、恢复身份和唯一终态。
- **代码位置：** 优先复用 `apps/runtime-service/tests/fixtures/tool_error_platform.py`、`tests/services/dearflow_agent/test_tool_error_platform.py` 的隔离范式；新增 `apps/runtime-service/tests/e2e/test_run_reliability.py`、必要时一个最小 fixture；不创建长期生产探针 Agent 或全局模拟成功路径。
- **预期结果：** provider transient/耗尽不重排整个 Run；PG/Worker 真实故障仍能恢复；同 Run 身份稳定、资源不重复、写 task 不重放；HTTP/SSE/history 安全且一致。
- **验证项：** 真正启动进程并终止隔离 Worker 后恢复，保留命令、版本、attempt counter、checkpoint/Run ID、日志、最终状态；ASGI/mock 的证据单列不能代替 Worker 测试。缺环境须记录尝试替代办法及所需条件。
- **合规检查：** [x] 实现；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。scheduled/fork 授权使用锁定契约回归，FIFO/Skills/Memory 使用真实 PG；浏览器验收随 T10 交同事。

### T12：非前端 Final、回退与文档同步

- [x] 非前端范围已完成 2026-10-07；相关扩大回归、真实 API/Worker 故障及回退、安全/耗时/文档检查通过，前端报告已冻结。按用户范围将联合浏览器 Final 交 T10 负责人回填，不视为已完成。
- **改动内容：** 执行非前端相关扩大回归、安全/耗时/回退；更新现状与规范，冻结交接报告；调用 verify-change 写独立非前端 Final。联合三服务浏览器验收保留为 T10 待交付项。
- **代码位置：** 本项目 `verification.md`/`README.md`、`tasks.md`；`docs/CONTEXT.md`、`docs/FEATURES.md`、`docs/CHANGELOG.md`；Runtime 开发/验证规范、Platform 网关标准；跨服务标准仅按实际契约变化同步。
- **预期结果：** 本轮非前端实现与验证 done；专项整体 partial 等待 T10，不以阶段测试替代整单完成；回退无需删除用户数据/checkpoint。
- **验证项：** 保留新 checkpoint，恢复旧接线读取/执行，再切回新接线通过；Ruff/format/diff 通过；本次 13 份文档零违规，19 个本地链接/实际 JSON 通过。全仓 docs check 的 34 条既有路径问题与 HEAD 对照确认，未称全仓通过。见 verification 的非前端 Final。
- **合规检查：** [x] 实现/交接；[x] 验证；[x] 任务状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。经验提案待用户确认后写 lessons；专项 partial 不触发标准 draft 毕业；未提交、推送、部署。

## 接线顺序验收要求

按当前官方 wrap 组合语义用行为测试证明，而非只比类名列表：

- model：授权/模型选择在外层；官方调用限额不被重试清零；retry 外层记录汇总，内层 ModelError/ModelCallTimeout 记录每次 attempt；deadline 覆盖真正 provider 调用。
- tool：RuntimeConfig/Workspace 校验在 retry 外；ToolError 在 task retry 外；task 限额和并发保持当前语义。重试计数不能只依赖 logical tool_calls counter。
- child：只读 task 交父重试，子图不叠模型 retry；写 child 只重试当前模型请求。官方工具、中断、namespace 和 history 机制保留。

## 总体进度

- [x] 规划文档与基线证据交付。
- [x] G0 人工批准。
- [x] Phase 1 prepare/信任边界完成。
- [x] Phase 2 重试/生产接线完成。
- [x] Phase 3 Runtime/API 诊断与契约冻结完成。
- [x] Phase 3 前端 T10 代码实施与自动化门禁完成。
- [x] Phase 4 本地 API/Worker/provider/PG 故障与回退完成。
- [x] Phase 4 非前端 Final/文档最终检查。
- [ ] 全专项三服务浏览器联合 Final 待同事回填。

自主唤醒、生产发布和 Harness 重构不属于待完成 Task；其 deferred 理由已在 plan.md 中写明，不作为功能本期 done 的隐含条件。
