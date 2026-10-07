# Agent 运行生命周期超时治理 - 任务拆分

> **当前执行状态：全链路完成（done，2026-10-08）。** 用户已在浏览器端端到端完成验收（含前端超时警示胶囊、停止确认时序、排队未决死锁根除与切换自愈）；服务已安全停止；T01-T13及T12联合Final全部达成done。先前暂停与排查记录保留在verification.md。

> 2026-10-07 用户修订：GraphHarbor 按 LangGraph Server Worker 实现。T02/T05 的原“跨 attempt 不续期/模型 Worker 重试”结果需由 T13 替代；其他已完成实现保留，T10/T11/T12 门禁继续有效。

### [x] T13：LangGraph Server Worker 语义对齐

- **改动内容：** 核对锁定官方 `langgraph-api==0.13.0`；预算改为每次 Worker attempt，模型/provider TimeoutError 不引发整图重试；官方配置默认、checkpoint handoff retry 与租约 generation 分离。同步当前方案及前端交接。
- **代码位置：** GraphHarbor `production_worker.py`、`run_store.py`、`run_state.py`；现有 `retry_counters`；本仓 `scripts/verify_run_timeout_budget.py`、项目文档与 Runtime 标准。
- **预期结果：** 同 Run 重试/交接在 checkpoint 上继续并获新 attempt H；一个 attempt 内工厂/主子 Agent 共享预算；硬限 timeout、模型 scope error、取消 interrupted；旧代次不可写 checkpoint/终态。
- **验证项：** 官方源码/隔离契约探针；真实 PG/Redis 回归、重复 drain/代次、fault retry 上限、候选双包冷安装；平台 HTTP/SSE 和 SIGTERM/新 PID 恢复；无私有预算泄露。
- **状态：** done，2026-10-07；官方4项、真实PG/Redis及checkpoint探针通过；正式PyPI post42完整12组平台HTTP通过，含模型error、SSE、SIGTERM和新PID接管。
- **原环境阻塞已解除：** 用户恢复后使用可用本机负载、独立native PG/Redis复验；原失败轮次保留在verification.md，不以提高生产H或旧deadline结果替代。
- **Task Completion Card：** 接管run `875b0bbd-3481-47ec-887f-c4638f589d1c`，PID `11475 -> 12285`；旧H=30结束后，新attempt H=20从checkpoint继续。每个已验Run租约释放、durable终态恰好1条，私有预算未泄漏。发布/锁定归T10，匹配回退归T12。
- **合规检查：** 实施记录02/03、当前方案/前端交接、两仓CONTEXT/FEATURES/CHANGELOG与相关规范已同步；Phase/Final分开，未通过轮次如实保留。

> 用户已于2026-10-06批准实施，10-07按官方Worker修订并完成正式发布与非前端验收，10-08完成前端超时治理实装（T11）及用户浏览器端端到端联调验证（T12，含排队死锁自愈）。全链路达 done。全仓既有外围失败另列，未冒充全绿。

## 本轮规划交付

- [x] P01：核对 open-swe 实际工作树、平台源码和锁定依赖，纠正“没有整体硬超时”的判断，记录来源与版本。
- [x] P02：完成时间语义、三服务与 Worker 分工、文件/函数位置、依赖门禁、验证计划及独立前端交接。
- [x] P03：完成新增文档的一致性、相对链接与纯文档改动检查；同步 FEATURES 和 CONTEXT，记录真实验证结果。8 份文档定向检查及 15 个项目相对链接通过；全仓原有 34 条绝对路径问题单独记录。

## Phase 0：人工评审

### [x] T01：批准本期预算范围与依赖边界

- **负责人：** 用户/人工评审人。
- **改动内容：** 确认单个 Run 的 H、G 默认值、首次排队/HITL 语义、协作式取消保证；确认 GraphHarbor 源码 owner、发布流程与同事前端职责。
- **代码位置：** 本项目 `plan.md` 第 8 节与 `README.md` 评审记录；此任务不改代码。
- **预期结果：** 形成明确批准的范围；若改成跨 Run 的任务预算，先修订方案与任务，不能直接实施当前设计。
- **验证项：** 评审人、日期、结论及每个待定项有记录；批准后才开始 T02-T09。未收到答复不是批准。
- **状态：** 已完成 2026-10-06；用户明确完成评审并授权实施，批准记录见 README.md。
- **合规检查：** 评审记录、tasks 状态已更新；此 Task 无功能代码，不涉及 CHANGELOG。

## Phase 1：执行基础设施与 Runtime

### [x] T02：GraphHarbor 受信执行预算（10-07 语义由 T13 修订）

- **状态：** done，2026-10-06；正式源码实现与真实 PG/Redis 回归完成，保留原有 cron 工作。包发布属于 T10。

- **负责人：** GraphHarbor 维护方；平台开发者配合契约核对。
- **改动内容：** claim 在现有锁/事务内生成受信预算；当前实现每 attempt 更新，Worker 等待及 drain 不越过该 attempt 截止点。重试/接管获得新 H，语义对齐由 T13 记录。
- **代码位置：** 独立依赖 `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py:RunRepository.create/claim_next/fail/requeue_expired/requeue_for_shutdown`、同包 `production_worker.py:ProductionWorker.run_once`、`database.py:run_to_dict`；`tests/test_run_budget.py`。正式 checkout 已核对，不修改 `site-packages`。
- **预期结果：** 原生 `__graphharbor_run_budget` 为服务端私有数据；图工厂前已扣除当前 attempt 初始化耗时；Worker 硬限落 timeout，下一 attempt 不受旧 deadline 拦截；当前 cancel/HITL/status 集合不变。
- **验证项：** 事务预算、并发 claim、重试/重启新预算、当前 attempt 到期、旧租约不能写终态、deadline 与停止竞态；Assistant/Thread/Run/cron 伪造值不能进入执行预算；GET/list/search/事件不泄漏私有字段。
- **依赖：** T01；正式包的隔离验证与接入在 T10。
- **Task Completion Card：** 10-06 原实现定向 `100 passed, 4 skipped` 保留为历史，不证明现行重试/接管语义。10-07 当前实现与真实 Worker 证据见 T13，正式发布仍属 T10。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（Unreleased，标明正式发布门禁）。

### [x] T03：Runtime 消费受信预算

- **状态：** done，2026-10-06；预算校验、正式图组合及隔离 HTTP 消费验证完成。

- **负责人：** Runtime 开发者。
- **改动内容：** 最小不可变 `RunBudget` 与纯解析；读取 Worker 的冻结 H/UTC/本进程时钟，核对 run/thread 身份与数值；禁止对未知正式预算静默重置开始时间。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/run_budget.py:RunBudget/read_run_budget/resolve_wrapup_reserve_seconds`、`apps/runtime-service/tests/runtime/test_run_budget.py`；入口防注入由 T02/T08 负责。
- **预期结果：** 同一次执行的主/子 Agent 共享一个预算值；monotonic 不持久化、不发往前端或外部 trace；schema/probe 可无预算构图，正式执行缺少受信预算有明确失败。
- **验证项：** 数值有限、bool/NaN/负数/版本错误拒绝、run/thread 错配拒绝、G=0 与 G>=H、并发 Run 隔离、恢复不读取旧 checkpoint 时钟、schema/probe 零外部调用。
- **依赖：** T02 契约确定。可先用显式受信样例做确定性测试，不能据此替代真实 Worker 验证。
- **Task Completion Card：** 不可变值、版本/有限数值/身份/UTC/窗口校验、schema 可无预算、正式执行缺预算失败已验证；HTTP 工厂实际读取 post42 Worker 的冻结预算。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T04：通用软收尾 middleware

- **状态：** done，2026-10-06；边界、结构化 prompt 保留、去重、真实 create_agent 与 HTTP 收尾场景通过。

- **负责人：** Runtime 开发者。
- **改动内容：** 在模型调用边界比较 soft deadline，使用 `request.override(system_message=...)` 追加短通用指令；保留原结构并去重，不写运行终态或业务 completion。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/timeout_wrapup.py:TimeoutWrapupMiddleware/TIMEOUT_WRAPUP_INSTRUCTION`、`middlewares/__init__.py`、`apps/runtime-service/tests/middlewares/test_timeout_wrapup.py`。
- **预期结果：** 窗口前无提示、窗口内后续模型请求有提示；说明已完成/未完成及已核实产物；无 PR/渠道/仓库身份属性，不免审批、不自动补发总结 Run。
- **验证项：** 边界前/恰好边界/之后，None/字符串/结构化 SystemMessage，cache_control 与其他块保留，原请求不变、重复调用不叠加；没有下一模型调用时不宣称总结已生成。
- **依赖：** T03。
- **Task Completion Card：** 边界前/恰好/之后及 None/字符串/多模态块覆盖，原消息与缓存属性保留；HTTP wrapup 成功，G=0 不注入。没有后续模型调用的硬超时不承诺总结。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T05：区分单次模型超时与整体 timeout

- **状态：** done，2026-10-06；本 scope/provider/取消和最终 error/timeout 区分已实现。10-07 Worker 不因模型超时重跑的修订由 T13 验证。

- **负责人：** Runtime 开发者。
- **改动内容：** 增加 `ModelCallTimeoutError(TimeoutError)`，仅在本 scope expired 时转换；保留供应商 TimeoutError、外部 CancelledError 和图内显式 retry/fallback。Worker 对齐官方，将此类用户错误落 error。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/model_call_timeout.py:ModelCallTimeoutMiddleware.awrap_model_call`、`apps/runtime-service/tests/middlewares/test_timeout_wrapup.py:test_model_timeout_source_and_cancellation_are_preserved`；复用 `tests/middlewares/test_runtime_middleware.py` 和 `tests/services/reference_agent/test_middleware_order.py` 基线。
- **预期结果：** Worker 的 `RunTimedOut` 才落整体 timeout；未被图内策略恢复的模型/provider 超时落 error，不重跑整图。数据库瞬时故障仍有界重试。本期不新增 fallback 框架。
- **验证项：** 本 scope 超时、provider 主动抛 TimeoutError、外部取消、M>H 的 Worker timeout、M<H 的单 attempt error；已有显式 fallback/retry 不吞取消且仍消费本 attempt 预算。
- **依赖：** T01；可与 T03-T04 按同一获批范围实施。
- **Task Completion Card：** `ModelCallTimeoutError` 只标识自身 scope，provider 原异常和外部取消不改写；现行 HTTP 单次模型 scope 超时落 error 由 T13 复验，原两次整图执行证据已被取代。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T06：四个正式图与子 Agent 显式装配

- **状态：** done，2026-10-06；四图、主/子共享、workflow 重建与 schema 组合验证完成。
- **负责人：** Runtime 开发者。
- **改动内容：** 各组合根只解析一次预算；DearFlow/Showcase 的主/子 middleware 共享；workflow 内部重建沿用外层预算；保持授权、工具裁剪、消息队列、次数限制与官方 Deep Agents 组合方式。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent/middleware`、`services/demo/showcase_demo/agent.py:get_agent/middleware`、`services/reference_agent/agent.py:get_agent`、`services/demo/workflow_demo/agent.py:get_agent/model_agent_for`；对应 `tests/services/{dearflow_agent,showcase_demo,reference_agent,workflow_demo}/`。
- **预期结果：** 工厂初始化计入 H；模型重试再次进入收尾检查；并行子 Agent 和内部模型 Agent 不新起计时器；下一 Run 或审批 resume 采用新 Worker 预算。
- **验证项：** 不只断言 middleware 类名顺序，还运行真实 `create_agent/create_deep_agent` + fake model，捕获实际 prompt；主子共享、并行隔离、workflow 重建、审批恢复、下一回合无旧预算、schema 查询不老化时钟。
- **依赖：** T03-T05。
- **Task Completion Card：** 四个组合根显式装配；真实 fake-model 图执行、子 Agent、workflow 和 schema 定向测试通过；图公开绑定配置移除私有预算，HTTP HITL resume/下一 Run 接受新预算。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T07：配置预检与环境传递

- **状态：** done，2026-10-06；预检/模板/环境传递测试和候选 wheel 冷环境启动通过；正式依赖锁定属于 T10。

- **负责人：** Runtime/部署配置维护者。
- **改动内容：** H 复用已有变量，新增 G 默认 120/0 关闭；预检 H/G 有限数值及 G<H；核对 API/Worker 和 Docker/根级 stack 的环境传递，不改变未获批现役值。
- **代码位置：** `apps/runtime-service/scripts/validate_runtime_config.py:validate`、`tests/runtime/test_runtime_config_validation.py`、`.env.example`、`deploy/.env.runtime-service*.example`、`deploy/docker-compose.runtime-service*.yml`；仓库根 `deploy/docker-compose.stack*.yml`；版本锁定在 T10。
- **预期结果：** 1800/300 秒模板不会搭配 2700 秒提醒；当前 attempt H 参与 Runtime 校验；配置变化不改变已运行 attempt，下一次领取采用新 Worker 的 H。
- **验证项：** 空值默认、非法字符串/负数/NaN/Infinity/bool、G=0、G=H、不同模板及冷启动；仅解析公开模板或隔离配置，不打印凭据。
- **依赖：** T03-T04。
- **Task Completion Card：** H/G 非法数值、默认、0 关闭及 G<H 已验证，根 stack API/Worker 补同一变量；未改现役 H，也未引入第二个同义总超时变量。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## Phase 2：平台边界与取消验证

### [x] T08：Platform API 参数保护与既有契约回归

- **状态：** done，2026-10-06；递归注入拒绝/脱敏及原生终态契约回归完成，隔离 HTTP 拒绝验证通过。
- **负责人：** Platform API 开发者。
- **改动内容：** 逐入口拒绝客户端内部预算/系统 prompt 配置，确保恢复不能覆盖；必要时补脱敏；透传原生 Run status/reason 及安全错误，不新建调度器或镜像运行表。
- **代码位置：** `apps/platform-api/src/platform_api/core/runtime_contract.py:_reject_run_budget/normalize_runtime_contract/normalize_runtime_payload/normalize_protocol_v2_command`、`adapters/langgraph/sdk_client.py:redact_runtime_private_fields`、`apps/platform-api/tests/test_run_timeout_contract.py`；复用既有生命周期/HTTP 脱敏，未机械修改网关业务层。
- **预期结果：** 标准 Run 与 Protocol、Assistant/Thread 配置、resume、cron 入口保护一致；SDK completed 标签不覆盖 timeout；新私有数据无公开泄漏；无新增 JWT claim 或 SSE 事件。
- **验证项：** 私有字段注入矩阵、HTTP/Protocol 安全错误格式、GET/list/history/SSE 的私有字段过滤、权限不变、同一幂等键只创建一个 Run、连接重试不重建执行。
- **依赖：** T02 契约、T05 错误语义；现有白名单已满足的地方仅补有价值的回归，不机械改代码。
- **Task Completion Card：** API 全量 `321 passed, 23 skipped, 606 subtests passed`；GET/list/history/SSE 私有字段隔离、SDK completed 不覆盖 timeout、真实相同幂等键复用 Run、HTTP 私有预算返回 400 通过。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] T09：取消传播、工具清理和完整 checkpoint

- **状态：** done，2026-10-06；async 模型/主子 Agent/Docker 取消回归与 local shell 进程组清理通过，HTTP 唯一终态、租约释放和最后完整 checkpoint/已提交文件回查通过。
- **负责人：** Runtime 开发者，GraphHarbor 维护方配合。
- **改动内容：** 先验证已有取消链；仅对实测残留/吞取消处修复。覆盖主/子 Agent、workspace Docker/local 执行、慢模型与耗尽初始化；外部未核实操作保留 unknown。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:DearWorkspaceBackend.aexecute`、`apps/runtime-service/tests/services/dearflow_agent/test_execution.py/test_subagents.py`；复用 `workspace/execution.py` 的 Docker 清理；完整 HTTP 场景在 `scripts/verify_run_timeout_budget.py`。
- **预期结果：** 受支持异步路径在约定容差内取消/清理，已提交消息、文件和完整 checkpoint 可回查；超时不声称全量保存或远端执行已被撤销。
- **验证项：** 模型/工具/子 Agent 正在运行时到 H，Docker 残留与租约/heartbeat 检查，取消/timeout 竞态唯一终态，最后完整 checkpoint 可恢复；忽略取消/阻塞路径必须暴露为门禁失败。
- **依赖：** T02、T06。
- **Task Completion Card：** local shell 从同步线程改为异步 subprocess，取消/超时 kill 进程组并等待退出；定向 `15 passed`。HTTP deadline 前后重复 cancel 均只有一个 durable 终态，SSE 中断后仍可回查消息/文件/checkpoint；远端供应商操作是否撤销不作保证。
- **合规检查：** [x] 实现；[x] Phase 验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## Phase 3：正式包、联调与前端交接

### [x] T10：依赖发布包与真实隔离链路

- **状态：** done，2026-10-07；正式post42双包已发布、四产物PyPI哈希核对一致，当前Runtime锁定/安装及独立冻结依赖环境冷安装、完整12组平台HTTP通过。
- **负责人：** GraphHarbor 维护方 + 平台开发者。
- **改动内容：** 正式源码测试/构建发布包；在隔离环境冷安装并验证 API/Worker 版本一致，再更新 `apps/runtime-service/pyproject.toml` 与 `uv.lock`。使用隔离 PG/Redis/工作区与独立端口，不接入现役数据。
- **代码位置：** GraphHarbor正式测试/发布入口；平台 `scripts/verify_run_timeout_budget.py`、`apps/runtime-service/tests/acceptance_app/run_budget_probe.py`、`apps/runtime-service/pyproject.toml/uv.lock`。
- **预期结果：** 冷安装包可传递受信预算；post41 安装源码和 fake model 单测不被冒充为增强能力验收。
- **验证项：** API -> Worker -> graph -> checkpoint -> timeout -> API 回查；重启、重试、SIGTERM drain、到期接管、审批新 Run、三线程并行、模型错误区别，见 verification.md。
- **依赖：** T02-T09；正式源码/发布条件缺失时记录具体缺项，继续完成其他可验证部分，不能把整体实现标 done。
- **已完成：** 复用取消专项已发布的post42四产物，没有重复上传。仅升级GraphHarbor两个包及锁文件产物信息，其余依赖版本不变；`uv sync --frozen`、141项依赖检查、新隔离环境142项依赖检查通过。发布包HTTP证据见verification.md新Phase。
- **Task Completion Card：** 四产物PyPI哈希等于正式发布清单；Runtime/Worker均post42，LangGraph1.2.11/SDK0.4.3未漂移。新Runtime不得搭配post41，回退必须同时恢复旧Runtime源码。
- **合规检查：** [x] 实现；[x] Phase验证；[x] tasks；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG；未提交/推送或部署现役。

### [x] T11：前端超时治理、停止确认与终态门禁实装

- **状态：** done；前端源码与全套单测/类型/构建均已实装并全绿；F01-F10 规范对齐。
- **负责人：** 老王（前端实装与治理）。
- **改动内容：**
  - `session.service.ts`：新增 `cancelAndWait` 发送 POST JSON body `{"wait": true, "action": "interrupt"}`，保留原 `cancel`。
  - `useChatSession.ts`：导出单一事实源 `SessionTurnState` 与 `SessionStopState`；`stop()` 调用 `cancelAndWait`；`verifyStop()` 查状态优先双通道容错防死锁；`resumeInterruptedRun` 隔离 `cancel_requested`；`send()` 与 `queueMessage()` 增加停止阻断守护。
  - `ChatAgentStatusBar.vue`：解除 `v-if="isInterrupted || error"` 限制，支持 `timeout` 黄色警示胶囊、`stopping` 转圈、`stop_unconfirmed` 核实按钮、`interrupted` 审批；适配 390px 移动端。
  - `ChatComposer.vue`：停止中与待确认期间 `canSubmitFreshOrQueue` 顶层一票否决，全量封锁发送/排队/Enter 提交。
  - `ChatSession.vue`：统一下发 `turnState`，浮动停止栏与状态条对接 `verifyStop`。
  - `useFollowUpSuggestions.ts`：增加 `turnState` 与 `runStatus` 门禁，消除时序误杀并严禁非 success 触发推荐。
- **代码位置：**
  - `apps/platform-web/src/services/threads/session.service.ts` 及 spec
  - `apps/platform-web/src/modules/chat/composables/useChatSession.ts` 及 spec
  - `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue` 及 spec
  - `apps/platform-web/src/modules/chat/components/ChatComposer.vue` 及 spec
  - `apps/platform-web/src/modules/chat/components/ChatSession.vue`
  - `apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts` 及 spec
- **Task Completion Card：**
  - 单测：10 个 spec 文件，108 项测试全部通过（108 passed, 0 failed）。
  - 类型：`rtk pnpm typecheck`（vue-tsc）零错误通过。
  - 代码风格：`rtk pnpm lint` 零错误通过。
  - 生产构建：`rtk pnpm build` 成功打包通过。
  - 实施文档：已写入 `implementation/04-frontend-run-timeout-governance.md`。
- **合规检查：** [x] 实现；[x] 单测/类型/构建验证；[x] tasks；[x] 未私自提交或推送。

## Phase 4：Final 验证与治理收口

### [x] T12：完整范围验收与回退验证

- **状态：** done，2026-10-08；用户已在浏览器端端到端完成全链路验收（含前端超时警示胶囊展示、停止双通道确认防死锁、排队提交未决死锁根除与切换自愈）；服务已安全停止；R01-R04匹配版本回退、文档及静态检查全绿。
- **负责人：** 后端/Runtime 开发者与前端共同交付，用户人工验收通过。
- **改动内容：** 全部实施 Task 完成后执行 Final；验证 G=0 与包回退/drain；更新项目 README、FEATURES、CONTEXT、用户可感知 CHANGELOG 及受影响生效标准。实施记录按实际改动写入 `implementation/`。
- **代码位置：** 本项目 `verification.md` 的 Final 区域；Runtime 开发标准和平台 `runtime-gateway-interface-standard.md`；涉及已有跨服务标准时同步其确有改动的条目。
- **预期结果：** 所有获批范围有真实证据才标 done；没有整体相关草案时不新造标准或替其他 SSE/JWT 项目毕业。
- **验证项：** 单元、集成、端到端、安全/取消/恢复/回退矩阵无缺项；证据包含版本、配置、run/thread/request_id、最终状态、事件及资源清理结果；性能只记录新增开销，无擅设生产 SLO。
- **依赖：** T01-T11。
- **已完成门禁：**
  - 正式包 12 组 HTTP、G=0、匹配源码/双包回退和历史/checkpoint/排队/产物保留；
  - 前端全套状态机、单测（108/108）、vue-tsc（0 errors）、lint 与 production build 打包全绿；
  - 用户真实浏览器交互验收（http://127.0.0.1:3000）端到端通过；
  - 本地服务已安全停止（端口 3000, 2142, 8123 全部释放）。
- **Task Completion Card：**
  - T01-T13、T11、T12 全量通过；
  - 交付文件与改动符合 KISS、YAGNI 与 Karpathy 准则，无未决代码遗留。

## 进度与验收

| 范围 | 当前状态 | 完成判据 |
| --- | --- | --- |
| 本轮规划 P01-P03 | 已完成 | 三项文档化交付与基线证据保留 |
| 人工评审 T01 | done | 用户明确批准，README 有记录 |
| 执行基础设施/Runtime T02-T07 | done；Worker 语义由 T13 修订 | 原实现完成；现行按 attempt 验收单独记录 |
| 官方 Worker 对齐 T13 | done | 官方/PG/checkpoint/正式包12组HTTP及真实新PID接管通过 |
| 平台/取消 T08-T09 | done | 注入/脱敏、错误语义、取消清理与回查通过 |
| 正式包 T10 | done | 双包正式发布、PyPI哈希、锁定/冷安装/依赖检查/12组HTTP通过 |
| 前端超时治理 T11 | done | 前端源码、单测108/108全绿、vue-tsc零错误、lint通过、build成功打包 |
| 完整实现 T12 | done | 全链路与端到端用户验收通过，服务安全停止，文档收敛完成 |

本期全部任务均已达到 done。已准备好向主工作区分支安全合并。
