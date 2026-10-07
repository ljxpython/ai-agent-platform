# Agent 上下文窗口管理 - 整体方案

> 2026-10-07：方案已评审批准，后端与 Runtime 已按本方案实施；前端 F01–F03 和浏览器联合验收仍待交付。本文件是项目设计事实源，不替代 `docs/standards/` 的生效标准。

## 1. 问题与目标

本次只补上下文窗口管理。长任务的稳定性需要四个环节：知道模型实际容量、压缩模型输入、保存恢复依据、让调用方识别整理状态。浏览器历史懒加载、长期记忆和 checkpoint 空间优化是相关但不同的问题。

目标是自动压缩不泄漏摘要，手动压缩不执行正常任务，重启后有效上下文与历史仍可恢复，并能在异常时给出明确状态。验收不以“没有抛 `context_length_exceeded`”作为唯一标准，还要检查目标、约束、来源和工具配对。

## 2. 调研事实与证据

### 2.1 版本与阅读范围

| 对象 | 本轮基线 |
|---|---|
| 当前仓库 | HEAD `424ff90e4f9a5c06c32c17f84a2cdaed73b65ef6`，调研开始时工作树干净 |
| open-swe | 用户指定的本地参考仓库 `research/open-swe`，HEAD `ad417d64d91cc349d63d832c7b643637dc1774cf`；下文路径相对该仓库根目录 |
| Runtime 锁定依赖 | `deepagents 0.7.8`、`langchain 1.3.17`、`langchain-core 1.6.0`、`langgraph 1.2.11`、`graphharbor 0.13.0.post41`，见 `apps/runtime-service/uv.lock` |
| 官方资料 | 已查询 langchain-docs 与 langchain-reference MCP；在线文档可能比锁定包更新，行为以锁定包源码与离线测试复核 |

已读 Runtime 开发规范、Platform API 开发/网关规范、Web 三份入口规范、跨服务 SSE/JWT 健康表及 Runtime/跨服务经验库。新方案沿用组合根、模块化单体、官方 SDK 与既有身份边界。

官方参考：[Context engineering](https://docs.langchain.com/oss/python/deepagents/context-engineering)、[SummarizationMiddleware](https://reference.langchain.com/python/deepagents/middleware/summarization/SummarizationMiddleware)。

### 2.2 open-swe 实际实现

下表路径均相对参考仓库根目录。

| 位置 | 事实行为 | 可以借鉴什么 |
|---|---|---|
| `agent/middleware/conversation_offloading.py` → `ConversationOffloadingMiddleware` | 继承官方摘要，用 `name="SummarizationMiddleware"` 替换默认项；模型副本加 `nostream` / `langsmith:hidden`；复用 `compute_summarization_defaults()` | 替换而非重复装配；业务无关的内部流抑制 |
| 同文件 → `_status()` / `_acreate_summary()` / `awrap_model_call()` | `custom` 写 `conversation_offloading` 进度；成功 command update 增加 checkpoint 状态；摘要异常发 `failed` | 实时提示加持久终态，二者分开 |
| 同文件 → `abefore_model()` | 手动模式通过 `ContextVar` 强制触发；使用不调用正常模型的空 handler；`jump_to="end"`；不足以压缩时 `skipped` | 手动动作是一次维护 Run，不伪造用户发问 |
| `agent/server.py` 约 1267/1276 行 | 主图与通用子 Agent 均装配；主图接收 `cfg.offload_conversation`，子图仅自动 | 根图/子图内部摘要都需要隐藏；手动只作用于根图 |
| `agent/run_config.py` → `RunConfig.offload_conversation` | 默认 `False`；`True` 表示本次手动压缩 | 不是自动压缩开关 |
| `agent/dashboard/threads/runs.py` → 运行命令处理 | 已有 Thread 才能整理；重新构造受信配置；手动时 `input={}` | 服务端验证，不能只靠 UI 禁用 |
| `ui/src/features/agents/lib/provider/useSubmitAgentMessage.ts` | `/offload` 发空输入，不进入消息队列；拒绝活动 Run 和附件 | 独立维护动作的语义；不照搬 slash-command 产品形态 |
| `ui/src/features/agents/lib/stream/AgentStreamProvider.tsx` | SDK `custom` 订阅；忽略非根 namespace；结束/异常清整理状态 | 复用 SDK，压缩状态从属 Run |
| `tests/middleware/test_conversation_offloading.py` | 覆盖隐藏流、手动后恢复、原历史不变、默认摘要替换、无可压缩历史 | 按真实图/流行为验证，不能只测类方法 |

需要修正两种误读：归档的是原始对话文本/媒体引用，摘要主要在 checkpoint 私有事件中；“沙箱文件恢复摘要”不能代替 checkpoint 恢复。open-swe 的 `completed` 会在正常模型 handler 执行前发出，也不证明最后一个 checkpoint 已提交。

### 2.3 当前代码实际情况

| 位置 | 已有能力 | 本期缺口 |
|---|---|---|
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` → `get_agent()` | `create_deep_agent` 默认官方摘要；模型/工具限制、超时、ACL、队列、技能/记忆 middleware | 无专用压缩事件、内部流抑制与手动动作；预算要覆盖后续动态注入 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py` → `build_backend()` | `/conversation_history/`、`/large_tool_results/` 路由到 `StateBackend`；禁止模型修改历史/大结果 | 需要真实 PG 重启、多次压缩、子图及归档失败验证；不改为外部沙箱 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` / `backend.py` / `subagents.py` | 默认官方摘要与历史 `StateBackend`；声明式子 Agent | 同一能力接入样板；核查大结果/媒体新路径是否落受控 backend |
| `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py` | 使用 `create_agent`，无摘要 | 明确未支持；本期不增加文件工具来改变其教学职责 |
| `apps/runtime-service/tests/services/dearflow_agent/test_context.py` | 官方摘要保留记忆来源、队列回执和归档；预算跨重建图保存 | 本轮 3 passed；不证明生产组合根、真实模型或真实 Worker 全链路通过 |
| `apps/runtime-service/src/runtime_service/runtime/modeling.py` → `build_model()` / `fetch_model_connection()` | 按当前授权兑换模型连接，不落凭据到 Run | 没有容量元数据；默认 DeepSeek/未知代理的 profile 已实测为 `None` |
| `apps/platform-api/src/platform_api/modules/runtime_catalog/` | 模型目录、BYOK、权限和受信内部连接接口 | 模型记录/公开 DTO/内部连接都没有上下文容量字段 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py` | Context 快照、幂等、模型引用、ACL、原生并发拒绝 | 不接受手动压缩选项；快照/哈希/所有入口需同步 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` → `redact_runtime_private_fields()` | 递归删除模型引用等私有字段 | 未显式过滤 `_summarization_event` / `_summarization_session_id`；官方 PrivateStateAttr 不能替代公开出口检查 |
| `apps/platform-web/src/modules/chat/composables/useSessionConnection.ts` / `useChatSession.ts` | Vue 官方 SDK、恢复快照、ACL、会话池 | 没有压缩状态消费与维护动作；后台会暂停 SSE，不能只靠内存布尔值恢复 |

锁定包行为也已核实：`compute_summarization_defaults()` 有 profile 时使用 85% 触发/10% 保留，无 profile 时退回 170000 token/6 条消息；`awrap_model_call()` 统计它看到的 system/tools/messages、支持 `ContextOverflowError` fallback，私有事件累计 cutoff，常规摘要不删除消息。overflow 分支还可能将过大 ToolMessage 正文转存至 `/large_tool_results/` 并在 state 同 ID 消息内替换为引用，不能承诺所有历史正文始终原样驻留 messages；原文可恢复性必须同时验收文件载体。原始 DeltaChannel 序列化不能直接当普通 messages 数组读取，应使用 `graph.aget_state()`。

### 2.4 对同事建议的逐项判断

| 建议 | 结论 | 调整 |
|---|---|---|
| “没有压缩，靠报错发现” | 部分不准确 | DeepAgents 图已有自动摘要与标准溢出 fallback；存在 profile 缺失和具体 provider 错误映射未验问题 |
| 新建公共 `conversation_offloading.py` | 采纳薄扩展 | 继承官方能力，单个默认摘要替换；不复制源码或实现摘要循环 |
| 摘要加 `nostream` | 采纳 | 只给模型副本加标签；保证主模型仍流式；观测与费用保留 |
| 统一阈值 80000 | 不采纳为容量依据 | 优先受管目录容量，再官方 profile；阈值按预算派生，禁止浏览器传容量 |
| RunConfig `offload_conversation: bool` | 采纳手动语义 | 放现有受管 RuntimeContext；`true` 是独立维护 Run，`false` 不关闭自动策略 |
| 摘要文件写 sandbox 持久化 | 不移植存储 | 保留当前 checkpoint + StateBackend；不增加沙箱供应商依赖 |
| state event + SSE 提示 | 采纳并补恢复规则 | 实时进度、持久终态、Run 终态分别处理；去掉摘要、路径、原文；补 namespace、幂等与迟到事件保护 |

## 3. 三层职责与调用链

```text
Web 手动动作/普通消息
  -> Platform API: 当前 ACL、Agent/模型策略、严格选项、幂等快照、Context 哈希
  -> GraphHarbor: 原生 Run 调度/并发裁决、checkpoint、事件流
  -> Runtime agent.py: 已验证身份 + 模型容量 + 官方摘要薄扩展
  -> custom 进度 / checkpoint 脱敏终态
  -> Platform API 统一过滤
  -> Web 官方 SDK 提示与恢复
```

前端不计算压缩阈值、不调用模型、不拉完整历史重组 Prompt、不修改 messages。后端不生成摘要或新建压缩任务表。Runtime 不承载平台模型目录 CRUD、浏览器状态或额外用户权限数据库。

## 4. Runtime 方案

### 4.1 共享位置和装配

拟新增 `apps/runtime-service/src/runtime_service/middlewares/conversation_offloading.py`，包含 `ConversationOffloadingMiddleware`、必要的最终输入预算 guard 和少量纯预算函数；在 `middlewares/__init__.py` 显式导出。不新增 Builder/Registry。

在 DearFlow 与 Showcase 的 `agent.py`，用已解析/授权的当前模型和既有 backend 显式装配；声明式子 Agent 同样覆盖默认摘要，手动标志不向子图扩散。保留官方 `name="SummarizationMiddleware"` 的替换语义，组合测试必须证明每个图只存在一个摘要组件。

薄扩展预计覆盖 `_should_summarize()`、`_acreate_summary()`、`_aoffload_to_backend()`、`_aoffload_inline_media()`、`_build_new_messages_with_path()` 和 `awrap_model_call()`，分别用于手动触发、内部超时/事件、归档结果检查、媒体失败检查、步骤成功事件及安全终态更新；手动路径使用 `abefore_model()`。这些私有 hook 与锁定版本绑定，依赖升级须重跑组合测试；不复制官方摘要循环、cutoff 算法或消息 reducer。同步调用若仍被支持，也必须有同等门禁；本期异步图不得绕入无保护的同步摘要。

### 4.2 容量与预算

采用目录可空正整数 `context_window_tokens`，语义为当前端点部署版本支持的总窗口上限。优先级：平台目录显式值 > 已识别真实 provider/model 的官方 profile `max_input_tokens` > 未知。别名/代理官方 profile 只能作为已核实端点的参考，不能声称等于部署容量。

- `C`：可信容量；`R`：本次明确的 `max_tokens`，否则已核实端点的可信 profile `max_output_tokens` 上限。两者都未知时，在模型调用前返回 `runtime.context.output_budget_unknown`，要求用现有 Agent/Run 参数补齐 `max_tokens`；不猜预留值，不悄悄修改用户生成参数。显式输出预算超过已知 provider 上限时明确拒绝。
- `M = max(1024, ceil(0.05 * C))`：拟定安全余量，待基线测量确认。
- `B = C - R - M`：可用输入预算；非正或不能容纳固定 Prompt/工具时，在模型调用前明确失败。
- 自动触发使用公开 `trigger=("tokens", floor(0.85 * B))`，保留目标使用 `keep=("tokens", floor(0.10 * B))`；保留合法工具批次优先于机械裁剪到整数 token。
- token counter 先复用官方包含 tool schema 的计数能力；真实 tokenizer 可用时使用，未知 tokenizer 明确为估算，多模态单独验收，禁止标为精确使用率。
- 摘要调用单独核对其 system Prompt、待摘要内容及输出预留；不能因为主模型 guard 存在就假定内部调用已受限。锁定版默认只摘要最近约 4000 token，需要质量验收再调整公开 `trim_tokens_to_summarize`，不能默认无限放大。

官方 profile 的 `max_input_tokens` 文档称为 context window，但代理部署可能使用不同窗口或独立输入/输出限制。目录字段以共享总窗口为固定语义；仅使用 profile 时，本期保守从该值再扣输出预留并记录来源，不将其宣传为端点精确剩余容量，发布前须核实端点预算语义。

未知容量策略：灰度开关启用前由管理员补齐目录；启用后不接受将 170000/80000 猜测值作为生产窗口，明确 `runtime.context.capacity_unknown`。容量和输出预算必须同时有来源；缺少任意一项均不放行新策略。该策略会影响当前无 profile 且未设置 max_tokens 的模型，属于明确的兼容性评审项；旧策略回退只用于受控回滚。

### 4.3 最终请求预算与 middleware 顺序

当前官方摘要在核心 stack 中，技能/记忆等自定义 `awrap_model_call()` 会在其后增加 system 内容，RuntimeConfig 也会过滤工具/切换模型。仅对摘要入口计数不能保证最终请求预算。

本期保持默认摘要的替换位置，在服务显式装配的模型边界末端增加一个最小输入 guard，使用 `request.model`、最终 system/tools/messages 和同一个计数器检查 `B`。超预算且未压缩时抛框架标准 `ContextOverflowError`，由外层官方摘要 fallback 一次；已压缩仍超预算则明确失败，不自建第二层重试。

组合测试须抓取到真正 provider handler 看到的请求，证明动态技能/记忆已算入、工具已授权过滤、预算 guard 在这些变化之后；不能只看传给 `create_deep_agent` 的列表。若锁定框架的合成顺序不能满足门禁，先记录 Spike 决策再改设计，不注册跨请求全局 profile 来调整某一 Run。

### 4.4 摘要模型、失败与持久化

- 使用当前授权模型的副本加 `nostream` / `langsmith:hidden`，不污染主模型，不另取模型凭据、不新增摘要模型选择器。
- 摘要模型调用是内部调用，现有主模型 ModelCallLimit/Timeout 不一定包住它；摘要步骤使用 `asyncio.timeout` 与既有 `resolve_model_call_timeout_seconds()`。沿用官方有限摘要重试，不再叠加自建重试。
- `langsmith:hidden` 不隐藏 Langfuse 或计费；通过当前 tracing 记录摘要调用/耗时/失败及输入输出 usage（可用时），日志不记录正文/凭据。
- 复用官方 `_summarization_event` 和会话归档；只在成功结果 command update 上追加一个有界 `conversation_offloading` 终态，不写无限事件数组。
- 归档失败不得对外宣称 history 已保存；本期默认维护/自动压缩失败，不提交新有效摘要。现有 messages/checkpoint 保留，可核实后重试；禁止 fallback 成无来源截断。
- 自动摘要还须覆盖 provider 已映射的 `ContextOverflowError`，不对任意异常/字符串做宽泛兜底；未知 provider 映射通过定向测试补齐。
- 锁定 OpenAI/DeepSeek SDK 原先不转换标准 400；本期在最终模型 guard 只转换 `BadRequestError.code=context_length_exceeded`，进入官方一次回退。真实摘要/回答结合受控 HTTP 错误验证，不把合成错误称为远端自然窗口溢出。
- `completed` live 事件只表示压缩步骤得到成功结果，checkpoint 确认才表示可恢复；如果后续模型 handler 失败，外层也发 `failed`，不能只捕获 `_acreate_summary()` 的错误。
- 原始历史、媒体引用与压缩后的有效输入是不同载体；不删除浏览器对话消息，不把 StateBackend 的 file_path 当可公开下载文件。若官方 overflow 转存替换过大工具正文，沿现有受权文件读取保留可恢复性，不能声称该工具正文仍原样驻留 state；转存失败必须结束，不能保留失效引用。

### 4.5 手动维护 Run

`offload_conversation=true` 时，从最新根 checkpoint 整理，输入必须为空；摘要成功/无可压缩范围后通过 hook 跳到结束，不产生正常 assistant 回答，不运行工具/子 Agent。

不能直接复制 open-swe 的 before-model 位置：本项目有 `MessageQueueMiddleware`、`MemoryContextMiddleware` 和持久待发队列。手动路径在任何队列 claim 前结束，并禁止该路径的记忆候选提取、正常调用预算累计及后续 prompt drain。可以在现有 queue/memory hook 加受管 Context guard，或在组合根为维护 Run 省略对应组件；优先选择改动更小且重启语义清晰的一种，测试证明副作用为零。

前置检查：已有 Thread、支持的 graph、当前 `comment` 权限、无 pending/running Run、无待审批/澄清、无持久待发消息、无附件/消息/旧 checkpoint override。平台预检用于明确反馈，最终并发仍由 GraphHarbor 原子 reject 裁决。若待发调度与维护 Run 的抢占不能由原生并发保证，必须保留队列原语义并记录整合阻塞，不在 API 新造进程内锁。

## 5. Platform API 与契约

### 5.1 模型目录

在现有模型 CRUD 增加 `context_window_tokens: int | null`；严格正整数，布尔/0/负数/字符串拒绝，nullable 保持存量迁移兼容，`null` 明确清除受管值。平台模型与 BYOK 沿用当前编辑权限与审计。

改动集中在 `apps/platform-api/src/platform_api/modules/runtime_catalog/` 的 `domain/models.py`、`application/ports.py`、`application/service.py` 的模型 CRUD/`resolve_model_connection()`、`infra/sqlalchemy/models.py` / `repository.py` 及现有 migrations，完整位置见 tasks B01/B02。内部 `/api/runtime/internal/model-config` 增加该可选值；Runtime `fetch_model_connection()` 保留并验证字段，调整返回类型，不把凭据暴露到公开 Run。

新迁移只加可空列，不按模型名称自动猜测 backfill；在隔离 PG 验证 upgrade/downgrade 和存量数据保留，再由授权管理员配置真实容量。前端未上线时后端 CRUD 也应可配置，不阻塞 Runtime 自动能力验证。

### 5.2 手动选项与 Context 哈希

新增受管 `RuntimeContext.offload_conversation: bool = False`，外部入口使用 `config.configurable.platform_runtime.offload_conversation`；保持标准 Context 路径也接受，但互相冲突必须拒绝。禁止顶层 `configurable.offload_conversation` 旁路。

API `core/runtime_contract.py`、网关 `_runtime_context_snapshot()`、运行配置验证、Runtime `runtime/contracts.py` / `resolver.py`、双端空 Context hash 同步增加字段，拟升级 `runtime-context/v5`；默认/省略/`false` 必须规范为同一个 hash。拟定固定字段：model_id、temperature、max_tokens、top_p、execution_mode、access_policy、offload_conversation。

这是受管契约变更，不能只扩 Runtime dataclass；审批 resume 保持原快照，禁止顺带开启手动压缩。定时任务/持久队列定义不能保存手动维护选项，防止周期任务只整理不执行。无新增 JWT operation，仍使用当前 `run-create` 且绑定最新 Context hash。

### 5.3 公共请求与状态

复用 `POST /api/langgraph/threads/{thread_id}/commands`，`Idempotency-Key` 覆盖维护动作；标准 `/runs`、`/runs/stream` 共用相同校验，不允许换入口绕过守卫。不新增 maintenance endpoint/table。

支持能力复用现有 `GET /api/langgraph/threads/{thread_id}/capabilities`，增加只读 `conversation_offloading: bool`，由 Runtime 现有 `graph_capabilities()` 按图接入情况与 `AGENT_CONTEXT_MANAGEMENT_ENABLED` 声明，API 结合当前 Thread `comment` 权限裁决；这不是新的授权。前端与网关手动预检使用同一能力来源，不根据共享 RuntimeContext 字段或 graph 名称推断支持。`GraphParameterSchemaProvider` 的普通可编辑字段继续排除 `offload_conversation`，避免将维护动作保存为 Agent 默认参数；不新增能力 endpoint/registry。

手动请求示例见 [前端交接](frontend-handoff.md)。ACK 是 Run 接受，不是压缩成功。错误分支沿用 error-envelope；拟定安全码：`context_offload_not_supported`、`context_offload_empty_thread`、`context_offload_input_invalid`、`context_offload_pending_input`、`context_offload_interrupt_pending`，并复用既有 ACL/并发/幂等错误。

对外 `custom` payload 及 `values.conversation_offloading` 使用相同有界结构：

```json
{
  "type": "conversation_offloading",
  "operation_id": "opaque-id",
  "run_id": "server-run-id",
  "status": "completed",
  "trigger": "automatic",
  "history_saved": true
}
```

状态为 `started/completed/skipped/failed`；`trigger` 为 `automatic/manual`。`history_saved` 仅在保存结果已知时出现；失败/跳过可附固定 `reason_code`，不附任意 exception 文本。persisted state 保存最近一次成功/跳过终态；失败若 Run 未提交 checkpoint，依靠 Run error/lifecycle 核实，不能承诺有持久失败 state。

Runtime 优先从 execution_info 取得 run_id，空时沿现有队列范式回退到可信 config metadata；子图 namespace 用官方事件 envelope，不以 payload 自报范围作为授权依据。操作 ID 在同一次步骤的 started/终态间一致；断流重放用 SDK 游标及 operation_id 去重，不加全局事件系统。

公开出口拒绝写入 `conversation_offloading`、`_summarization_event`、`_summarization_session_id`，并过滤私有 summary/path/session state。状态读取、history、Run JSON、checkpoints/updates、v2/v3 SSE 和子图事件都要测。不能简单把所有 `files` 全局删掉而破坏现有成果面；对新增公共状态只允许显式字段，归档访问继续受既有 Thread read/资源规则控制。

`custom` 使用已有通道，不新增物理 SSE。标准 Run 默认订阅补 `custom`；Protocol 的 SDK 消费须启用既有 custom 投影，分别验证 payload envelope，不能照搬 open-swe React 事件对象。

## 6. 前端交接与分期

由同事在当前 Vue Chat 会话中接入，DearAgent 复用同一个 ChatSession；具体入口、状态机与清单见 [frontend-handoff.md](frontend-handoff.md)。

1. P0 评审与基线：冻结预算来源、hash 版本、公开状态和失败语义。
2. P1 后端/Runtime 自动能力：容量目录、隐藏摘要、guard、恢复与脱敏。前端未接入也能验收该阶段，项目不因此整体 done。
3. P2 受控手动动作：全入口校验、无副作用维护 Run、幂等/取消/队列竞争验证。
4. P3 同事实现 UI：容量编辑、状态、手动动作、KeepAlive/断流补偿。
5. Final 联合验证：真实三服务、真实模型、PG/Worker 重启、失败注入、回滚与三个视口。

## 7. 风险、上线与后置

| 风险 | 处理与门禁 |
|---|---|
| 目录填写值与代理部署不符 | 管理员核对端点；实际 overflow fallback；禁止声明 token 估算严格保证不溢出 |
| 摘要遗失早期目标/约束 | 固定质量集，包含早期承诺、多次压缩、来源和媒体；用公开保留/摘要输入参数调优，不写假完整性承诺 |
| completed 早于 checkpoint，取消/模型失败 | checkpoint + Run 核实；只显示步骤状态；失败不覆盖最后可恢复摘要 |
| 手动消费队列/记忆/建议 | 空输入不等于无副作用；组合根/hook 守卫和后处理抑制，故障测试覆盖 |
| Context v5 与存量审批/定时定义 | 双端同步发版；隔离验证已有 v4 数据恢复，若需要仅对服务端历史快照做确定性升级，不开放双版本客户端旁路 |
| DeltaChannel 私有数据读取/子图归档 | 使用公开 state API 和 PG checkpointer，验证 restart；不自行解析 delta blob |
| 生产变更及回滚 | 新增 nullable 列先部署；服务端 feature flag `AGENT_CONTEXT_MANAGEMENT_ENABLED` 在目录与双端契约就绪后启用；停用新手动入口和 wrapper 时保留官方私有事件/StateBackend，验证旧图可继续聊天 |

回滚不删已有摘要/历史，不清 Run/checkpoint，数据库 downgrade 仅用于隔离演练。确认无活动维护 Run 后回退；回滚日志与既有审批/队列/定时任务的恢复证据是发布门禁。功能开关关闭时自动能力退回现有官方行为，不能称为“完全关闭摘要”。

后置项：独立摘要模型目录、用户开关自动压缩、实时 token 百分比、导出全文归档、新存储后端、所有 `create_agent` 教学图统一接入。出现明确需求与测量证据再规划。

本轮已同步 `docs/standards/sse-event.md`、Delegation Context hash 说明、API 网关规范和 Runtime 开发规范；这些补充仍保留原标准的 `draft` 状态，不使既有 SSE/JWT 未完成专项自动毕业。

### 本轮实施结果与部署顺序

后端与 Runtime 的 B01–B05/R01–R03、V01/V02A 已完成；新增能力默认关闭，前端 F01–F03 与浏览器/联合 Final 仍待交付。早期摘要丢失锚点已修正并用多次整理的真实回答重验，不以 Run success 代替质量检查。

1. Platform API 先执行 nullable migration `20261006_0006`；配置经核实的端点容量与既有 `max_tokens`，没有自动猜值 backfill。
2. API 与 Runtime API/Worker 同步升级 Context v5；先保持 `AGENT_CONTEXT_MANAGEMENT_ENABLED=0`。SSE/JWT 原专项仍 draft，本期批准不自动解除它们的旧门禁。
3. 前端按 capabilities 消费；灰度开启前验证所有受影响模型容量/输出预算，并确认没有混跑 v4/v5 Worker。
4. 回退先等待活动维护结束，再关闭开关并同步重启隔离栈；capabilities false、维护 409，普通对话继续使用官方摘要。保留 v5 契约/迁移列/历史；完整旧代码回退需另行配对评估，不在现役库 downgrade。

本轮没有提交、创建分支或部署现役服务。隔离证据与限制见 [verification.md](verification.md)；未完成清单只看 [tasks.md](tasks.md)。
