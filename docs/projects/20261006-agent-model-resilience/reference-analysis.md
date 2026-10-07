# 源码对照与建议评估

## 证据边界

本轮核对日期为 2026-10-06。参考的是用户提供的本地 open-swe 检出，项目为 [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe)，检出 HEAD 为 `ad417d64d91cc349d63d832c7b643637dc1774cf`；当前平台 HEAD 为 `424ff90e4f9a5c06c32c17f84a2cdaed73b65ef6`。文件行号是本轮阅读位置，后续改动以符号定位为准。

下文 open-swe 路径相对其仓库根目录；本平台路径相对当前仓库根目录。**源码核对不等于运行过 open-swe，也不等于已验证跨供应商兼容性。**

## open-swe 如何处理模型故障

### 1. 组合根建立主备模型

`agent/server.py:get_agent()` 的 1062 行附近读取 `LLM_FALLBACK_MODEL_ID`，未配置时调用 `agent/utils/model.py:fallback_model_id_for()`，为 Anthropic/OpenAI 主模型挑选跨供应商备模型。备模型通过原有模型初始化器构造，不在 middleware 内自行建立客户端。

可借鉴的是「组合根负责构造模型，middleware 只更换 `ModelRequest.model`」。其默认模型名称、Gateway、OAuth、team/profile/thread 配置及桌面模型策略不属于本平台通用能力，不迁入。

### 2. 策略包围单次 timeout

`agent/server.py` 的 1323~1337 行附近先装配 `*fallback_middleware`，最后装配 `ModelCallTimeoutMiddleware()`。源码注释明确 timeout 位于最内层，让超时向外传播到 fallback。

`agent/middleware/model_call_timeout.py:ModelCallTimeoutMiddleware.awrap_model_call()` 用 `asyncio.wait_for()` 包住整个 handler，默认 900 秒，并将超时转成 `ModelCallTimeoutError(TimeoutError)`。

本平台已有 `asyncio.timeout()` 实现，默认 600 秒，还验证 finite、正数和 bool 排除。无需照搬另一份 timeout。

### 3. 对 transient 错误交替尝试

`agent/middleware/model_fallback.py:_should_fallback()`，88 行附近：

- 识别 OpenAI/Anthropic 的连接、timeout、rate limit、internal server error，以及 transport error。
- 识别 LangChain `ModelError.is_retryable`。
- 实际状态码集合是 `{408, 409, 425, 429, 500, 502, 503, 504, 529}`，比同事提案中的摘录更宽。

`ModelFallbackMiddleware.awrap_model_call()`，174 行附近：

- 主模型和备模型交替：A、B、A、B、A、B。
- 默认 schedule 是 `(0, 5, 15, 30, 45)`，**总尝试数是 schedule 长度加一，即 6 次**。
- 第一次切换无等待；之后等待加入 `random.uniform(0, delay * 0.25)`，实际是 **0~25% 正向 jitter**，并不是注释所写的正负 25%。
- 非 transient 异常上抛；耗尽时默认返回故障 `AIMessage`，也可通过 `surface_outage_message=False` 上抛。
- 部分 model unavailable 错误另转为可见 `AIMessage`。

`agent/utils/model.py:make_model()` 默认还设置 SDK `max_retries=6`。因此不能用「middleware 6 次」推断实际只访问 provider 6 次；同事摘录没有包含这一层。

### 4. 用户通知与实际业务耦合

`MODEL_OUTAGE_MESSAGE` 明确提到 Slack/GitHub 上的可见结束和用户 retrigger。`model_errors.py:ModelErrorMiddleware` 另把模型错误分类写进线程 metadata，供运行完成通知消费。

可以借鉴「记录准确原因，用户能理解失败」。不迁入 Slack、GitHub、Linear 回复、issue/PR、workspace/team 属性、OpenSWE trace 基类、thread metadata 通知存储和业务文案。本平台已有原生 Run、HTTP 错误出口、SDK lifecycle、审计与 Langfuse。

### 5. 参考项目也有覆盖边界

`agent/server.py:_subagent_model_middleware()`，362 行附近，只安装 provider sanitization、model error 和 timeout。**父 Agent 的 fallback 并不自动包住独立子图。** `tests/middleware/test_model_fallback_middleware.py` 测了分类、A/B 交替、耗尽和错误透出，但没有证明浏览器已收到部分 token 后切换模型不会污染消息。

因此不能声称「照搬 middleware 就获得所有 Agent、所有流式场景的生产稳定性」。

## 当前项目实际能力与缺口

| 能力 | 当前代码证据 | 差距与本期处理 |
|---|---|---|
| 单次模型 timeout | `apps/runtime-service/src/runtime_service/middlewares/model_call_timeout.py:ModelCallTimeoutMiddleware` | 已有，默认 600 秒，取消与环境覆盖已测试；补总预算组合，不重写 |
| 模型实例与参数解析 | `apps/runtime-service/src/runtime_service/runtime/modeling.py:build_model()` | 已支持 OpenAI compatible、DeepSeek、Anthropic，且支持 `max_retries` 参数；正式组合根通常未明确关闭 SDK 内部重试 |
| 官方 retry/fallback | `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py:get_agent()`，186~250 行 | 只在 `_runtime_model` 测试注入下启用；retry 仅覆盖 `ConnectionError`，不是正式主备配置 |
| 正式 DearFlow 主/子推理 | `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py:get_agent()/middleware()`，198、280、326、362 行 | 主模型、researcher 都有 timeout 和限额，没有正式模型 retry/fallback |
| Deep Agents 子图 | 锁定依赖 `deepagents/graph.py:create_deep_agent()`；`services/demo/showcase_demo/subagents.py:build_subagents()`；`services/dearflow_agent/subagents/researcher.py:researcher()` | 未显式声明时自动加入 general-purpose，且不继承全部用户 middleware；Showcase 显式覆盖，DearFlow researcher 的实际 name 也是 general-purpose，已经只读覆盖，不得重复添加同名全工具子图 |
| Showcase / Workflow 模型调用 | `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py:get_agent()`；`services/demo/workflow_demo/agent.py:model_agent_for()` | 同样使用单模型；Workflow 在节点中构造 Agent，不能只改 DearFlow |
| 重建模型与工具校验 | `apps/runtime-service/src/runtime_service/middlewares/runtime_config.py:RuntimeConfigMiddleware.awrap_model_call()`，401 行 | 会覆盖 request.model；它必须位于可靠性策略外层，否则每次 fallback 会被重置回主模型 |
| 平台/项目模型与密钥 | `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py:resolve_model_connection()`；`model_connection.py:create_model_reference()` | 已有加密凭据、项目检查、actor/Thread/Agent 复核；只有一个模型连接，尚无主备策略快照 |
| 项目模型允许名单 | `apps/platform-api/src/platform_api/modules/runtime_policies/application/service.py:build_delegation_policy()` | 读取 `list_models()` 未带 project_id；不得把该名单单独当成备模型可用证明，见下方授权差异 |
| Agent 默认配置 | `apps/platform-api/src/platform_api/modules/agents/application/service.py:_normalize_agent_context()`；`infra/sqlalchemy/models.py:AgentRecord.context` | 已有 JSON，但公开 Context 只有模型参数/执行模式；新增管理配置不能直接混入 Run Context |
| 所有 Run 入口 | `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py:launch_runtime_run()` | 已统一幂等提交/审批与 opaque ref 组装；需要在这里固定可靠性快照 |
| 定时任务执行 | `apps/platform-api/src/platform_api/modules/scheduled_tasks/service.py:authorize_execution()`；`apps/runtime-service/src/runtime_service/runtime/scheduled.py:scheduled_execution()` | 执行前重验权并重新发模型 ref；备模型必须进入这条路径，不能只覆盖浏览器 Run |
| 前端管理/聊天 | `apps/platform-web/src/modules/agents/pages/AgentEditorPage.vue`；`src/services/agents/agents.service.ts`；`src/modules/chat/composables/useChatSession.ts` | 已有模型配置、失败态和 SDK controller；缺策略字段与模型故障语义联调，不需要新页面或第二个状态机 |
| 摘要与上下文压缩 | 锁定依赖 `deepagents/graph.py:create_deep_agent()`、`deepagents/middleware/summarization.py:awrap_model_call()` | 根/子图自动加入摘要；摘要直接调用模型，LangChain helper 另有 with_retry；ContextOverflowError 还触发压缩后重新生成，不能用普通 middleware 次数代表整节点请求数 |
| 其他辅助模型调用 | `apps/runtime-service/src/runtime_service/services/suggestions.py`、`services/dearflow_agent/middleware/memory.py`、`utils/title_summarizer.py` | suggestions/标题有独立入口，记忆提取直接复用主模型；不都经过 Agent model middleware，需隔离 SDK 重试设置并回归 |

### Deep Agents 的真实构图边界

Deep Agents `0.7.8` 的 `create_deep_agent()` 会为未显式提供的 `general-purpose` 建图。其继承规则只复制同名覆盖默认槽位的 middleware，不会自动继承新增的可靠性、RuntimeConfig 或 timeout。Showcase 的 `build_subagents()` 已显式覆盖默认图。2026-10-06 实施复核发现原规划误把 DearFlow 的函数名 researcher 当成子图 name；其返回的 name 实际是 general-purpose，已覆盖默认槽位，工具只有读文件和研究工具。实际只有一个只读研究子图，直接在现有 child middleware 装配策略，不增加或禁用任何子图。

根图和声明式子图还默认安装 `create_summarization_middleware(model, backend)`。摘要通过 LangChain helper 的 `_summary_model.ainvoke()` 独立请求，helper 默认另有最多三次的 `with_retry()`；SDK 重试可能继续叠加。`awrap_model_call()` 捕获 `ContextOverflowError` 后会压缩历史并再次调用下游 handler。这是原生上下文恢复，不能在分类阶段提前转换异常而使它失效，也不能把压缩后的新请求与普通 transient 重试混为一谈。

DearFlow 的 `MemoryContextMiddleware(model)` 确实直接用同一个主模型做结构化提取；把该实例 SDK retry 设为 0 会同时改变记忆提取和默认摘要的行为。建议接入路径另建一个共用已兑换主连接的辅助实例，保持其原有重试设置，用公开摘要 factory 同名覆盖默认摘要并供记忆提取复用。它不新增 credential 兑换或自动改用备模型。摘要失败仍可能使长对话失败，本期不能宣称辅助推理具备受管主备保障；R03 必须确认此范围。

`services/dearflow_agent/tools/skills.py:build_skill_tools(workspace, model)` 虽接收 model 参数，当前函数体没有 invoke/ainvoke，也没有模型客户端调用。它是存储/静态检查工具，不能列为缺少模型 fallback 的推理路径；保留共享构图回归即可。

### 必须提交人工评审的授权差异

`build_delegation_policy()` 的 82~97 行读取所有 Catalog 模型；仓储 `list_models()` 只有收到 `project_id` 才过滤其他项目私有模型。与此同时，网关 `_assert_runtime_options_allowed()` 使用按项目过滤的 Catalog，且 `resolve_model_connection()` 另核对私有模型所属项目。

这说明 **JWT 允许名单与现有网关/凭据兑换的作用域口径不一致**，但不等于已经证明能取得其他项目密钥。本轮只标记事实，不自行修改安全行为。建议 R01 评审批准统一到现有项目可见 Catalog 与模型策略，再实施和补跨项目拒绝测试；若不批准，必须另定明确授权方案，不能仅凭旧 JWT 名单启用 fallback。

### Worker 重试不是模型重试

已安装 `graphharbor-runtime==0.13.0.post41` 的 `langgraph_runtime_pg/production_worker.py:_is_infrastructure_error()` 会把 `TimeoutError/ConnectionError/OSError` 归为 infrastructure error，可能重新调度整 Run；Worker 的终态 payload 使用异常 type/message。

模型策略耗尽应转换为只含稳定代码的 `RuntimeResolutionError`（现有基类为 `ValueError`），并抑制原始异常文本串入终态。**不能原样抛 timeout，让模型重试预算外再套整 Run 重试。** 该结论仍需未来真实 Worker 故障注入验收；本轮仅核对源码。

## 对同事提案的逐项结论

| 提案 | 结论 | 本平台建议 |
|---|---|---|
| 补模型 fallback | 采纳目标 | 从项目可用 Catalog 选择一个明确授权的备模型，复用连接兑换 |
| 新建 `model_fallback.py` 照搬实现 | 调整 | 官方能力已安装；新增小型 `model_resilience.py` 仅承担分类保护、预算、流式边界和平台错误归一化 |
| fallback_model 可选 | 采纳 | 没有备模型时只对同一个模型重试；不暗中选择外部供应商 |
| provider transient 分类 | 采纳并收窄 | 识别 SDK/LangChain 类型；参数、身份、配额耗尽和程序错误不自动切换；409/425 不作为无条件通用重试码 |
| backoff jitter | 采纳 | 复用官方 retry 的指数退避与正负 25% jitter；官方 Retry 外包 Fallback 时首次 A/B 切换立即执行，后续轮次退避，不能写成每次物理请求都等待 |
| 全局 `AGENT_FALLBACK_MODEL_ID` | 不采用为正式控制面配置 | 全局值不能表达不同项目 BYOK、数据出域和可用模型权限；生产从受管配置取得 |
| 放在 timeout 之后 | 不采用 | 列表先可靠性策略、后单次 timeout；RuntimeConfig 还要在两者外层 |
| 全失败返回 AIMessage，避免 error | 不采用 | 失败必须体现在 Run/定时任务/审计中；可读提示放在既有失败态，不充当模型回答 |
| SDK 重试保持默认 | 提案遗漏 | 启用受管策略的模型显式 `max_retries=0`，只保留一层受预算控制的模型重试 |
| 流式/子 Agent/摘要覆盖 | 提案遗漏 | 单独验收 partial、实际 general-purpose、摘要 ContextOverflow 恢复与 SDK 设置隔离；明确受管次数不是全节点/全仓推理次数 |

## 依赖与官方资料

当前 Runtime lock 和实际借用的已安装环境一致：LangChain `1.3.17`、langchain-core `1.6.0`、Deep Agents `0.7.8`、OpenAI SDK `2.46.0`、Anthropic SDK `0.125.0`、httpx `0.28.1`、GraphHarbor `0.13.0.post41`。本期不以升级核心依赖为前提，也不引入参考仓库的 `httpx2`。

已通过 `langchain-docs` 和 `langchain-reference` MCP 核对：

- [Model retry](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-retry)：`retry_on` 可传 callable，支持指数退避、jitter；必须设置 `on_failure="error"`。
- [ModelRetryMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_retry/ModelRetryMiddleware)：未知异常默认也可能重试，本平台必须提供显式分类器。
- [ModelFallbackMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_fallback/ModelFallbackMiddleware)：候选依次尝试；当前 API 没有 `retry_on`，不能直接裸用来保证只切换 transient 错误。
- [Deep Agents fault tolerance](https://docs.langchain.com/oss/python/deepagents/fault-tolerance)：模型故障、工具故障和程序错误采用不同策略。
- [create_summarization_middleware](https://reference.langchain.com/python/deepagents/middleware/summarization/create_summarization_middleware)：公开 factory 保留历史 offload、模型阈值与 ContextOverflow 恢复；替换时不访问私有 helper 字段。

实际安装源码另确认：官方 fallback 会处理跨模型请求中的 Anthropic cache markers，但不保证所有多模态和 reasoning 历史兼容；官方 factory 的第一个 wrap handler 包住后续 handler。在线资料不替代锁定版本的组合测试。
