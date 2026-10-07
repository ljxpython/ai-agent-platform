# Agent 模型调用稳定性治理 - 任务拆分

## 进度与完成条件

P01~P03 规划已交付。2026-10-06 用户批准原方案；后端/Runtime 已实施并完成局部和隔离链路验证；前端继续由同事实施，未授权提交或发布。

**当前推进状态：`done`。** 后端/Runtime 与 GraphHarbor 取消修复已通过，前端 F01/F02 实施与单测（559 passed）完成；V02 真实三服务栈浏览器与故障注入端到端联合验收通过；V03 最终门禁与规范同步完成，经用户人工验收合格。

| 阶段 | 状态 | 完成条件 |
|---|---|---|
| 本轮规划 | 已完成 | 源码对照、建议评估、服务分工、代码位置、验证与前端交接齐全，基线结果可复查 |
| Phase 0 人工评审与组合验证 | 已完成 | R01~R05 已获用户批准；官方组合、流式边界和实际子图验证通过 |
| Phase 1 控制面 | 已完成 | 配置、候选授权、内部契约、快照/审批/脱敏测试通过 |
| Phase 2 Runtime | 已完成 | 分类、预算、流式、直接取消、四组合根、摘要恢复和跨协议测试通过 |
| Phase 3 后端真实链路 | 已完成 | 隔离 Worker/定时/排队/重启、16 条模型 smoke、V01-C 默认配置及 9 项实际子图已通过；Anthropic 真实 API 排除 |
| Phase 4 前端实施与联合验收 | 已完成 | F01/F02 前端代码与单测验证已完成（559 passed）；V02 真实三服务栈浏览器与故障注入联验通过，用户人工验收通过 |
| Final | 已完成 | 所有本期验收、回退及规范同步完成，状态达到 done |

## 本轮规划

### [x] P01：同步项目现状与源码证据

- **改动内容：** 阅读 CONTEXT、三服务入口/相关规范、跨服务标准与经验；核对用户提供的 open-swe 源码、实际锁定依赖和所有模型构造调用者。
- **代码位置：** 阅读位置详见 `reference-analysis.md`，未改业务代码。
- **预期结果：** 已有、未接通、真实缺失与未验证能力明确区分；建议评估有真实符号依据。
- **验证项：** 参考 Git HEAD、锁定/安装版本、中间件顺序及 Worker 分类源码交叉核对。
- **完成日期：** 2026-10-06。

### [x] P02：完成分层方案和前端交接

- **改动内容：** 创建标准项目文档，定义具体开发范围、字段/默认值、信任边界、错误/流式语义、任务、风险与回退。
- **代码位置：** 本项目 `README.md`、`reference-analysis.md`、`plan.md`、`tasks.md`、`verification.md`、`frontend-handoff.md`。
- **预期结果：** 后端、Runtime 和同事能按同一份受评审方案实现，不需要猜字段或职责。
- **验证项：** 文档路径/链接检查、git diff 检查；在 `verification.md` 记录实际结果。
- **完成日期：** 2026-10-06。

### [x] P03：建立可重复基线

- **改动内容：** 在当前 worktree 源码上运行现有 Runtime/API 的相关测试；借用主检出的既有 venv，不安装、更新依赖或启动现役服务。
- **代码位置：** `apps/runtime-service/tests/services/reference_agent/test_middleware_order.py`、`tests/runtime/test_modeling.py`、`tests/middlewares/test_runtime_middleware.py`；`apps/platform-api/tests/test_runtime_model_reference.py`、`test_byok_model_lifecycle.py`、`test_assistants_runtime_contract.py`、`test_agent_single_table.py`。
- **预期结果：** 原有能力和测试边界可信，新功能仍明确未实现。
- **验证项：** Runtime 37 passed；API 11 passed、8 subtests passed；执行命令见 `verification.md`。
- **完成日期：** 2026-10-06。

## Phase 0：评审与实现路径确认

### [x] G01：记录 Worker 取消传播决定与跨仓库任务

- **改动内容：** 记录用户确认的 Redis 即时通知、持久标记/PG 兜底、Worker 停止确认、默认 ACK 与 `wait=true` 边界；在 GraphHarbor 创建跨包方案/任务/验证清单，同步平台依赖与前端交接。
- **代码位置：** 本项目 README/plan/tasks/verification/frontend-handoff；GraphHarbor 仓库 `docs/projects/20261007-worker-cancel-propagation/`。
- **预期结果：** 两仓库采用同一验收口径；1 秒心跳不代替修复；不把默认 ACK 当停止确认。
- **验证项：** 文档路径、任务编号、范围、状态和双仓库链接/空白检查；本项不代表 GraphHarbor 实现完成。
- **完成日期：** 2026-10-07，用户明确同意设计并要求写入文档。

### [x] G00：人工评审治理方案

- **负责人：** 用户/指定评审人。
- **改动内容：** 对 `plan.md` 的 R01~R05 给出批准或调整；记录具体范围、评审人和日期。优先裁定 Delegation/BYOK 作用域差异与错误终态。
- **代码位置：** `plan.md` 评审表、本文；本任务完成前不开始策略实现。
- **预期结果：** 受管备模型、数据可用范围、默认预算、前后端契约和回退方式有人工决定。
- **验证项：** 每项都有明确决定；不由 AI 填「批准」。
- **状态：** `[x]` 已完成 2026-10-06。用户明确批准「按照原方案来推进，可以开始实施了」，R01~R05 维持原范围；前端由同事实施。
- **合规检查：** 评审来自用户明确指令；已更新 plan/README/tasks；无代码或发布操作。

### [x] R00：锁定版本的策略组合与消息边界验证

- **负责人：** Runtime 开发。
- **改动内容：** 使用现有 Fake/Bindable 模型做最小组合验证，证明 official Retry + Fallback + 局部 guard 的次数/非 transient 保护/timeout 顺序/stream callback 可行；检查实际 Deep Agents compiled graph 的根、researcher、general-purpose 和摘要。证明摘要外层原生 ContextOverflow 恢复仍有效，区分受管 invocation 与压缩重入/辅助请求的计数；确认稳定失败归一化位置，验证 Worker 对稳定业务错误与原始 timeout 的不同路径。
- **代码位置：** 新增 `apps/runtime-service/tests/middlewares/test_model_resilience.py`；扩充 `tests/services/reference_agent/test_middleware_order.py`、`tests/services/dearflow_agent/test_agent.py`、`tests/services/showcase_demo/test_agent.py`；只读核对已锁定依赖源码，不修改 site-packages。
- **预期结果：** 明确最小实现能否达成物理请求最多 N 次、不可重试错误不访问 B、partial stream 不访问 B，并列出实际自动生成的子图。
- **验证项：** 单个受管 invocation A/B/A 最多 3 次；A 永久错误 1 次；无 B 的 A/A/A；首次 A/B 无官方轮次等待、下一轮退避有 jitter；Timeout 在 fallback 内层；tool-call chunk/reasoning 被检测；implicit 子图无漏装；ContextOverflow 仍能压缩后重入且计数/预算边界有真实记录。
- **状态：** `[x]` 已完成 2026-10-06；middleware 33 passed、组合/子图 77 passed，证据见 verification.md Phase 0~2。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5~1 天。

## Phase 1：Platform API 控制面

### [x] A01：Agent 管理配置与已有 JSON 存储

- **负责人：** API 开发。
- **改动内容：** 增加严格 `model_resilience` DTO、默认关闭、GET/PATCH 清空/替换语义；内部 JSON 与公开 Context 分离，保存 context 不丢策略，关闭后删除内部保留键；按图支持集合呈现管理 schema。
- **代码位置：** `apps/platform-api/src/platform_api/modules/agents/application/contracts.py`、`domain/models.py`、`application/service.py:_assistant_item()/create_assistant()/update_assistant()/get_parameter_schema()`；复用 `infra/sqlalchemy/repository.py:update_assistant_configuration()`。
- **预期结果：** 列表/详情能读到默认或有效策略；没有新表/列；原有 Run Context 字段集合不扩展。
- **验证项：** 缺省/清空/完整对象；bool/NaN/Infinity/非整数/未知字段；老 Agent 空 JSON；普通配置与策略双向保留；内部键不可通过 context 注入；写权限和审计。
- **状态：** `[x]` 已完成 2026-10-06；test_agent_model_resilience 管理用例通过，包含于控制面定向 57 passed/24 subtests。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 1 天。

### [x] A02：候选模型授权与作用域一致性

- **负责人：** API 开发，依赖 R01 批准。
- **改动内容：** 保存/执行/兑换均校验主备；按批准决定统一 Catalog/Delegation 项目模型允许范围；允许已授权公共模型与本项目私有模型，拒绝其他项目 BYOK、disabled 或策略禁用候选。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py:build_delegation_policy()`；`modules/runtime_gateway/application/service.py:_assert_runtime_options_allowed()`；`modules/runtime_catalog/application/service.py:_authorize_model_reference()/resolve_model_connection()`；候选保存检查放在 Agent 用例中。
- **预期结果：** fallback 不扩大任何模型、actor、Thread 或图权限；JWT 名单不泄露其他项目私有候选。
- **验证项：** P1 正常主备；P1 使用 P2 私有模型拒绝；公共模型项目禁用拒绝；actor/凭据/Agent/图/Thread 撤销拒绝；服务账号路径；主备重复拒绝或运行期去重。
- **状态：** `[x]` 已完成 2026-10-06；候选保存/Delegation/兑换正反例及隔离服务账号链路通过，见 verification.md Phase 0~3。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5~1 天。

### [x] A03：幂等策略快照与签名连接 bundle

- **负责人：** API 开发。
- **改动内容：** 在首次提交固定受管策略，幂等重试复用快照；opaque ref 签名覆盖策略和备用 ID；内部兑换返回主备 bundle；旧 reference 和 disabled 策略保持当前响应；公开数据过滤不暴露 ref/连接/内部键。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:launch_runtime_run()/_attach_runtime_model_reference()`；`modules/runtime_catalog/application/model_connection.py:create_model_reference()/parse_model_reference()`；`modules/runtime_catalog/application/service.py:resolve_model_connection()`；`presentation/http.py:get_internal_runtime_model_config()`；`adapters/langgraph/sdk_client.py:redact_runtime_private_fields()`。
- **预期结果：** 只有服务端受管值进入 GraphHarbor，凭据只在内部 HTTP 与 Runtime 客户端内存；相同 submission 不漂移策略。
- **验证项：** 客户端每种配置位置注入拒绝；签名篡改备用/预算/项目拒绝；过期 ref+新鲜 Runtime HMAC；配置改动后的同 key 不漂移；metadata/state/history/public Run 脱敏。
- **状态：** `[x]` 已完成 2026-10-06；未知结果同 key、签名篡改和公开投影测试通过；隔离 queue/restart 证据通过。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 1 天。

### [x] A04：所有执行入口、定时任务与审批

- **负责人：** API + Runtime 开发。
- **改动内容：** trace 每个 Run 入口的实际调用链；交互、Protocol、排队和审批均采用受管快照；定时执行前刷新主备授权与连接；辅助 suggestions 不请求主备策略。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:create_thread_run()/stream_thread_run()/send_thread_command()/launch_runtime_run()`；`modules/scheduled_tasks/service.py:authorize_execution()`；`apps/runtime-service/src/runtime_service/runtime/scheduled.py:scheduled_execution()`。
- **预期结果：** 无入口暗中绕过策略；审批只恢复批准动作；定时实际失败不能记 success。
- **验证项：** command/native/manual/cron/resume 各一条最小链；同一 tool action 不重复；排队超过 ref TTL 后正确执行；执行前禁用 B/撤权 fail closed；suggestions 既有短预算回归。
- **状态：** `[x]` 已完成 2026-10-06；API 全量 327 passed/23 skipped/613 subtests，隔离 Worker、manual/once/cron、禁用 B 与审批组合通过；skip 不算通过。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5 天。

## Phase 2：Runtime 模型可靠性

### [x] R01：连接解析与独立模型构造

- **负责人：** Runtime 开发。
- **改动内容：** 新增不可变 policy 和 `fetch_model_bundle()`，严格校验启用策略的版本/预算/主备 ID；复用 connection HTTP/HMAC 和 provider builder；启用路径主备和 model_builder 重建均 `max_retries=0`，备用独立应用 reasoning。按批准范围另建共用主连接的辅助实例，供公开摘要 factory 和记忆提取使用，保留它们的原有设置；不新增连接兑换。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/contracts.py`、`runtime/modeling.py:fetch_model_connection()/build_model()`；`services/dearflow_agent/agent.py:get_agent()`、`services/dearflow_agent/modes.py:apply_reasoning()`。
- **预期结果：** 无备模型时只有一候选；无策略旧 ref 行为明确；探测构图无 HTTP/provider/workspace 资源；密钥不进 Graph State。
- **验证项：** bundle schema/版本错误、model ID 不匹配、未知 provider、缺凭据、same-ID 去重；每个 supported protocol；初建/重建/绑定的生成实例 retry=0，辅助实例设置与原行为一致；reasoning 不串 provider。
- **状态：** `[x]` 已完成 2026-10-06；bundle、组合根/实际子图与跨协议 9 项通过，真实候选 smoke 的证据边界另见 V01。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5 天。

### [x] R02：显式 transient 分类与 Retry-After

- **负责人：** Runtime 开发。
- **改动内容：** 在唯一策略模块实现显式 classifier 和候选 cooldown；优先永久错误/取消/GraphBubbleUp 拒绝，保留 ContextOverflow 原类型供官方摘要恢复，再识别 SDK、LangChain 和允许的 transport/status；用标准库处理 Retry-After 秒/日期。
- **代码位置：** 新增 `apps/runtime-service/src/runtime_service/middlewares/model_resilience.py`；新增 `tests/middlewares/test_model_resilience.py`。
- **预期结果：** provider 限流与 quota 不混淆，参数/权限/程序错误不访问备用。
- **验证项：** 408/429/500/502/503/504/529；quota、401/403/400/404、context-length、业务权限与未知异常；malformed/过期/未来 Retry-After；transport 可重试与本地协议错误不可重试。
- **状态：** `[x]` 已完成 2026-10-06；middleware 33 passed，包括分类与秒/日期 cooldown；隔离总预算用例通过。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5 天。

### [x] R03：官方 middleware 组合、物理预算与稳定失败

- **负责人：** Runtime 开发。
- **改动内容：** 根据 R00 结果组合官方 Retry/Fallback 与局部候选 guard；统一物理次数、指数 backoff/jitter 和单次/总预算；耗尽或已知永久 provider 错误转成稳定 Runtime 错误，取消/GraphBubbleUp 原样传播。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/model_resilience.py:ModelResilienceMiddleware`；复用 `middlewares/model_call_timeout.py:ModelCallTimeoutMiddleware`、`runtime/errors.py:RuntimeResolutionError`。
- **预期结果：** A/B/A 或 A/A/A，真正访问次数不超过配置；耗尽不返回故障 AIMessage，也不触发 Worker 整 Run infrastructure retry。
- **验证项：** 首次成功 1 次；B 成功 2 次；A 再恢复 3 次；全失败 exactly 3 次；预算在 handler/sleep/cooldown 内均有效；取消后 0 个后续请求；并行调用局部计数不串扰。
- **状态：** `[x]` 已完成 2026-10-06；33 项 middleware 与隔离耗尽/恢复/预算通过。直接取消已验，Worker 端到端取消另在 V01 保留未满足条件。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 1 天。

### [x] R04：流式提交边界与消息兼容

- **负责人：** Runtime 开发。
- **改动内容：** 在实际 model invocation 上观察内容 chunk；text/reasoning/tool-call 后失败不自动再访问候选；保持官方消息转换和工具配对，不能丢模态/历史。失败空占位以原生事件和同事消息投影回归收敛。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/model_resilience.py`；复用 `middlewares/runtime_config.py:sanitize_tool_call_messages()/repair_model_tool_calls()`；`tests/middlewares/test_model_resilience.py`、`tests/durable/test_agent_server_durable.py` 或新增同目录专项测试。
- **预期结果：** SDK 最终消息、正文、reasoning 与工具身份一致；没有混合 A/B 回答或重复工具副作用。
- **验证项：** 首块前 503；空 metadata；reasoning-only；正文后 timeout；部分 tool args 后断连；跨协议 cache/thinking/history；图片不支持拒绝；取消/失败 callback 清理。
- **状态：** `[x]` 已完成 2026-10-06；middleware 流式和跨协议 9 项通过，隔离 partial/reasoning/tool/empty 计数与消息身份通过。前端投影仍归 F02/V02。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5~1 天。

### [x] R05：四个组合根与全部实际子图装配

- **负责人：** Runtime 开发。
- **改动内容：** Reference、Showcase、DearFlow、Workflow 采用同一 policy；保证 RuntimeConfig 位于策略外层、timeout 位于内层。DearFlow researcher 已名为 general-purpose，只在现有只读 child 装配策略，不新增子图或工具。公开摘要 factory 使用辅助实例同名替换根/子图默认摘要，保留 offload/阈值与压缩恢复；记忆提取改用辅助实例，skills 不新增推理包装。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py:get_agent()`；`services/demo/showcase_demo/agent.py:get_agent()`、`subagents.py:build_subagents()`；`services/dearflow_agent/agent.py:get_agent()/middleware()`；`services/demo/workflow_demo/agent.py:model_agent_for()`；现有 `MemoryContextMiddleware` 注入位置；显式维护 `middlewares/__init__.py:__all__`。
- **预期结果：** 公开可达主/子生成路径受同一 invocation 策略；辅助摘要/记忆的已批准边界与设置清晰，不宣称所有 model 节点总请求数均 <=N；Probe 不联网，未支持图不能静默开启。
- **验证项：** 四图逐个；researcher/Showcase 子图/实际 general-purpose；model_builder 不重置备用；工具只减不增；schema probe 无凭据；摘要 ContextOverflow 恢复与辅助 retry 设置；skills 无模型调用，suggestions/标题仍独立。
- **状态：** `[x]` 已完成 2026-10-06；组合/子图 77 passed，ContextOverflow 压缩成功/最终失败与只读子图权限通过。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5~1 天。

### [x] R06：脱敏观测与失败出口

- **负责人：** Runtime + API 开发。
- **改动内容：** 将 attempted/effective model、次数、分类/耗时、fallback 结果和 trace/run 关联加入现有观测；保证失败型异常及 Worker 终态只含稳定信息，公开错误走既有 SDK/HTTP 出口。前端收到的具体 error 投影以真实数据定稿。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/langfuse.py:with_langfuse_tracing()` 及 callbacks；`middlewares/model_resilience.py`；`apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` 与受影响错误 catalog/规范。
- **预期结果：** 管理者能区分 A 失败/B 成功与全失败，用户看到可读失败；无 key、endpoint、provider body 或凭据泄漏，无额外 metrics 高基数字段。
- **验证项：** error/lifecycle/state/HTTP/trace/log 五出口检查；raw SDK exception/context chain 清洗；计数/实际模型一致；观测出口故障不改变 Run 结果。
- **状态：** `[x]` 已完成 2026-10-06；Langfuse/SDK 脱敏单测及隔离 Run/SSE/state/稳定失败投影通过；成功消息实际模型摘要与物理请求数一致。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。
- **预计：** 0.5 天。

## Phase 3：后端链路验证

### [x] V01：隔离故障注入、真实模型对与 Worker

- **负责人：** API + Runtime 开发。
- **改动内容：** 隔离 PG/Redis 和受控 provider 复现 `verification.md` I/E 场景；覆盖全失败/总预算/取消/恢复、服务账号/定时任务、部分输出和跨项目。真实 provider 只做可控 smoke，不对生产制造 outage。
- **代码位置：** 复用 `apps/runtime-service/tests/durable/`、`tests/integration/`、`apps/platform-api/tests/integration/`；参考 `apps/runtime-service/scripts/r6_worker_fault_injection.py`，只在确有缺口时新增最小注入用例。
- **预期结果：** provider 次数、tool 次数、Run 终态和定时历史全部与策略一致。
- **验证项：** 保留版本、匿名配置、Run ID、受控请求计数、结果和回放证据；真实模型文本/工具/实际模态配对通过。
- **预计：** 1~2 天。
- **当前证据与限制：** Worker 故障、排队过期ref、重启、审批/定时通过；官方DeepSeek↔miaomiao DeepSeek/Qwen 文本/工具/图片、↔Minimax文本/工具共16项通过，Anthropic真实API排除。smoke跨事件循环HTTP pool问题修复后复验通过。旧默认取消失败7.925秒及1秒heartbeat对照0.705秒保持为基线；post42 V01-C默认与9项实际子图已通过，后端Phase条件满足，前端/完整回退/Final另验。
- **状态：** `[x]` 已完成 2026-10-07；原失败未改为通过，修复后证据独立留存。
- **合规检查：** [x] 隔离链路与smoke完成；[x] 对应Phase已执行；[x] tasks更新；[x] CONTEXT/FEATURES/CHANGELOG同步。

### [x] V01-C：GraphHarbor 取消修复后的默认配置与停止确认复验

- **负责人：** GraphHarbor 维护者 + Platform API/Runtime 开发。
- **改动内容：** 依赖 GraphHarbor `20261007-worker-cancel-propagation` 完成通用控制修复后，在候选同版本双包的独立栈核对默认 heartbeat、`wait`/`action` 透传和实际模型/子图取消。
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/runs_sdk_adapter.py:LangGraphRunsSdkAdapter.cancel()`、`runtime_gateway_upstream.py`；`apps/runtime-service/tests/integration/test_model_resilience_worker.py`、durable tests；GraphHarbor 实现进度仅看其 tasks.md。
- **预期结果：** 默认配置通过控制队列即时唤醒；`wait=true` 返回时执行/子图已退出，后续候选请求为零。`wait=false` 仅验证受理和传播时延，提前 interrupted、本地 abort、lease 到期都不作为停止证据。
- **验证项：** factory、handler、backoff、cooldown、stream、实际 researcher/general-purpose；受理/收到/退出/释放四时间点、候选调用数、终态事件数和任务/连接回收；SDK/HTTP 正反例及默认配置复测。复用受控 provider，不要求 Anthropic 凭据。
- **状态：** `[x]` 已完成 2026-10-07；候选 post42 默认 heartbeat 的 HTTP adapter 取消仅 primary，ACK→lease 释放 0.123 秒；实际 DearFlow general-purpose、Showcase research/general-purpose × provider/backoff/cooldown 9 passed，wait 阻塞至子图清理完成，确认后候选次数不增长。旧失败证据保留为优化前基线。
- **合规检查：** [x] 用例/实现完成；[x] 默认与实际子图验证执行；[x] tasks 更新；[x] CONTEXT/FEATURES/CHANGELOG 同步。

## Phase 4：前端交接与联合验收

### [x] H01：交付前端实现版接口与验收文档

- **负责人：** 本轮后端/Runtime 开发。
- **改动内容：** 用实际 Pydantic section、v3 Worker lifecycle 和成功 state 替换草案；保留完整配置、权限/候选、错误/partial、取消、定时及联合测试范围。2026-10-07 补齐源码差距、F01/F02 开发顺序、平台取消 200/502/504 映射、12 项停止验收、测试落点与联调分工；按用户确认写入两仓库经验。
- **代码位置：** `frontend-handoff.md`、`docs/lessons/cross-service.md`/index；GraphHarbor 仓库 `docs/lessons/runtime-persistence.md`/index；不修改 `apps/platform-web`。
- **预期结果：** 同事可直接按字段/错误投影接入，不猜测 error.code 或公开 Context 扩展。
- **验证项：** 与当前 API schema、evidence/worker.json、scheduled.json、成功 state 及支持图集合核对；新增入口与实际 SDK adapter/网关映射、文档 checker/链接/空白检查见 verification.md 专属交接 Phase。
- **完成日期：** 2026-10-06；2026-10-07 交接补充与经验落笔。交付不替代 F01/F02/V02 验收。
- **合规检查：** [x] 实际字段/事件核对完成；[x] 本专项文档检查通过；[x] tasks 状态更新；[x] CONTEXT/FEATURES 同步；CHANGELOG 随后端能力统一记录。

### [x] F01：接入 Agent 配置与权限状态

- **负责人：** 前端开发。
- **改动内容：** 按 `frontend-handoff.md` 扩展管理类型/service/schema 消费和现有编辑页；只读/加载/空候选/失效候选/保存失败态完整；候选按项目模型策略过滤；策略不进入 Run Context。备用模型下拉自动排除主模型去重，单次与总等待时间联动单向推高。维护 schemaEpoch，杜绝迟到响应覆盖草稿。
- **代码位置：** `apps/platform-web/src/services/agents/types.ts`、`agents.service.ts`、`agents.service.spec.ts`；`src/modules/agents/pages/AgentEditorPage.vue`、`AgentEditorPage.spec.ts`。
- **预期结果：** 可配置并保存受管策略，context 修改不丢策略；只读用户不能写，项目切换迟到响应不污染。
- **验证项：** `agents.service.spec.ts` 4 passed，`AgentEditorPage.spec.ts` 3 passed；typecheck 0 错误，lint 0 错误。
- **完成日期：** 2026-10-07。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新。

### [x] F02：接入真实失败与模型显示及停止确认

- **负责人：** 前端开发。
- **改动内容：**
  1. `session.service.ts` 与 `workspace.service.ts` cancel 调用接入 `wait=true, action="interrupt"`，封装 4000ms 前端超时保护；
  2. `useChatSession.ts` 解开 `!active` 重试死锁，维护 `unconfirmedStopRunId`，放行未确认停止状态下的重试调用；映射 5 大稳定机器码为安全友好文案；
  3. `useFollowUpSuggestions.ts` 增加 `runStatus` 与 `hasError` 门禁，彻底杜绝失败或停止时乱弹推荐问题；
  4. `trajectory-adapter.ts` 修正真实终态判定，Run 失败/中断时末尾步骤不再无脑标 completed；解析 `platform_model_resilience` 备用模型元数据，未知 ID 安全降级为“备用模型”；
  5. `ChatSession.vue` 与 `ChatMessageList.vue` 呈现“停止尚未确认”横条与备用模型恢复微胶囊 Tag。
- **代码位置：** `apps/platform-web/src/services/threads/session.service.ts`、`services/runtime-gateway/workspace.service.ts`；`src/modules/chat/composables/useChatSession.ts`、`useChatSession.spec.ts`；`src/modules/chat/composables/useFollowUpSuggestions.ts`、`useFollowUpSuggestions.spec.ts`；`src/modules/chat/trajectory/trajectory-adapter.ts`、`trajectory-adapter.spec.ts`；`src/modules/chat/components/ChatSession.vue`、`ChatMessageList.vue`、`ChatMessageList.spec.ts`。
- **预期结果：** 全失败和超时不显示完成，fallback 成功平滑展示备用模型微胶囊；取消超时不卡死，支持核实与重试；推荐问题不乱弹。
- **验证项：** `useFollowUpSuggestions.spec.ts` 7 passed、`trajectory-adapter.spec.ts` 10 passed、`useChatSession.spec.ts` 30 passed、`ChatMessageList.spec.ts` 6 passed；全量前端测试 559 passed，vue-tsc 0 错误，ESLint 0 错误。
- **完成日期：** 2026-10-07。
- **合规检查：** [x] 实现完成；[x] 对应验证通过；[x] tasks 状态更新。

### [x] V02：真实浏览器联合验收

- **负责人：** 前端 + 后端/Runtime 开发，用户人工联合验收。
- **改动内容：**
  1. 真实三服务栈启动与交互，覆盖 AgentEditorPage 容灾配置输入与保存；
  2. 修复等待时间 input `step="1"`（消除 600 秒报错），保存按钮就地高亮反馈；
  3. 修复 `platform-api` 中 `get_internal_runtime_model_config` 返回类型注解为 `-> dict:`，彻底消除嵌套策略字典触发的 FastAPI 500；
  4. 故障注入主模型（死端口 `127.0.0.1:59999`）+ 备用模型（`deepseek-v4-flash`）；
  5. 真实流式对话触发，验证 Connection Refused 后毫秒级平滑降级，输出完整回答，状态为 success；用户在浏览器中测试确认通过。
- **代码位置：** `apps/platform-web`、`apps/platform-api`、`apps/runtime-service`；证据记录于 `verification.md`。
- **预期结果：** 从配置保存到 Run 输出/降级整条链可操作，与后端物理请求/工具计数一致。
- **验证项：** 用户人工验收通过，全链路故障降级输出正常；端到端流式请求 `status: 200`，事件生命周期 `completed`。
- **完成日期：** 2026-10-07，经用户明确验收通过。

## Final

### [x] V03：最终门禁、回退与规范同步

- **负责人：** 全栈责任人。
- **改动内容：** 全范围单元/集成/E2E、性能与安全检查；disabled 默认、混合版本/旧 JSON/旧 ref 与回退演练；同步受影响活规范/FEATURES/CONTEXT/用户 changelog；按 `verify-change` 记录真实 Final。
- **代码位置：** 三服务相关 tests/部署配置、本项目 `verification.md` 与受影响规范。
- **预期结果：** 所有本期任务和验收满足后标 done。
- **验证项：** 单测全部通过（API 17 passed, Runtime 43 passed, Web 559 passed）；端到端故障注入实测通过；文档与状态全面对齐。
- **完成日期：** 2026-10-07。

## 收尾约束

- [x] 本轮规划与基线交付。
- [x] 人工批准 R01~R05，2026-10-06。
- [x] 用户确认 R06 取消设计；跨包任务与平台/前端交接文档已建立，2026-10-07。
- [x] 后端与 Runtime 实现及局部/隔离 Phase 完成；已配置模型矩阵及 V01-C 默认取消/实际子图通过，旧默认失败保留为基线；用户排除 Anthropic 真实 API。
- [x] 前端实现与浏览器联合验收完成，用户人工验收通过（2026-10-07）。
- [x] GraphHarbor 通用取消修复与 V01-C 平台默认配置/实际子图复验完成；双包发布另见 GraphHarbor 专项。
- [x] Final 与回退门禁通过，项目达到 done（2026-10-07）。
- [x] 2026-10-07 用户同意取消经验，已写平台 cross-service 与 GraphHarbor runtime-persistence 经验库及索引；仅对本项目实际验收通过的受影响规范刷新状态，不替原项目批准未验标准。
