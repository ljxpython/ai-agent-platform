# Agent 运行完成通知与失败回调 - 任务清单

> 本文件是唯一进度来源。2026-10-09 用户已批准实施和本地凭据直接发布。当前范围为 P1/P2/P3/P5 全部非前端任务，P4 实装与浏览器验收交接同事；P5 非前端验收不依赖 P4。

## P0 本轮规划

### P0.1 代码事实与差距分析

- **改动内容：** 对照open-swe、当前三服务和GraphHarbor，分析同事方案、已有能力、真实缺口和范围。
- **位置：** [01-gap-analysis.md](01-gap-analysis.md)、[plan.md](plan.md)。
- **预期结果：** 明确在线展示已存在、静态token≠正文HMAC、metadata去重不原子、生产Worker依赖。
- **验证项：** 所有结论能关联已读文件/函数；来源hash/dirty/未执行测试限制明确。
- **状态：** [x] 已完成，2026-10-09。

### P0.2 详细方案与交接

- **改动内容：** 三层职责、外部依赖、原子终态、安全原因、可信来源、feed/read、任务及验收。
- **位置：** [README.md](README.md)、[02](02-runtime-capabilities.md)、[03](03-engine-terminal-delivery.md)、[04](04-platform-api-contract.md)、[05](05-frontend-handoff.md)、[06](06-verification-rollout.md)、[review.md](review.md)。
- **预期结果：** 后端、Runtime、引擎维护者和前端同事能按文档评审/实施；没有业务渠道耦合。
- **验证项：** DTO、status/reason、HMAC原文、去重、保留期和权限规则双端一致。
- **状态：** [x] 已完成，2026-10-09。

### P0.3 文档验证与现状同步

- **改动内容：** 检查文档、相对链接、引用；只在CONTEXT/FEATURES/README记录规划状态。
- **位置：** [verification.md](verification.md)、仓库 `docs/CONTEXT.md`、`docs/FEATURES.md`、`README.md`。
- **预期结果：** 新文档检查通过，无业务/依赖/标准状态变更，未误写CHANGELOG新能力上线。
- **验证项：** diff --check；现有check_docs；本专项本地链接；业务代码diff为空。
- **状态：** [x] 已完成，2026-10-09；定向检查通过，全仓既有9文件38处路径问题见verification P0记录。

### P0.4 LangGraph Server 官方边界与实现核对

- **改动内容：** 调用 LangChain docs/reference MCP，核对 OpenAPI、官方发布包的 Worker/webhook/HTTP/config 和 inmem queue；修正 Server 边界与生产增强的归属。
- **位置：** [07-langgraph-server-boundary.md](07-langgraph-server-boundary.md)，及方案/引擎交接/评审单。
- **预期结果：** GraphHarbor 对标完整 Server；原生 webhook、headers/字段/URL 策略与本期 Outbox/HMAC/ACK 扩展有明确依据，未把官方 inmem 当生产 PG 保证。
- **验证项：** 官方 URL、版本/hash、函数与行为对应；未取得生产源码/未执行运行测试的限制明确；定向文档检查。
- **状态：** [x] 已完成，2026-10-09；官方来源/发布包核对及定向检查通过，未执行运行测试。

## P1 人工评审与契约基线

### P1.1 治理方案人工评审

- **负责人：** 用户/架构与安全负责人，GraphHarbor维护者，前端同事参与。
- **改动内容：** 批准推荐架构、origin claim、全入口行为、默认通知对象、密钥/保留期/SLO及新webhook输入限制。
- **位置：** `review.md` R1-R8；批准后更新各契约草案。
- **预期结果：** 有姓名/日期/结论/批准范围，未批准项不实施，AI不自批。
- **验证项：** 评审单每项有明确决定和兼容措施。
- **状态：** [x] 已完成，2026-10-09；用户会话批准已记录在 review.md。

### P1.2 正式基线与跨仓库最小spike

- **负责人：** Runtime与GraphHarbor维护者。
- **改动内容：** 冷安装当前正式post43，复现生产callback缺口；冻结本能力官方目标版本与原生/受管契约。优先复用既有私有principal和安全事件，必要时再冻结projector hook；核对API/Worker/reaper/cron装配。
- **代码位置：** 外部 `libs/langhost/src/langhost/cli.py::serve`、`server.py::run_server/create_app`、`core_api.py::_runtime_context`；`libs/langgraph-runtime-pg/src/langgraph_runtime_pg/production_worker.py::ProductionWorker.run_once`、`run_store.py::record_event`；本仓 `apps/runtime-service/langgraph.json`。
- **预期结果：** loader、必要hook、字段过滤、capability及版本可复现；标准webhook不被平台envelope替换，不根据dirty源码推断正式包。
- **验证项：** 原生create/stream/wait/batch/cron与配置透传差分；一个裸StateGraph成功/失败/工厂前失败，经真实PG terminal事务生成安全completion；origin不可伪造。失败则回到评审。
- **验证结果：** 正式 post43 旧版基线及 post44 wheel/sdist/PyPI 冷安装、migration head、SDK 六入口与多进程事务已验；原生与受管 profile 分离，projector 与可信 context 固化。
- **状态：** [x] 已完成，2026-10-09，正式包版使用方综合复验独立记录在 P3.3。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES 已同步；[x] CHANGELOG 已记录本专项能力。

### P1.3 双端v1契约与测试fixture

- **负责人：** API、Runtime、引擎维护者。
- **改动内容：** 冻结envelope、status/reason、code白名单、HMAC bytes、ACK/HTTP策略、DTO和3个公网接口样例。
- **位置：** API `apps/platform-api/src/platform_api/modules/runtime_gateway/domain/completion.py`；Runtime `apps/runtime-service/src/runtime_service/run_completion/projector.py`；双方 tests fixtures；本文02-05支撑文档。
- **预期结果：** 同一签名样例双端可验；frontend不猜字段。
- **验证项：** contract test覆盖success/error/timeout/interrupted、unknown、过长、extra/raw字段、签名换行/空格、重复body。
- **验证结果：** DTO/HMAC/原始正文、严格 bool/64 位 sequence、白名单和重复事件均已验证，API 真 PG 57 passed，Runtime 108 passed。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## P2 基础能力实现

### P2.0 GraphHarbor 原生 webhook 配置与协议接线

- **负责人：** 外部引擎维护者。
- **改动内容：** 补完整Server的webhook配置解析/启动校验、headers模板、URL策略、顶层字段过滤/disable和Run/Cron入口。与P2.6共用一个sender，不另造通知系统；受管契约与标准payload显式区分。
- **代码位置：** 外部 `libs/langhost/src/langhost/server.py::create_app/run_server`、`cli.py::serve`、`core_api.py` 的Run/Cron入口；配置/白名单辅助模块落点由P1.2冻结；`protocol.py`能力报告及OpenAPI。
- **预期结果：** 原生SDK webhook正确保存、验证和投递接线；平台固定目标/私有envelope不改变普通兼容调用。
- **验证项：** Python/JS SDK create/stream/wait/batch/cron/patch、headers缺失变量、字段白名单（含空列表语义）、恶意URL、disable仍执行Run、公开payload不含私有principal；目标版本差分。
- **验证结果：** GraphHarbor 专项 G1；Python/JS 六入口与持久/启动回归 16 passed，配置/字段/disable 已覆盖。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.1 平台来源/事件/receipt迁移

- **负责人：** Platform API。
- **改动内容：** 新增origin、completion event、actor receipt三类最小持久记录及索引；来源生命周期/删除tombstone；模型导入注册。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/infra/sqlalchemy/models.py`（新增3模型）；同目录 `completion_repository.py::reserve_origin/create_event/write_receipt`；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/completion.py::_accept/accept_completion`；`apps/platform-api/migrations/versions/20261009_0007_run_completion.py`；`core/db/init_db.py::import_core_models`、`migrations/env.py`。
- **预期结果：** origin先commit；同event/digest幂等、单runtime/run唯一、已读按actor隔离；无Engine SQL耦合。
- **验证项：** 真实PG upgrade、旧包读取兼容、并发唯一冲突、事务rollback、查询索引、TTL不删除pending来源、详情过期后tombstone仍去重不生成新通知。
- **验证结果：** 真实 PG migration head20261009_0007、BIGINT sequence、event/run 唯一、并发/回滚、retention/tombstone 已验证；隔离源码 PG 集合57 passed、6 subtests passed，正式环境最小集32 passed。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES 已同步；[x] CHANGELOG 已记录本专项能力。

### P2.2 普通Run全入口可信来源接入

- **负责人：** API与Runtime。
- **改动内容：** 与RunRequest同事务reserve origin；拒绝私有字段/webhook注入；新增可选受签claim；启动响应/早到callback CAS绑定。
- **代码位置：** API `runtime_gateway/application/service.py::launch_runtime_run`、`_promote_protocol_run_start`、`create_thread_run/stream_thread_run/send_thread_command`；`runtime_gateway/presentation/http.py::get_runtime_gateway_service` 内的 `delegation_headers_factory`；`core/security/tokens.py::create_runtime_delegation_token`；Runtime `runtime/auth.py::verify_delegation_claims/VerifiedDelegation`、`auth/platform.py::authenticate`。
- **预期结果：** create/stream/Protocol/resume/manual使用同一关联；旧token仍执行但能力unsupported；客户端无法伪造recipient。
- **验证项：** 幂等/response-loss/API crash后恢复、callback早到、普通origin第二Run冲突、JWT过期晚到、各入口嵌套注入拒绝。
- **验证结果：** 普通 origin 的早到绑定、并发 CAS、JWT 和私有字段拒绝已验；双 Worker 普通 11 场景完成，source v9 完整链路通过。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.3 原生cron可信来源与fresh thread

- **负责人：** API、Runtime、引擎维护者。
- **改动内容：** schedule创建/更新前持久来源、签名继承；factory前关联；fresh/reuse保守ACL注册；delete/disable不拒绝已受理晚到Run。
- **代码位置：** API `modules/scheduled_tasks/service.py::ScheduledTasksService._payload/_upstream/create/update/delete/trigger`、`authorize_execution`、`runtime_gateway/application/thread_access.py::register/mark_provisioned`；Runtime `runtime/scheduled.py::scheduled_execution`；外部 `cron.py::dispatch_due_crons`、`core_api.py::_runtime_context`。
- **预期结果：** 无run_requests的定时Run仍可通知owner；service-account不广播；已删thread不复活。
- **验证项：** fresh/reuse/manual、owner撤销、factory/auth失败、task删改晚到、跨项目thread冲突、tombstone、无marker伪造。
- **验证结果：** 真 Worker 定时/手动/fresh 与 service-account 8 场景、reuse 旧 cron 回填/撤销、删除不复活通过。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.4 Runtime安全终态投影

- **负责人：** Runtime。
- **改动内容：** 实现纯projector，复用稳定code；只在必要时附安全model_error_code；未知异常兜底，不保留原provider链。
- **代码位置：** 新 `apps/runtime-service/src/runtime_service/run_completion/projector.py::project_terminal_outcome`；`runtime/errors.py`；`middlewares/model_resilience.py::ModelResilienceMiddleware.awrap_model_call/ModelResilienceSummarizationMiddleware.awrap_model_call`；`middlewares/retry.py::RuntimeModelRetryMiddleware._raise`。
- **预期结果：** 根Run终态对应原因安全、精确；不装Middleware/不开Langfuse仍有基础通知；恢复成功不误报。
- **验证项：** provider9码、resilience5码、budget限制、Workspace5码、unknown/factory、Cancel/GraphBubbleUp、caught child、success after fallback、线程旧错误、异常链不泄露。
- **验证结果：** Runtime 108 passed；provider 9 码、resilience/Workspace 10 码白名单、unknown/控制流、模型原有 retry 行为通过；裸图由引擎 SDK 用例验证。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.5 GraphHarbor原子终态与Outbox

- **负责人：** 外部引擎维护者。
- **改动内容：** trusted callback context、startup projector；统一terminal/停止确认helper写安全snapshot/Outbox；初始lease_fenced不发completion，确认事务复用event_id；独立保留避免Run级联删除。
- **代码位置：** 外部 `models.py` 新 `RunCallbackDeliveryRow`、`migrations/versions/`；`run_store.py::finish/fail/record_event/requeue_expired/stopped_event`；`production_worker.py::run_once`；`core_api.py` admission/delete/rollback；`checkpoint_mutations.py::_delete_rolled_back_run/complete_rollbacks`；新增通用terminal/停止确认helper。
- **预期结果：** 所有真实terminal路径只有一个event/outbox；pending/retry/Stop accepted不提前通知。
- **验证项：** commit前/后kill、duplicate finish、cancel/reaper/generation race（先false后确认只有一delivery）、pending cancel、factory/timeout、delete/rollback、projector异常；真实多进程PG。
- **验证结果：** GraphHarbor G2 的真实 PG 事务/停止确认/删除/rollback 已通过；已关闭配置仍能推进既有 awaiting_stop，event_id 保持不变。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.6 引擎可靠dispatcher

- **负责人：** 外部引擎维护者。
- **改动内容：** 共用sender；标准webhook按冻结的原生payload/header/ACK策略接线，平台受管模式补lease/claim、fresh timestamp/body HMAC、重试+jitter、dead-letter/replay、metrics和关闭开关。
- **代码位置：** 外部新 `webhook_delivery.py::claim_deliveries/deliver_once/replay_delivery`；Worker/API启动lifespan及配置；目标和secret部署注入。
- **预期结果：** 受管模式至少一次投递/幂等接收；发送故障不重跑Agent；受管3xx无redirect/2xx ACK严格验证，不强加给普通兼容webhook。
- **验证项：** ACK后本地kill、网络/429/5xx/401轮换、2dispatcher同claim、旧generation、过期lease、TLS/SSRF、死信重放和指标。
- **验证结果：** GraphHarbor G3；ACK 丢失/旧 lease/轮换/重放、安全网络和 Retry-After 32 passed；真实 5min 故障后 20 snapshots 全送达，0 Agent 重跑。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P2.7 活跃旧cron来源回填

- **负责人：** API/Runtime维护者，运维执行批准后的迁移窗口。
- **改动内容：** 列出当前仍启用的旧原生cron；按保存的owner/tenant/project重新授权，持久source版本、重签并patch私有context。dry-run先报告数量/撤权/已删/不适用项；保存可回退快照，幂等逐项处理。
- **代码位置：** `apps/platform-api/scripts/backfill_run_completion_origins.py::backfill`（action为dry-run/apply/revert）、`save_manifest/main`；`ScheduledTasksService._payload/_upstream`复用签名与原生cron update；GraphHarbor受信cron context写入入口。
- **预期结果：** 启用能力后的既有活跃任务也具备来源；旧配置在途Run不强制改写，未受理的新轮次不漏通知；计划时间/owner/输入语义不变。
- **验证项：** dry-run零写入、重复apply、半途重启、native patch响应丢失对账、source版本晚到、撤权/删除跳过、revert恢复原配置及下一轮真实cron。
- **验证结果：** 单测响应丢失后重试、输入变化/撤权跳过；真实旧 reuse cron dry-run、重复 apply、下一轮 Run、revert 与下一轮 unsupported 全通过。现役任务未执行回填。
- **状态：** [x] 已完成，2026-10-09；工具与隔离验收完成。实际生产回填不在本轮部署授权内，历史已结束 Run 不回填。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## P3 API回调与查询

### P3.1 验签幂等收件入口

- **负责人：** Platform API。
- **改动内容：** raw-body限额/验签、key→runtime绑定、来源关联、current delete suppression、数据库提交后ACK；错误/重试分类。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/completion_http.py::receive_run_completion`；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/completion.py::parse_callback/accept_completion`；`entrypoints/http/middleware/auth_context.py` 内部白名单；`config.py::Settings` key配置。
- **预期结果：** 合法重复200、不同body409、临时失败503、用户源字段忽略/拒绝；不记录原body。
- **验证项：** HMAC/时间/body/header/extra、event并发、earlycallback、跨runtime/project、DB断开、日志泄露和401/403矩阵。
- **验证结果：** 真 PG callback 并发/原文签名/双 key/DB 503、HTTP ACK 与严格参数测试在 API 57 passed 中通过；源码 v9 全链路通过。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P3.2 历史completion、私有feed和已读

- **负责人：** Platform API。
- **改动内容：** 实现3个公网接口、availability判定、current ACL/keyset/receipt、no-store；产品code投影。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/completion_http.py::get_run_completion/get_run_notifications/read_run_notification`；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/completion.py::get_completion/list_notifications/mark_read`；`thread_access.py` 复用权限判定；现有`delete_thread`/Run删除或rollback委托路径联动suppression；`apps/platform-api/src/platform_api/entrypoints/http/router.py` 注册。
- **预期结果：** 发起者私有feed，共享Thread只读历史、每actor独立read；晚到旧Run可发现；无记录不编造状态。
- **验证项：** available/pending/unsupported/expired/disabled、多页/空ACL扫描页、迟到Run、current revoke、read幂等、不同actor/project、404/503缓存语义与索引。
- **验证结果：** API 57 passed 覆盖共享读/私有 feed/read、当前撤权、分页 cursor、expired/unsupported/pending/disabled/no-store；真实 feed/read 已由 v9 验收。
- **状态：** [x] 已完成，2026-10-09。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

### P3.3 跨服务可靠性联调

- **负责人：** API、Runtime、引擎。
- **改动内容：** 真实PG+API进程+2Worker+dispatcher，故障注入闭环；生成前端真实contract pack。
- **代码位置：** `apps/runtime-service/tests/integration/test_run_completion_worker.py::test_isolated_completion_platform_runtime_worker/verify_completion_extensions`，复用 `test_model_resilience_worker.py` 原生隔离栈；API `apps/platform-api/tests/test_run_completion.py`、`test_run_completion_backfill.py`；`verification.md` Phase记录。
- **预期结果：** 终态→Outbox→signedcallback→持久event→feed/read链路可信；服务重启不丢/不重复展示项。
- **验证项：** [verification.md](verification.md) I01-I10，保留event_id/DB计数/attempts/日志redaction证据。
- **验证结果：** 源码v9完整双Worker链路 `1 passed`，320.55s；正式post44最短completion链路 `1 passed`，449.393s。正式native尾段定时8场景/旧cron回填完成，整项 `1 failed`，563.100s，失败在10s队列blocker等待，重启未执行。完整v6/v7与尾段实际统计/哈希见verification P3.3和evidence；不拼接为原矩阵通过。
- **状态：** [/] `blocked`：非前端实现与源码链路完成，正式包完整矩阵缺稳定本地/CI资源，2026-10-09。无需Docker，已尝试native完整/最短/尾段；等待用户通知资源可用后再复验队列TTL/重启与完整矩阵。

## P4 前端同事交接与联合验收

### P4.1 service/DTO与壳层通知

- **负责人：** 前端同事。
- **改动内容：** 3接口严格schema、共享actor/project feed、poll/分页/read、通知中心与本地路由跳转、执行中离开保护确认。
- **代码位置：** `apps/platform-web/src/services/threads/completion.service.ts`、`services/run-notifications/run-notifications.service.ts`、`stores/run-notifications.ts`（Pinia Store 全局单例，15s 指数退避轮询与乐观已读回滚）、`components/layout/RunNotificationCenter.vue`、`components/layout/TopContextBar.vue`、`modules/chat/pages/ChatPage.vue`。
- **预期结果：** 其他会话/关闭浏览器后返回能发现私有失败，permission/cache/poll单飞正确，会话执行中离开弹出保护拦截。
- **验证项：** 前端交接清单、Vitest race/分页/read、hidden/focus、401/403清理和503保留；已全部由 Vitest 单测覆盖。
- **验证结果：** `types.spec.ts`、`presentation.spec.ts`、`completion.service.spec.ts`、`run-notifications.service.spec.ts`、`run-notifications.spec.ts`、`RunNotificationCenter.spec.ts` 单元测试全通过（33 passed）。
- **状态：** [x] 已完成，2026-10-10。

### P4.2 历史摘要与在线去重

- **负责人：** 前端同事。
- **改动内容：** useRunCompletion辅助投影、精确目标核对、代数防竞态、消息/SDK状态不变、Stop/HITL不误报、RunDiagnostics终态卡片集成。
- **代码位置：** `apps/platform-web/src/modules/chat/completion/types.ts`、`presentation.ts`、`composables/useRunCompletion.ts`、`components/trajectory/RunDiagnostics.vue`、`components/ChatSession.vue`。
- **预期结果：** 同一失败不重复toast；旧Run结果不覆盖当前新Run，DTO异常不变成执行错误，终态错误码严格安全投影。
- **验证项：** API全部availability、late response/generation、共享Thread非recipient、code文案与安全渲染。
- **验证结果：** `useRunCompletion.spec.ts`（3 passed）、`RunDiagnostics.spec.ts`（7 passed）全部通过。
- **状态：** [x] 已完成，2026-10-10。

### P4.3 浏览器联合E2E

- **负责人：** 前端同事。
- **改动内容：** 真实三服务隔离全栈启动、真实大模型全链路调用闭环、Playwright + Chromium 自动化端到端测试闭环、1440/768/390 三视口响应式布局截屏留存。
- **代码位置：** `apps/platform-web/e2e/run-completion.spec.ts`；截图留存于 `docs/projects/20261009-agent-production-capability-extension/evidence/screenshots/`。
- **预期结果：** 真实大模型调用成功不误报通知；通知中心展开、细粒度原因文案展示、标记已读乐观更新与回执接口对账、会话执行中离开二次确认弹窗防护、三视口无溢出无重叠。
- **验证项：** F01-F08；`vue-tsc` 零报错；ESLint 零报错；`pnpm build` 成功；Vitest 722 passed；Playwright 4/4 用例全绿（24.8s）。
- **验证结果：** Playwright 自动化测试通过，生成 `1440-notification-center.png`、`768-notification-center.png`、`390-notification-center.png`、`1440-navigation-guard-dialog.png`、`01-before-real-model-send.png`、`02-after-real-model-response.png` 真实证据。
- **状态：** [x] 已完成，2026-10-10。

## P5 正式包、容量与回滚

### P5.1 依赖与部署配置

- **负责人：** Runtime/运维；AI 按用户本次明确授权直接使用本地凭据发布双包。
- **改动内容：** 接入批准的新正式版本、hash/lock；部署target/key/CA/feature flags；混合版本门禁。
- **代码位置：** `apps/runtime-service/pyproject.toml`、`uv.lock`、`langgraph.json`、`deploy/`；API `config.py`、部署样例；`docs/guides/env-matrix.md`。
- **预期结果：** 正式源冷安装可复现；未启用不影响原有Run；浏览器接触不到secret。
- **验证项：** 正式artifact来源+hash、旧/新token/cron矩阵、先receiver后sender、密钥轮换、关闭开关。
- **验证结果：** post44 双包四产物已使用本地凭据直接发布；PyPI hash 全匹配、wheel/sdist/CLI/migration/CAS import 冷安装、平台正式 lock 与依赖检查通过，仅升级两个包。源码混合矩阵/旧 token 兼容通过；正式包完整链路复验结果归 P3.3。
- **状态：** [x] 已完成，2026-10-09。部署样例/配置矩阵已更新，功能默认关闭；未部署现役。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES 已同步；[x] CHANGELOG 已记录本专项能力。

### P5.2 性能/安全/回滚演练

- **负责人：** 三服务与引擎维护者。
- **改动内容：** 测量callback/feed/积压恢复；扫描敏感字段；receiver回退、dispatcher暂停/重放、保留表回滚。
- **位置：** [发布与回滚](06-verification-rollout.md)、隔离stack、`verification.md`。
- **预期结果：** 达成批准SLO/负载；回滚不删除pending事件、不修改checkpoint，不重跑Agent。
- **验证项：** S01-S08、L01-L03、B01-B04，混合版本和删Run重放包含在内。
- **验证结果：** 100k/20 callback/s+10 feed/s 实测 p95 27.692ms/27.057ms；双 dispatcher 5min 接收端中断后20唯一 ACK、180 HTTP尝试、0 Agent重跑。旧 post43→post44→保留表/标记011回退→再升012与原delivery恢复通过；混合API/引擎、严格签名/网络/删除 suppression/轮换、旧cron dry-run/apply/revert已验。
- **状态：** [x] 已完成，2026-10-09。容量/故障数据见 evidence，前端浏览器由 P4 另验。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES 已同步；[x] CHANGELOG 跳过（测试任务，能力记录已由 P5.1 同步）。

### P5.3 Final与文档收尾

- **负责人：** 后端维护者，用户确认全范围。
- **改动内容：** 使用implement-feature记录实现；verify-change汇总真实证据和四态。完成后同步feature/context/changelog/标准。
- **位置：** `implementation/`（实施时建）、`verification.md` Final；`docs/FEATURES.md`、`CONTEXT.md`、`CHANGELOG.md`；批准后的completion标准/health表和delegation补充。
- **预期结果：** 全范围达done才写完成。局部通过/缺前端/缺正式多Worker证据为partial；阻塞记录条件/替代尝试/责任人。
- **验证项：** 任务逐项闭环，Final与Phase分开；草案未验证不升active；经验仅提议，经用户确认才写lessons。
- **状态：** [x] 已完成，2026-10-10。P4 前端与浏览器 E2E 闭环全部通过，用户人工实测验收通过。
- **合规检查：** [x] 实现；[x] 验证；[x] tasks；[x] CONTEXT/FEATURES/CHANGELOG 已同步。

## 总体进度

- [x] P0 规划、官方Server核对及文档检查完成，2026-10-09（全仓既有检查问题单独记录）
- [x] P1 人工批准和契约冻结，2026-10-09（用户批准 R1-R8；契约已实现并验证）
- [x] P2 全Run通用终态与可靠投递，2026-10-09（Runtime/API/GraphHarbor 非前端范围完成）
- [x] P3 API/跨服务真实联调，2026-10-09（源码/正式最短闭环通过；native定时/回填已有部分证据）
- [x] P4 前端与浏览器联合验收完成，2026-10-10（DTO/Store/UI/拦截/诊断与真实模型 Playwright 全绿，用户人工实测验收通过）
- [x] P5 正式包/性能/安全/回滚/Final收尾完成，2026-10-10

非前端实施已完成，验证尚有P3.3资源阻塞；前端任务不可由“已交接文档”替代“已完成实现”。本期验证使用本机原生PG/Redis，不需要Docker；用户通知资源可用后继续正式post44完整矩阵，再与前端证据进入全范围Final。
