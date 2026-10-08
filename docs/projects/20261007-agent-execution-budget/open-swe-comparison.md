# open-swe 源码对照与同事方案辨析

> 本文保留规划时的取证快照。后续用户已批准 G0，Runtime/API 全部非前端项已实现并验证，当前状态见 tasks.md/verification.md；下文“未开始”等仅指当时基线。

## 取证边界

2026-10-07 只读核对用户指定的 open-swe 工作目录。`O/` 表示该目录，`R/` 表示 `apps/runtime-service/`，`A/` 表示 `apps/platform-api/`，`W/` 表示 `apps/platform-web/`。

- 本项目初始工作树干净，HEAD `bf47991b`。
- open-swe HEAD `ad417d64d91cc349d63d832c7b643637dc1774cf`；本次读取的 `server.py`、两个 middleware 和收尾 prompt 存在本地改动，HEAD 不能代表所读实现。没有修改、启动或测试参考项目。
- `O/agent/middleware/notify_step_limit.py` SHA256：`45ffac71992f9ca9ae737d894645bc207ac68f455b14491fbc247ed93b394460`。
- `O/agent/middleware/timeout_wrapup.py` SHA256：`ef9e4d6e7d0362d512dc5774e3f2144f57b2bc8644c142ac2470c3ef567e26e1`。
- `O/agent/resources/prompts/timeout-wrapup.md` SHA256：`f1a2b1922a63b9bda8fce46b3007855cd9c999855a09902eec9e3174e7cfb61e`。
- 本项目锁定且测试解释器实装：LangChain `1.3.17`、LangGraph `1.2.11`、Deep Agents `0.7.8`、GraphHarbor/Runtime `0.13.0.post41`、Python SDK `0.4.3`。
- Web 声明版本：`@langchain/vue==1.0.35`、`@langchain/langgraph-sdk==1.10.2`；接入以这些版本的真实类型和组合测试为准。

## open-swe 实际怎样做

### 1. 模型预算先终止，通知随后执行

`O/agent/server.py:get_agent()` 装配 `ModelCallLimitMiddleware(run_limit=MODEL_CALL_RECURSION_LIMIT, exit_behavior="end")`，随后装配 `TimeoutWrapupMiddleware()`、`notify_step_limit_reached`。

官方 LangChain 的 `end` 分支向 messages 追加人工 `AIMessage` 并返回 `jump_to="end"`。`notify_step_limit_reached.aafter_agent()` 从最后一条消息提取文本，匹配 `Model call limits exceeded`，查找活跃 Slack thread 后回复警告。

这是一条特定渠道的结束通知，名称虽然叫 step limit，来源实际是模型调用预算。它没有观察 LangGraph 的 superstep 剩余量，也没有在接近模型调用限额时发预警。最后消息被别的 middleware 改写、文本变更或恰好引用该短语时，匹配会失效或误判。

无 Slack 配置就跳过；`post_slack_thread_reply()` 的发送异常被捕获并记日志。但前面的 `RunConfig.from_runtime()`、`get_active_slack_thread()` 位于 try 之外，其异常仍可能传播，不能据此认为整条通知路径都不会影响 Agent 结果。可以借鉴发送失败隔离的目标；本平台应保护完整通知出口，保留取消/中断控制流，不迁入 Slack 查找、RunConfig 来源字段或业务文案。

### 2. 收尾 prompt 是软能力

`O/agent/middleware/timeout_wrapup.py:TimeoutWrapupMiddleware` 使用 `time.monotonic()`，第一次模型请求时才启动计时。软阈值默认 45 分钟，可通过参考项目专属环境变量修改。

达到阈值后，`awrap_model_call()` 在 system message 追加收尾指令，再继续调用原 handler。`_content_with_instruction()` 保留 list 型内容块并避免重复追加；测试覆盖了惰性起点和结构化内容保留。

指令要求报告现状、不要开始新调查、结束当前回合。实现没有定时取消、没有阻止工具继续运行，也没有权威 Worker deadline；卡住的单次模型调用或工具不经过下一次 wrapper，就不会得到收尾提示。构图前耗时与人工等待也不能从这个计时器推导。

可以借鉴单调时钟、request override、内容块保留与提示词幂等。不能直接照搬 45 分钟阈值并称为本平台 Run timeout 管理。

### 3. 前后端的原始责任边界

本次查看的通知路径是 Agent middleware 直接调用 Slack，没有浏览器专用步骤告警事件或状态机。参考 dashboard 对 Run 错误/timeout 的展示不能证明它实现了这项前端预警。

本平台的入口是 Vue Chat + Platform 网关。因此应保留“执行层知道限制原因，表现层通知用户”的设计，渠道改为现有 LangGraph custom 事件和安全 JSON/SSE 错误；不能把 Slack webhook 换成浏览器回调就当作完成。

## 当前项目的事实与差距

| 能力 | 当前代码证据 | 实际缺口 |
| --- | --- | --- |
| DearFlow 模型预算 | `R/src/runtime_service/services/dearflow_agent/agent.py:middleware()`；主图 run/thread，子图分别限额，`exit_behavior="error"` | 缺预警和结构化触限通知；不能通过 after_agent 捕获 |
| Showcase 模型预算 | `R/src/runtime_service/services/demo/showcase_demo/agent.py:middleware()`；默认 run 50/thread 500，主/子图显式装配 | 与 DearFlow 同类缺口 |
| Reference 模型预算 | `R/src/runtime_service/services/reference_agent/agent.py:_build_agent()`；run 10，`end` | 人工英文消息能显示，但没有专用语义、阶段预警或通知去重 |
| Workflow 模型预算 | `R/src/runtime_service/services/demo/workflow_demo/agent.py:model_agent_for()`；run 10，`end` | 只作用于内层 create_agent，外层 StateGraph 需另接图预算 |
| 工具预算 | DearFlow/Showcase/Reference 已用官方 `ToolCallLimitMiddleware`；DearFlow 另有限制 task 的预算 | 首期只补停止原因展示，不重写工具计数/限制策略 |
| 图硬限制 | `A/.../application/service.py:_execution_config()`；`R/.../dearflow_agent/agent.py` 与 Showcase 绑定 config | API 允许整数 1-1000，代码默认 1000；无近限图预警 |
| 模型单次超时 | `R/src/runtime_service/middlewares/model_call_timeout.py:ModelCallTimeoutMiddleware.awrap_model_call()` | 已有 600 秒默认边界，不能代替整次 Run timeout |
| 整次 Run 硬超时 | 实装 `langgraph_runtime_pg/production_worker.py:_run_timeout_seconds()`、`ProductionWorker.run_once()` | 已有，配置缺省时关闭；缺与软收尾的明确口径 |
| 流式通知运输 | GraphHarbor `graph_executor.py:invoke_graph()` 使用 v3 `CustomTransformer`；Worker `_publish_events()` 保存事件 | Runtime 尚无本项生产者；默认普通流 modes 不含 custom；Web 尚无本项消费者 |
| 历史Run原因 | GraphHarbor `models.py:RunRow`、`database.py:_RUN_KEYS/run_to_dict()`没有error字段；Thread有最新error槽位 | 只能从本Run事件或人工消息标记取证；事件过期后不能用当前Thread.error推断旧Run原因 |
| 错误安全出口 | `A/src/platform_api/adapters/langgraph/sdk_client.py:project_execution_error()` | 默认安全泛化；模型/工具限额类名不在保留清单，具体触限原因会丢失 |
| 前端状态 | `W/.../composables/useSessionConnection.ts` 官方 `useStream()`；`ChatAgentStatusBar.vue` 和 SDK Run | 已有运行/中断/错误展示；缺限额专属提示与后续动作边界 |

DearFlow 实际阈值由 `max(mode.*_limit, env_default)` 求主图限额，子图采用 `min(24/48, env_default)`。因此环境变量目前不是一个全局 hard cap。这个事实需要说明，但本期不改模式阈值、阈值优先级或线程累计策略。

Deep Agents 将官方预算计数等 `PrivateStateAttr` 从父子输入/输出中剔除。父子图的独立计数不是全树共享配额，不得用父图 remaining 显示整个 Agent 的总成本。

## 同事方案逐项辨析

| 建议 | 结论 | 理由与替代落点 |
| --- | --- | --- |
| 到步骤限制时应通知用户 | 采纳目标 | 必须区分图 superstep、模型调用和工具调用；用稳定 code 说明来源 |
| 用 `aafter_agent` 检查末条标记 | 不作为通用实现 | 只适合官方 `end` 人工消息；实际 `error` 与 GraphRecursionError 不走 after_agent |
| 匹配 `Model call limits exceeded` | 不采纳为事实判断 | 来源是普通文本，不能证明真的限额；复用官方计数、返回值和异常类型 |
| 通过 SSE writer 推提示 | 采纳运输方式 | 要补 custom 订阅、namespace/Run 关联、网关安全投影、重放去重和无订阅降级 |
| 快到限制时告警 | 采纳 | 模型预算读取官方 counters，图预算读取 `RemainingSteps`；不能用消息数或 tool call 数估算 graph step |
| 配合 TimeoutWrapupMiddleware | 有边界采纳 | 独立软时间提示，保留既有单次模型 timeout 和 Worker hard timeout；不开第二套硬超时 |
| 所有 Agent 可适配 | 采纳 | create_agent/create_deep_agent 用共享 middleware；自定义 StateGraph 用 managed state + 节点检查函数，无强制框架改造 |

## 已核实的边界与冲突

### after_agent 不是 finally

本轮使用锁定环境和 fake model 做离线探针：

| 路径 | 结果 | after_agent 是否执行 |
| --- | --- | --- |
| model run limit=1，`error`，recursion=100 | `ModelCallLimitExceededError` | 否 |
| model run limit=1，`end`，recursion=100 | 返回官方人工 AIMessage | 是 |
| recursion=1，`end` | `GraphRecursionError` | 否 |

验证方式和基线结果见 [verification.md](verification.md)。这些结果只证明生命周期，不声称真实 Worker 通知已经实现。

### managed state 必须按锁定版本适配

本轮附加构图探针发现：裸 `remaining_steps: RemainingSteps` 进入create_agent生成的InputSchema会报“Managed channels are not permitted”；`Annotated[RemainingSteps, PrivateStateAttr]`虽然构图成功，manager不在末尾导致读值为None。正确已验证写法是 `Annotated[int, PrivateStateAttr, RemainingStepsManager]`，实际recursion=20时before_model读到19且该键不进入公开输出。需在T01固化schema和数值断言，不能只断言“构图成功”。

### 文档与代码需由人工裁决

1. `A/docs/standards/runtime-gateway-interface-standard.md` 写 recursion 默认 25，API/Web 与主要模板代码实际默认 1000。建议按当前代码更新文档；规划不改生效契约。
2. `docs/guides/env-matrix.md` 写 Run timeout 默认 300/配置 900；Worker 无配置时实际关闭，`R/.env.example` 写 1800。示例不是生产有效配置；本轮没有读取私有 `.env`，不能声称生产已开启。
3. API 两项基线测试涉及三个失败断言：现有泛化码 `runtime_execution_failed` 与断言 `runtime.execution_failed` 不一致；Protocol 字符串错误不带 code；`tasks.error` 的异常原文未被该出口清洗。后者是已复现安全缺口，实施需先按 G0 批准的出口范围处理。

安全/契约冲突已标记，相关业务实现尚未开始；不能自行批准修改 public error 形状、恢复权限或执行策略。

## 官方依据

先查询了 LangChain Docs 和 API Reference MCP，再核对本机锁定包源码。

- [ModelCallLimitMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_call_limit/ModelCallLimitMiddleware)：官方 run/thread 计数、`end`/`error` 及专门异常。
- [内置模型调用限制](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)：run 是 invocation 范围，thread 需要 checkpoint。
- [LangGraph recursion limit](https://docs.langchain.com/oss/python/langgraph/graph-api#recursion-limit)：superstep 预算，config 顶层键。
- [使用 RemainingSteps](https://docs.langchain.com/oss/python/langgraph/use-graph-api#impose-a-recursion-limit)与[API 类型](https://reference.langchain.com/python/langgraph/managed/is_last_step/RemainingSteps)：managed value，不是持久化消息计数。
- [Stream writer](https://docs.langchain.com/oss/python/langchain/tools#stream-writer)及[自定义流 transformer](https://docs.langchain.com/oss/python/langchain/middleware/custom#custom-stream-transformers)：复用现有流能力，不创建浏览器直连 Runtime。
