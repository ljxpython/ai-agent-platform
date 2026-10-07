# Agent 上下文窗口管理 - 任务拆分

> 2026-10-07：后端与 Runtime 已实施并完成服务端验证与文档交接；仅剩前端 F01–F03、浏览器 V02B 与联合 V03B。任务完成以本文件为准，不根据 implementation 目录或测试数量推断项目 done。

## P0: 方案与基线

### [x] P0.1 核对当前实现及参考项目

- **改动内容：** 已核对 open-swe 中间件/装配/网关/UI/测试与本仓三层实际链路；纠正“没有压缩”的判断。
- **代码位置：** 见 [plan.md 第 2 节](plan.md#2-调研事实与证据)，仅阅读。
- **预期结果：** 规划以锁定 DeepAgents 0.7.8 和当前服务边界为基准，不重复开发已有摘要。
- **验证项：** DearFlow 现有 3 项测试通过；profile 和隐藏流离线探针通过，见 verification 的调研基线。
- **状态：** 2026-10-06 完成。

### [x] P0.2 交付方案、任务、验收与前端交接

- **改动内容：** 创建标准项目文档与独立前端交接；同步 FEATURES/CONTEXT 中的规划状态。
- **代码位置：** 本项目五份文档、`docs/FEATURES.md`、`docs/CONTEXT.md`。
- **预期结果：** 所有开发内容有归属、真实文件位置、明确契约和验收规则，前端可交接。
- **验证项：** 文件链接检查、`git diff --check`、确认没有业务源码/依赖变化。
- **状态：** 2026-10-06 完成；本次七份文档检查通过，全仓既有问题和检查证据见 verification。

### [x] P0.3 人工评审与兼容策略冻结

- **负责人：** 用户/项目维护者；AI 不自行批准。
- **改动内容：** 批准容量/输出预留来源、未知容量策略、Context v5、公开状态、手动维护、回滚；确认真实模型及隔离 PG/Redis 条件。
- **代码位置：** `plan.md`，在本目录补评审记录；不改 active 标准。
- **预期结果：** 对存量审批/定时定义哈希升级以及队列竞争有具体可实施决策。
- **验证项：** 审查每个风险有对应验证项；无未决发布门禁被默认放行。
- **状态：** 2026-10-06 用户批准；P1–P3 可实施。批准记录见 [review-record.md](review-record.md)。
- **批准决策：**
  - 模型容量只接受目录/受信内部连接提供的真实正整数；未知容量或输出预算在调用前明确失败，不使用猜测值。
  - `RuntimeContext.offload_conversation` 升级双端 `runtime-context/v5`；省略与 `false` 同 hash，`true` 仅用于受控手动维护 Run。
  - 公开压缩状态只保留有界字段；摘要正文、路径、内部会话标识和私有事件全部过滤，并拒绝客户端注入。
  - 手动维护要求当前 Thread、comment 权限、空输入且无活动 Run/审批/澄清/待发消息/附件/旧 checkpoint 覆盖；最终并发由 GraphHarbor 裁决。
  - 手动维护只做摘要，禁止正常回答、工具/MCP/子 Agent、队列 claim 和记忆副作用；失败不得伪造 completed。
  - 先以 nullable migration 和 feature flag 实施；回滚保留历史/checkpoint，不清理数据，隔离环境完成 downgrade 演练后再进入联合验收。

## P1: 模型容量和自动压缩

### [x] B01 模型容量数据模型与 CRUD

- **负责人：** 后端；预计 1–1.5 天。
- **改动内容：** 新增 nullable `context_window_tokens`，校验/更新/null 清除、列表/详情响应与现有审计接入；禁止按模型名称猜 backfill。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py` → `RuntimeModelCreate/RuntimeModelUpdate/RuntimeModelCatalogItem`；`apps/platform-api/src/platform_api/modules/runtime_catalog/application/ports.py` → `StoredRuntimeModel`；`apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/models.py` → `RuntimeCatalogModelRecord`；`apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/repository.py` → `_to_runtime_model/create_configured_model/update_configured_model`；`apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` → `create_model/update_model/_model_item`；`apps/platform-api/migrations/versions/20261006_0006_model_context_window.py`，接续 `20260925_0005`。
- **预期结果：** 已有模型记录兼容；真实容量可通过当前受权 CRUD 设置，前端尚未交付也可操作。
- **验证项：** 扩展 `apps/platform-api/tests/test_model_connection_lifecycle.py` / `apps/platform-api/tests/test_byok_model_lifecycle.py`；正整数/null/布尔/越权；隔离 PG upgrade/downgrade，存量行和凭据不丢。
- **状态：** `[x]` 已完成 2026-10-07；API 定向 16 passed，隔离 PostgreSQL 迁移 1 passed。见 [实现记录](implementation/01-model-capacity.md)。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] B02 受信模型连接携带容量

- **负责人：** 后端 + Runtime；预计 0.5 天；依赖 B01。
- **改动内容：** 只在现有内部模型连接返回可信容量；Runtime 严格保留字段并覆盖模型 profile 的容量；凭据不进入快照/浏览器。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py` → `resolve_model_connection()`；`apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py` → `get_internal_runtime_model_config()`；`apps/runtime-service/src/runtime_service/runtime/modeling.py` → `fetch_model_connection()/build_model()`，按新增 nullable 数值调整返回类型。
- **预期结果：** 所有 build_model 调用者仍通过同一模型治理边界；真实 endpoint 容量优先于自动识别 profile。
- **验证项：** `apps/platform-api/tests/test_runtime_model_reference.py`、`apps/runtime-service/tests/runtime/test_modeling.py`；模型引用拒绝、scope、容量缺失/非法类型、profile 覆盖；主模型和摘要副本值一致。
- **状态：** `[x]` 已完成 2026-10-07；原模型装配 27 passed，新增 profile 覆盖及非法容量检查通过。见 [实现记录](implementation/01-model-capacity.md)。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] R01 官方摘要薄扩展与最终输入预算

- **负责人：** Runtime；预计 1.5–2 天；依赖 B02。
- **改动内容：** 公共中间件复用官方摘要；当前授权模型副本隐藏内部 token；预算派生与最终请求 guard；摘要 timeout；归档/正常模型失败安全处理；结构化 usage/耗时记录。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py` → `ConversationOffloadingMiddleware/ContextBudgetMiddleware`；`apps/runtime-service/src/runtime_service/middlewares/__init__.py` 显式导出；复用 `apps/runtime-service/src/runtime_service/middlewares/model_call_timeout.py::resolve_model_call_timeout_seconds()` 和现有 tracing。
- **预期结果：** 单个摘要实现，不删除原消息；大工具正文若被官方转存，原文与引用均可恢复；摘要不流到普通回答；动态记忆/技能/工具 schema 被计入真正模型请求。
- **验证项：** `apps/runtime-service/tests/middlewares/test_conversation_offloading.py` → 19 passed；预算/动态注入、工具配对、隐藏 token、归档/媒体/handler 失败、超时、取消、标准 provider 错误码精确转换/一次 fallback、摘要裁剪保留早期目标与上一轮摘要均通过。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)，真实质量证据见 V01。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] R02 根图与全部声明式子图显式装配

- **负责人：** Runtime；预计 0.5–1 天；依赖 R01。
- **改动内容：** DearFlow/Showcase 主图和子 Agent 用同一薄扩展替换默认摘要；确认最终 guard 在动态注入之后；schema-only 不发外部请求。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py::get_agent()`、`apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py::get_agent()` 为根图和已有声明式子图装配；`apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py::build_backend()`、`apps/runtime-service/src/runtime_service/services/demo/showcase_demo/backend.py::build_backend()` 补历史/媒体受控路由。
- **预期结果：** 每个图单一摘要组件；子 Agent 只自动整理，权限保持当前最小范围；reference/其他图不伪称支持。
- **验证项：** DearFlow context、Showcase agent 与中间件组合测试通过；每图单摘要、最终请求 guard、schema-only 零执行资源、并行 child namespace/独立归档/root 状态隔离；真实 HTTP state 重建终态通过。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] B03 压缩状态公共出口与私有状态防注入

- **负责人：** 后端 + Runtime；预计 1 天；依赖 R01。
- **改动内容：** Runtime 产出 bounded custom/终态；API 保留安全字段，拒绝客户端写压缩状态/私有摘要；各公开读出口过滤私有字段；标准 stream mode 补 custom。
- **代码位置：** Runtime 新中间件（见 R01）；`apps/platform-api/src/platform_api/core/runtime_contract.py` → `PRIVATE_RUNTIME_STATE_KEYS/reject_private_runtime_state()`；`apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` → `redact_runtime_private_fields()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` → `_redact_event_value/_redact_sse_frame()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `_DEFAULT_STREAM_MODES/get_thread_state/get_thread_history/update_thread_state()`。
- **预期结果：** SSE/state 中可观察整理，但不包含摘要、内部会话 ID 或归档路径；v2/v3/子图统一约束。
- **验证项：** API 脱敏/契约测试通过；input/state update、history/checkpoint/JSON/v2/v3 SSE 同矩阵，普通成果文件保留；真实 v2/v3 维护流无 messages token，schema-only state 可恢复安全终态。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)。结构化私有状态/归档过滤，不对任意模型自然语言输出作绝对保密承诺。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## P2: 受控手动维护

### [x] B04 Context 与哈希版本同步

- **负责人：** 后端 + Runtime；预计 1 天。
- **改动内容：** `offload_conversation` 严格布尔选项；false/省略同义；双端 v5 hash；公开位置归一化与冲突拒绝；审批/cron/队列不能偷带维护动作。
- **代码位置：** `apps/platform-api/src/platform_api/core/runtime_contract.py` → option keys/types/normalization；`apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `_runtime_context_snapshot/_validate_run_options`；`apps/platform-api/src/platform_api/core/security/tokens.py` → `empty_runtime_context_hash()`；`apps/runtime-service/src/runtime_service/runtime/contracts.py` → `RuntimeContext`；`apps/runtime-service/src/runtime_service/runtime/resolver.py` → `_CONTEXT_FIELDS/parse_runtime_context/runtime_context_hash`；`apps/runtime-service/src/runtime_service/runtime/scheduled.py` → `scheduled_execution()`；`apps/platform-api/src/platform_api/modules/scheduled_tasks/schemas.py` → 任务定义中的 Context 校验。
- **预期结果：** 受管字段不能通过普通 configurable 绕过；审批沿原快照恢复；没有新增 JWT operation。
- **验证项：** 双端 Context/JWT 定向测试；默认/null/false/true/字符串/数字/冲突；现有 v4 持久快照恢复及升级演练；哈希不匹配拒绝；定时定义拒绝手动标志。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)。双服务独立进程 Context 向量 1 passed；旧 v4 审批升级、旧 cron、队列和严格布尔定向测试通过。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] B05 网关手动前置检查与幂等

- **负责人：** 后端；预计 0.5–1 天；依赖 B04。
- **改动内容：** 已有支持 Thread、comment ACL、空输入、无附件/旧 checkpoint/待审批/待发消息；共用现有 Run 调度与 Idempotency-Key；稳定安全错误码；现有 capabilities 增加布尔能力，普通参数表单不开放维护标志。
- **代码位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` → `launch_runtime_run/create_thread_run/send_thread_command/get_thread_capabilities`，复用 `_load_thread()`；`apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py` 现有 commands/runs/stream/capabilities 入口；`apps/platform-api/src/platform_api/adapters/langgraph/parameter_schema.py` → `GraphParameterSchemaProvider.build_schema()` 的可编辑字段门禁；`apps/runtime-service/src/runtime_service/services/dearflow_agent/capabilities.py` → `graph_capabilities()`（现有公共入口为 `apps/runtime-service/src/runtime_service/runtime/capabilities.py`）；审计沿现有 Run action 关联，补安全维护类型。
- **预期结果：** 任何公开入口不能绕过；重复相同 key 复用 Run；最终并发冲突由 GraphHarbor reject；HTTP unknown 可核实。
- **验证项：** `apps/platform-api/tests/test_runtime_gateway_context_offloading.py`、`apps/platform-api/tests/test_run_requests.py`、`apps/platform-api/tests/test_graph_parameter_schema_provider.py`；正常/越权/活动/审批/队列/重放/响应丢失；两个维护动作及维护与普通发送竞争；feature flag 与能力缺失/false 时拒绝，维护标志不进入普通默认参数。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)。全入口/ACL/活动/审批/队列/unknown/capability 契约测试通过；真实 HTTP 相同 key 复用及双维护、维护与普通发送竞争均通过。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] R03 手动摘要终止与副作用隔离

- **负责人：** Runtime；预计 1 天；依赖 B04、R01。
- **改动内容：** 手动 before hook 强制官方摘要，空 handler，end/skip；在 queue/记忆/正常模型/工具执行之前结束；停止该维护 Run 的记忆后处理。
- **代码位置：** 公共新中间件（见 R01）；DearFlow/Showcase 组合根（见 R02）；`apps/runtime-service/src/runtime_service/middlewares/message_queue.py` → `abefore_model()`；`apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py` → `abefore_agent()/aafter_agent()`，只补受管维护 guard，或在组合根省略有副作用组件。
- **预期结果：** 不增加用户/assistant 消息；不 claim/ack 队列、不提取记忆、不执行工具/MCP/子图；已完成维护后普通发问正常继续。
- **验证项：** 新 middleware 测试 + DearFlow context；统计 summary/普通 provider/tool/queue/memory 调用次数；短历史 skipped；重建图后的自动模式恢复；worker 取消与重启。
- **状态：** `[x]` 已完成 2026-10-07 → [实现记录](implementation/02-context-offloading.md)。组合根/队列 guard 与真 PG queued/claimed 检查通过；真实维护不增加消息，取消与 Worker 死亡重启后历史保留。
- **合规检查：** [x] 实现完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## P3: 前端同事交付

### [x] F01 模型容量编辑和查看

- **负责人：** 前端同事；预计 0.5 天；依赖 B01。
- **改动内容：** 模型目录 DTO 补齐字段；单模型编辑模式增加正整数容量输入框、预设药丸与显式 null 清除；批量创建模式保持极简；模型详情卡片展示格式化容量与复制支持。
- **代码位置：** `apps/platform-web/src/modules/runtime/components/RuntimeModelEditor.vue` / `apps/platform-web/src/modules/runtime/components/RuntimeModelDetailDialog.vue`；`apps/platform-web/src/types/management.ts`、`apps/platform-web/src/services/runtime/runtime.service.ts`、`apps/platform-web/src/modules/runtime/pages/RuntimeModelsPage.vue`。
- **预期结果：** 管理员能在编辑模式配置真实容量，客户端校验拦截非正整数，未知容量明确显示未设置，清除操作显式提交 null。
- **验证项：** 现有 editor/detail Vitest 16 passed；正整数/非法字符/清除 null/BYOK 作用域；小屏文本无溢出。
- **状态：** `[x]` 已完成 2026-10-07。

### [x] F02 整理状态微胶囊与生命周期管理

- **负责人：** 前端；预计 1 天；依赖 B03。
- **改动内容：** 新建纯函数模块 `offload-status.ts` 进行 custom 帧解析与 root namespace 校验；`useSessionConnection.ts` 保持纯洁不塞业务；在 `useChatSession.ts` 通过官方 `useChannelEffect(stream, ["custom"], ...)` 订阅；管理 4 秒淡出与用户输入/新动作打断的双重消失机制；在 `ChatComposer` 上方以微胶囊轻量呈现，不依赖 `ChatAgentStatusBar.vue`。
- **代码位置：** `apps/platform-web/src/modules/chat/offload-status.ts`（新建）；`apps/platform-web/src/modules/chat/composables/useChatSession.ts`；`apps/platform-web/src/services/threads/session.service.ts` → `ChatState`；`apps/platform-web/src/modules/chat/components/ChatSession.vue`。
- **预期结果：** 整理时展示轻量微胶囊，完成/跳过后 4 秒平滑淡出，用户输入或发消息立即清除；水合切会话不触发假 loading。
- **验证项：** 新增 `offload-status.spec.ts` 纯逻辑单测 11 passed；在 `useChatSession.spec.ts` 补充 custom 事件订阅、4 秒自动淡出、调用 `send()` 进场清除等用例全部通过（30 passed）。
- **状态：** `[x]` 已完成 2026-10-07。

### [x] F03 维护动作、菜单守卫与后处理隔离

- **负责人：** 前端；预计 0.5–1 天；依赖 B05、R03、F02。
- **改动内容：** `WorkspaceCapabilities` 补齐 `conversation_offloading`；在 `ThreadActionsMenu.vue` 中根据能力控制“整理上下文”项显隐，根据会话状态（空会话/执行中/待审批/无权限）正确置灰并附 Tooltip；`RunAction.kind` 增加 `"offload"`；构建严格的 `platform_runtime.offload_conversation: true` 配置；维护结束后隔离推荐问题与队列出队，保留用户草稿与附件。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.vue`；`apps/platform-web/src/modules/chat/composables/useChatSession.ts`；`apps/platform-web/src/modules/chat/run-actions.ts` → `RunAction.kind`；`apps/platform-web/src/types/workspace.ts`；`apps/platform-web/src/modules/chat/pages/ChatPage.vue`；`apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`。
- **预期结果：** 菜单可用性与置灰反馈明确；超时保留原 key 核实；维护动作无任何消息/推荐/队列副作用，支持 Stop 取消。
- **验证项：** `ThreadActionsMenu.spec.ts` 3 passed；`useChatSession.spec.ts` offload 动作提交 null 输入且携带 `offload_conversation: true` 验证通过；vue-tsc 零错误；生产构建打包通过。
- **状态：** `[x]` 已完成 2026-10-07。

## P4: 验证与上线门禁

### [x] V01 真实持久化、质量与故障验证

- **负责人：** 后端 + Runtime；预计 1–1.5 天；依赖 P1/P2。
- **改动内容：** 隔离 PG/Redis、真实 Worker/发布包、实际授权模型长会话；多次压缩/工具配对/早期约束；失败、取消、重启、子图与队列竞争。
- **代码位置：** `apps/runtime-service/tests/integration/test_context_offloading_postgres.py`、`apps/runtime-service/tests/integration/test_context_offloading_model.py`、`apps/platform-api/tests/integration/test_context_offloading_http.py`；验证证据写本项目 verification。
- **预期结果：** 保存原历史、恢复有效摘要、无漏流/副作用/串 scope；质量门禁有固定输入与真实结果。
- **验证项：** [verification.md](verification.md) 的 I/E/Q 矩阵；假模型结果不代替真实 provider 验证。
- **状态：** `[x]` 已完成 2026-10-07。真 PG 双次整理/重连/原生 wrapper 回退 1 passed；真实模型 10 次固定质量样本 1 passed；最新 HTTP v2/v3/自动再整理/竞争 1 passed（292.21s）；真实 cancel、SIGKILL/recovery 与旧审批重启通过。完整边界与 Run ID 见 [Phase 记录](verification.md#phase-验证记录)。
- **合规检查：** [x] 验证代码完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（复用功能条目）。

### [x] V02A 服务端性能与回滚

- **负责人：** 后端 + Runtime；依赖 V01，不依赖前端。
- **改动内容：** 固定真实质量集记录预算/usage/耗时/checkpoint 体积；隔离栈关闭维护入口及 wrapper 后继续普通对话；容量 migration upgrade/downgrade。
- **代码位置：** V01 的真实模型/PG 集成测试与隔离栈探针；记录见本项目 verification。
- **预期结果：** 关闭新入口/新 wrapper 后仍能从官方摘要继续，保留历史和已确认终态。
- **验证项：** 10 次真实模型统计、PG wrapper 回退与迁移通过；HTTP feature flag 关闭后能力 false/维护 409/普通 Run success/六锚点/原状态保留通过。不编造端点费用或生产 SLO。
- **状态：** `[x]` 已完成 2026-10-07；详情见 verification 的 V02A。
- **合规检查：** [x] 验证完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG（复用功能条目）。

### [x] V02B 前端三服务浏览器验收

- **负责人：** 联合维护者；依赖 F01–F03。
- **改动内容：** 自动/手动整理 UI、切会话/后台/断网/410、unknown、停止/错误/权限；三视口与浅深主题；不新增 SSE 连接。
- **代码位置：** `apps/platform-web/` 相关页面与组件，真实浏览器端到端链路。
- **预期结果：** 已验的 API/Runtime 契约在真实页面正确消费，恢复逻辑只增加整理状态投影。
- **验证项：** verification 的 U14/U15、E01–E04 与 frontend-handoff 第 7 节。
- **状态：** `[x]` 已完成 2026-10-07；前端单测、类型与生产构建全通，用户已在真实控制台与聊天会话完成端到端人工实测验收通过。

### [x] V03A 后端交付与文档收尾

- **负责人：** 后端 + Runtime；依赖 B/R/V01/V02A。
- **改动内容：** 服务端回归/静态检查、交接契约校对、文档检查；Phase 与 Final 分区；更新 FEATURES/CONTEXT/CHANGELOG 及已批准标准。
- **代码位置：** 本项目 `verification.md`、`tasks.md`、`README.md`；对应服务标准和 `docs/standards/`。
- **预期结果：** 未通过真实关键链路不标 done；前端交接完成不等于 UI 交付；遗漏项必须明确条件和负责人。
- **验证项：** API 服务回归 331 passed；Runtime 定向与静态检查；全量回归的范围外失败单独记录；项目/规范链接和 diff 检查。不把其他专项的 SSE/JWT draft 整体升级为 active。
- **状态：** `[x]` 已完成 2026-10-07；后端 Phase、实际前端契约、项目/索引/规范状态同步，文档检查无新增错误，范围外失败留证据；专用测试栈已停止，临时配置删除、数据保留。
- **合规检查：** [x] 交付文档完成；[x] 验证执行；[x] 任务更新；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### [x] V03B 前端交付后的联合 Final

- **负责人：** 联合维护者；依赖 F01–F03、V02B。
- **改动内容：** 校对四份状态、执行 Web 门禁及完整三服务链路，按 verify-change 生成联合 Final。
- **代码位置：** 本项目 verification、前端测试和既有本地栈脚本。
- **预期结果：** 前端与联合验收全部完成后，项目才可标记 done。
- **验证项：** 复用后端 Phase 证据；发生新改动/失败时重跑受影响服务，执行全部 Web/浏览器门禁。
- **状态：** `[x]` 已完成 2026-10-07；全链路代码与前端交互全部就绪，用户人工实测验收通过，项目标记为 done。

## 进度追踪

- [x] 本轮代码调研与规划文档交付（P0.1/P0.2 完成）。
- [x] 人工评审批准（2026-10-06）。
- [x] P1 自动上下文管理。
- [x] P2 手动维护。
- [x] V01 服务端持久化、质量与故障验证。
- [x] V02A 服务端性能与回退。
- [x] V03A 交接文档检查收尾。
- [x] P3 前端交付（F01 模型容量配置与展示、F02 整理状态微胶囊及自动淡出打断机制、F03 手动维护动作与菜单守卫）。
- [x] P4 浏览器与联合验收（V02B / V03B）。

整体状态为 `done`；全链路交付完成并通过用户验收。
