# 源码对照与方案辨析

## 目标

把 open-swe 的通用工程思想和业务耦合拆开，基于当前仓库代码确认真正缺口，避免把“能统计 Token”误写成“能计费”。这篇只做事实与决策记录，不改代码。

## 证据边界

- 本项目源码基线：`bf47991b`，读取时工作树干净。
- 参考仓库是用户提供的本机 `research/open-swe`，HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`；usage middleware、cost、completion、dashboard、LangSmith helper 和 UI 文件含已暂存的本地新增/修改。以下结论对应这份工作区，并不声称是上游该提交的正式行为。
- 当前工作树无独立虚拟环境，本轮使用同仓主检出的 Runtime venv，测试的 `pythonpath` 指向本工作树 `src/tests`。实测依赖：LangChain Core 1.6.0、OpenAI 1.6.0、Anthropic 1.6.1、DeepSeek 1.1.0、LangGraph 1.2.11、DeepAgents 0.7.8、GraphHarbor 0.13.0.post41；实施时按实际锁定环境再核对，不更新依赖。
- 官方核对已查询 `langchain-docs` 和 `langchain-reference` MCP：[Token usage](https://docs.langchain.com/oss/python/langchain/models#token-usage)、[UsageMetadata](https://reference.langchain.com/python/langchain-core/langchain_core/messages/ai/UsageMetadata)、[UsageMetadataCallbackHandler](https://reference.langchain.com/python/langchain-core/langchain_core/callbacks/usage/UsageMetadataCallbackHandler)、[成本跟踪](https://docs.langchain.com/langsmith/cost-tracking)。

## open-swe 的做法

| open-swe 位置 | 设计 | 可借鉴部分 | 不迁移的业务耦合 |
|---|---|---|---|
| `agent/middleware/record_run_usage.py` | `awrap_model_call` 给 `AIMessage` 写 invocation 标识，`aafter_agent` 在 Run 完成时触发收尾 | Middleware 是 Agent 的统一接入点；Run 完成时做幂等 finalize | `open_swe_invocation_id` 字段名、Agent Server 专用 `RunConfig`、Slack/GitHub 身份 |
| `agent/utils/run_usage.py` | 从 `AIMessage.usage_metadata` 聚合 input/output/total，支持跨 HumanMessage 的同一 invocation | 标准化 provider 字段、模型集合、缓存明细和缺失值语义 | `total_tokens - cache_read` 不能作为所有供应商的计费公式 |
| `agent/agent_cost.py` | 完成记录后通过 LangGraph scheduler 延迟查询 LangSmith cost，有限重试 | 外部 cost 最终一致、有限重试、成本不可用不阻断主 Run | LangSmith 私有 trace、Open SWE store namespace、业务专属 scheduler |
| `agent/dashboard/agent_usage.py` | 按 invocation 存 usage/cost，再按用户/周期做 leaderboard | invocation 幂等写入、完成态与 cost refresh 分离 | GitHub login、PR、review、leaderboard 业务和内存锁实现 |
| `agent/completion.py::_finalize_agent_usage_telemetry` | terminal webhook 再执行 finalize，包括异常/取消后的收尾；重复调用有 finished 标记保护 | `after_agent` 不能覆盖所有终态，必须存在执行外层收尾 | 不复制 Open SWE webhook server、prepare_run_id 和 Slack 消息更新 |
| `agent/utils/langsmith.py` | 用 invocation metadata 找 root trace，再以 trace filter 查 Thread stats | 关联 ID、结束时间校验、成本新鲜度校验 | LangSmith API、项目名解析、供应商 SaaS 权限 |
| `ui/src/routes/usage.tsx` | 独立 Usage 页面按周期显示 Token/Cost | 前端需要明确 loading/empty/error 和周期聚合 | 不复制 UI、路由、英文文案和 PR 指标 |

open-swe 的核心链路是：`server 创建 invocation 记录 -> model response 打 tag -> after_agent 或 terminal webhook 收尾 -> Store usage 记录 -> scheduler 最多 5 次延迟查询 LangSmith -> dashboard`。`run_usage.py` 仅聚合当前主 Agent 的 messages，不能据此证明子 Agent 或隐藏摘要的 Token 已包含；LangSmith trace cost 的统计范围又可能更广。本项目必须让 Token 与成本使用同一批模型调用。

其他限制：Store 的读改写依赖进程内 `asyncio.Lock`，多 Worker 不受同一锁保护；缺 usage 可能留下初始 0；leaderboard 需要分页扫描 Store 再聚合。借鉴幂等语义，但本项目用数据库唯一键和索引查询解决这些具体问题。

## 当前项目已经具备的能力

### Runtime

- [runtime/modeling.py](../../../apps/runtime-service/src/runtime_service/runtime/modeling.py) 的 `build_model()` 对 DeepSeek/OpenAI/Anthropic 显式构造分支已经开启 `stream_usage=True`；通用 `init_chat_model` 分支仍需按 provider 验证，不能要求不支持的供应商开关。
- [observability/langfuse.py](../../../apps/runtime-service/src/runtime_service/observability/langfuse.py) 的 `_RuntimeDiagnosticsCallback.on_llm_end()` 只读 `LLMResult.llm_output.token_usage.total_tokens` 并写进进程级 `_metrics`。流式/Anthropic 往往只在 generation 的 `AIMessage.usage_metadata` 报告，现有 counter 有漏记路径。
- `with_langfuse_tracing()` 被 Showcase、DearFlow、Reference、backend/failure/mcp/deep-agent/workflow 图入口复用；[test_graph_tracing.py](../../../apps/runtime-service/tests/observability/test_graph_tracing.py) 已验证模型、工具及子图 callback 传播，但未验证 usage ledger。
- [observability/diagnostics.py](../../../apps/runtime-service/src/runtime_service/observability/diagnostics.py) 已有 tenant/project/thread/run 白名单元数据；[Runtime 自有迁移](../../../apps/runtime-service/src/runtime_service/db/migrations/versions/0001_application.py)与 GraphHarbor 引擎迁移分开。
- [memory.py](../../../apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py) 在 `aafter_agent()` 内直接 await 提取模型并保存过 usage，调用使用 `callbacks=[]` 和隐藏标签；没有独立 `_extract` 或后台任务。[vision Tool](../../../apps/runtime-service/src/runtime_service/tools/images.py)也显式清空 callbacks。实际继承是否仍发生需要组合测试，不能从标签推断用量已覆盖。
- 锁定 GraphHarbor `production_worker.py` 在模型工厂之前，用数据库中的 native Run ID 覆盖 `metadata.run_id/thread_id`。这个 ID 与 `on_llm_end(run_id=...)` 的模型 callback UUID 不同，也与 `request_id/platform_trace_id` 不同；成本不得按 HTTP 请求数或最后一条 HumanMessage 归属。

### Platform API

- [Runtime 模型目录](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/infra/sqlalchemy/models.py)已有 catalog UUID、Provider、协议、项目范围和加密凭据；[RuntimeCatalogService.resolve_model_connection()](../../../apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py)经短期内部引用返回模型连接。
- [Runtime Gateway](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py)已有 Thread/Run 级授权、`diagnostics-read` Delegation；[diagnostics DTO](../../../apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py)提供只读白名单投影。
- Platform API 迁移使用 `migrations/versions/`，新增字段可以采用可回滚前向兼容的 nullable migration。

### Platform Web

- `src/modules/chat/components/trajectory/TrajectoryView.vue` 已有 `RunDiagnostics` 模式和 Run 选择入口。
- `src/services/threads/diagnostics.service.ts`、`src/modules/chat/composables/useRunDiagnostics.ts` 已有带 AbortSignal、epoch 防竞态和安全 DTO 校验的读取模式。
- [trajectory-adapter.ts](../../../apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts) 已读部分 usage，但 `asObject()` 返回 `{}`，用 `||` 会挡住 metadata fallback；reasoning 标准嵌套也未完整识别。tool-call-only AIMessage 在轨迹里未必形成 assistant record，不能按显示记录统计全成本。
- [ChatSession.vue](../../../apps/platform-web/src/modules/chat/components/ChatSession.vue) 按 displayedMessages 汇总，读平铺 cache 字段，存在按字符数估算及 `46800/197` fallback，还将 cache 加到 input 上，可能重复。只修本期 Token/Cost 相关路径，耗时模拟问题另行记录，不顺带重构。
- `src/services/runtime/runtime.service.ts` 和模型编辑组件是价格字段的自然接入点，不需要新建页面壳或新 UI 库。

## 当前差距

| 差距 | 代码证据 | 影响 |
|---|---|---|
| 只有进程内 Token counter | `observability/langfuse.py::_metrics` | 进程重启、并发 Worker、历史 Run 后无法查询 |
| 没有每次模型调用的去重 ID和持久化 | callback 只累计 `total_tokens` | 重试/父子图/流式回调容易重复或丢失 |
| input/output/cache/reasoning 未形成统一事实 | UI 多处自行兼容字段，Runtime 只有 total | 无法可靠比较模型和计算成本 |
| 没有模型价格快照 | Runtime Catalog 没有 rate 字段 | Langfuse 未配置价格时无法得到成本，模型改价会改变历史解释 |
| 没有 Run/Thread 聚合 API | 现有 diagnostics 只读错误、阶段和 trace | 前端只能从消息猜，无法跨 invocation 汇总 |
| 内部模型调用不统一 | suggestions/title/vision/memory 有直接 `.ainvoke()` | 主图之外的可计费调用可能漏记，或被误计入主 Run |
| 单纯完成钩子不可靠 | after_agent 可能遇异常跳过，消息可能经压缩、回滚或分叉 | 已发生的物理模型消耗不能随 checkpoint 消失 |
| 前端存在伪造 fallback | `ChatSession.vue` 使用 `46800/197` 等 fallback | 缺数据时把估算伪装成真实用量，生产账务风险 |

## 对同事方案的辩证结论

| 建议 | 结论 | 具体调整 |
|---|---|---|
| 新增 `record_run_usage.py` Middleware | **采纳装配思想，优先已有 callback** | 官方已有 `UsageMetadataCallbackHandler` 和 `add_usage`；本项目扩展关联/持久化，用图级 callback 覆盖任意 StateGraph。只有确需模型重写的能力才加 Middleware，不同时挂两套计数器 |
| `awrap_model_call` 后给 AIMessage 打 invocation_id | **不作为唯一来源** | trusted `config.metadata.run_id` + callback `run_id` 更可靠；不写 `open_swe_*` 私有字段，避免内部标识随消息进入 Web。必要的内部关联字段由持久化记录保存 |
| `aafter_agent` 遍历 state.messages | **不作为主采集或历史补账** | 失败、取消、摘要、fork/rollback、子图均会破坏完整消息假设。图 root callback 只记录采集生命周期；Run 终态读 GraphHarbor。没有可信调用关联的旧消息不用于成本 |
| `input + output - cache_read` | **拒绝通用化** | 缓存读取通常按折扣价格收费；原始 input、cache_read、cache_creation 分开保存，按模型价格快照分别计算 |
| 直接持久化到 Platform API 计费表 | **本期不采纳** | Runtime 才能看到真实模型回调，执行事实归 Runtime DB；Platform API 管价格、授权和投影，避免第二套执行账 |
| LangSmith 延迟 cost enrichment | **价格快照优先；借鉴 unknown/有限重试语义** | Runtime 用可信目录价格算 `estimated`，Langfuse 是观测副本。首期不增加 scheduler、队列或同步 SaaS 查询；外部 cost 对账单独评审 |

## 方案设计

已选：Runtime callback + Runtime DB usage calls + Platform model pricing + Platform authorized projection。

建议供评审：价格归属现有 catalog 记录。平台公共模型价格由当前模型管理权限维护；项目 BYOK 记录拥有自己的价格，项目不能覆盖公共记录。首期不增加“同一公共模型按项目另定价”的层级。

建议供评审：有可信 native Run 的 vision/memory 计入 `auxiliary`，DeepAgents 摘要计入同 Run 的 `summarization`；没有 native Run 的 HTTP suggestions/title 和非 LLM 外部费用明确排除，并在 API `excluded_operations` 说明。标题 endpoint 当前没有向调用层传递经验证的 principal，不能仅凭 URL 的 Thread 字符串关联成本；这项安全现状保持显式标记，若未来纳入，先评审其授权契约。本期不扩大鉴权改造。

最小可靠性边界：数据库唯一键保证已观测调用不会重复入库；供应商处理完成与本地持久化之间没有跨系统事务，SIGKILL、SDK 隐藏重试或未报告 usage 的消费只能标记未知，不能保证完整账单或“恰好一次扣费”。

## 任务拆分

| 状态 | 任务 | 结果 |
|---|---|---|
| [x] | S01 两仓源码对照 | 包含 middleware、completion、store、scheduler、UI |
| [x] | S02 官方 MCP 与本机依赖核对 | 确认标准字段、callback 复用和缓存 TTL |
| [x] | S03 Runtime 基线 | `test_langfuse.py`、`test_graph_tracing.py`、`test_modeling.py` 共 45 passed，5 条既有 SWIG 弃用警告 |
| [x] | S04 三层职责与交接 | 三层职责、旁路范围和前端交接已落文档 |

## 验证要求与记录

- [x] 只读当前 Runtime、Platform API、Platform Web 入口与 lessons；结果记录在本篇和 05。
- [x] 对照 open-swe 工作树 HEAD 和未提交状态；结论不视为干净上游事实。
- [x] 2026-10-07 用户批准 02/03 的数据归属、价格口径、usage-read、保留边界，原话和范围见 [README](README.md#实施阶段与评审)。

基线命令和限制见 [05 规划阶段验证](05-verification-rollout.md#规划阶段验证记录历史)。以上不是新能力实现或成本准确性的测试结果。

## 状态

源码分析与规划已完成，治理方案已获用户批准。本文保留实施前源码基线，当前实现与验证以 02/03/05 为准。
