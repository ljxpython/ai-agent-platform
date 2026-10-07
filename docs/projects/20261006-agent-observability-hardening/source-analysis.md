# open-swe 源码对照与方案辨析

## 核查口径

本次读取用户指定的本地 open-swe，下文 `O/` 表示该参考仓库根，`R/` 表示 `apps/runtime-service/src/runtime_service/`，`A/` 表示 `apps/platform-api/src/platform_api/`，`W/` 表示 `apps/platform-web/src/`。路径定位到文件和符号；实现时应再次核对代码。

- 本仓库基线 HEAD：`0bc15df1840c83750d821c93fb65600d0d483fa4`，开始时工作树干净。
- open-swe HEAD：`ad417d64`，但参考工作树有大量 staged/unstaged 改动，`agent/utils/tracing.py` 的 Git 状态为 `UU`。这里比较的是读取到的工作树内容，**不能声称是该 HEAD 的干净上游实现**；未启动或测试参考应用。
- 规划时Runtime锁定：GraphHarbor/runtime `0.13.0.post41`、LangChain `1.3.17`、LangChain Core `1.6.0`、LangGraph `1.2.11`、Deep Agents `0.7.8`、Langfuse `4.15.1`。当时使用可用解释器核对，工作树尚无`.venv`；实施期间已准备Runtime虚拟环境，实际版本与命令见[后端验收](implementation/02-backend-verification.md)。
- 除源码外，先查询 LangChain docs/reference MCP，核对官方 middleware 顺序和 `ModelFallbackMiddleware`；再核对已安装 SDK。未来实现无需为本方案升级核心依赖。

## open-swe 的实际设计

| 能力 | 源码与符号 | 怎样做 | 可借鉴部分及边界 |
|---|---|---|---|
| 异常分类 | `O/agent/utils/errors.py:classify_exception`、`code_for_error_type` | 读取 status/body 内 type/code、异常文字及类名，生成有限原因码 | 在异常仍完整时分类；精确字段优先，文字只作受限补充 |
| provider 详情 | 同文件 `exception_fields`、`_bounded` | 记录 class/message/status/request_id/body/cause，body 大于 2000 字符截断 | 有界数据值得借鉴；截断不等于脱敏，原文不能直接进入本平台观测出口 |
| Datadog 分组 | 同文件 `error_tracking_fields` | 输出 `error.kind/message/stack`，解决 Datadog 不识别 structlog `exception` 的问题 | 这是供应商适配，不是 Agent 必备契约；当前不引入 |
| 模型失败捕获 | `O/agent/middleware/model_errors.py:ModelErrorMiddleware.awrap_model_call` | 捕获模型异常、写日志、分类、尽力更新 Thread metadata，然后裸 `raise` | 装配位置和保留原异常值得采用；HTTP 自回写按本项目权限不可照搬 |
| 通知恢复原因 | `O/agent/completion.py:_failure_reason_code` | 完成 webhook 将 Thread 记录与终态异常类、run_id 比对，生成 Slack 等失败通知 | 借鉴“尝试失败不等于最终失败”；通知渠道、failure_reply_* 字段不迁移 |
| startup | `O/agent/utils/startup_trace.py:aphase/flush_phases` | 按 Thread 保存阶段时间，等模型前 prepare 完成后回放到 LangSmith RunTree | 阶段计时值得采用；全局 Thread 缓存和 tracer 私有 run_map 不采用 |
| startup 装配 | `O/agent/server.py:get_agent/PrepareAgentRunMiddleware`、`O/agent/middleware/prepare_run.py:BasePrepareRunMiddleware` | 工厂和 sandbox 后台任务计时，prepare 的 finally flush | 只映射模型解析、MCP、workspace 等通用阶段，删除 GitHub/repo/sender 业务阶段 |
| 追踪链接 | `O/agent/utils/langsmith.py:get_langsmith_trace_url` | 解析组织/项目，构造 Thread URL；凭据/endpoint 隔离缓存 | 借鉴服务端生成且失败可返回空；本项目使用 Langfuse |
| 前端入口 | `O/agent/dashboard/threads/summary.py:_thread_summary` 的 traceUrl 组装、`O/ui/src/features/agents/components/ThreadMenuItems.tsx` | 后端查询时提供 traceUrl，前端菜单显示链接 | 只借鉴受控排障入口，不移植 React 页面或查询模块 |

`_thread_summary` 在第 357 行查询 `get_langsmith_trace_url(thread_id)`、第 414 行返回 `traceUrl`。参考目录中的旧学习文档仍描述 `traced_graph_factory`；当前 `agent/server.py` 末尾是 `traced_agent = get_agent`，不能按旧包装器设计实施。

### middleware 真实顺序

open-swe 主工厂尾部顺序是：`fallback -> 若干消息规范化 middleware -> ModelErrorMiddleware -> ModelCallTimeoutMiddleware -> provider`。第一个 wrap 在最外层；错误诊断包住 deadline，deadline 生成的超时因此也能被记录。主调用和子 Agent 分别装配，不能只给父 Agent 装一次。

open-swe 的 fallback 是自定义实现，包含自己的瞬时错误/退避策略；本项目 reference agent 使用官方 fallback，生产 DearFlow/Showcase 未装配生产 fallback。这次只补观测，不把 retry/fallback 配置顺便推广到生产 Agent。

### startup 方案的代价

open-swe `_PHASES` 按 Thread 存储，上限 512 Thread/每 Thread 200 phase；关闭时用单调时钟算耗时，UTC 时间用于 trace。flush 寻找 LangSmith 当前 RunTree，失败时尝试 tracer `run_map`；没有父 trace 时已取出的 completed phase 不保证保留，detached task 的未完成阶段还会留到后续 flush。LangSmith 子 span 起点会被父 span 裁剪，所以源码还单独携带真实 elapsed_ms。

我们必须保留准确计时，但用本次构图局部对象/显式 callback 关联，避免同 Thread 后续 Run 借用前次阶段、取消遗留缓存和私有 SDK 依赖。

## 当前代码实际覆盖和缺口

| 当前能力 | 源码事实 | 差距和规划 |
|---|---|---|
| 受信请求关联 | `A/core/context/runtime.py`、JWT 双端、`R/observability/langfuse.py:_trusted_metadata` | 已有 request_id/platform_trace_id，不再重新做；补日志缺少的 platform_trace_id/受信 scope |
| Langfuse 模型/工具/子图回调 | `R/observability/langfuse.py:with_langfuse_tracing/_FailSoftCallback`；`tests/observability/test_graph_tracing.py` | 已有，SDK 也有 on_llm_error；缺的是平台稳定分类、安全错误载荷和尝试/图退出语义 |
| 本地 Run/Tool 诊断 | 同文件 `_RuntimeDiagnosticsCallback` | 只记录根图完成/duration、tool_error/token_total；没有 on_llm_error 和稳定 provider 分类，也没有单独 run-start 日志 |
| 离线装配 | 同文件 `with_langfuse_tracing` 第 386-388 行提前返回 | Langfuse 和 OTLP 都关闭时，本地诊断也未装配。旧教学文档称“常驻”与代码不符，01 修装配及相关文档/测试 |
| OTel | `R/observability/otel.py:OTelDiagnosticsCallback` | 只创建 `runtime.graph` 根 span；关联 ID 只是属性，没有服务间 parent context 传播，不可声称已有完整分布式 trace |
| 错误脱敏 | `_mask/_redact`、OTel `on_chain_error` | 已有凭据键和长度处理；OTel 仍直接 `record_exception(error)`，Langfuse error status_message 由 SDK 生成；须实测错误原文路径，不能只测 prompt mask |
| factory | DearFlow/Showcase `services/.../agent.py:get_agent`，末尾才调用 with_langfuse_tracing | MCP 加载、模型凭据兑换/构建、workspace 和 compile 在 callback 装配之前；构图失败没有该 callback 的根诊断 |
| 超时与恢复 | `R/middlewares/model_call_timeout.py`、reference `agent.py` | async deadline 已有；reference fallback/retry 是注入模型测试/示例路径；分类不能改变已有 timeout 或取消语义 |
| 子任务 | DearFlow `agent.py:middleware` 同时装父/子；GraphHarbor checkpoint namespace | 已有调用轨迹/历史；补分类时显式装到子 Agent，沿用 namespace，不建第二套子任务记录 |
| 原生执行身份 | post41 Worker 在 config.metadata 写实际 run_id/thread_id；config 顶层 run_id 不保证存在 | 中间件若只读 config.run_id 会漏关联；不得把 callback UUID 当 durable Run ID |
| 原生写权限 | `R/auth/platform.py:deny_image_scope_on_server_resources` | run-create 只允许 create_run，Thread update 属 thread-edit；`get_client().threads.update()` 的照搬方案不满足授权边界 |
| 查询 | `A/modules/runtime_gateway/application/service.py:get_thread_run/list_thread_runs` | 已授权后读取原生 Run；没有 Langfuse 安全摘要接口，也无专门诊断 DTO |
| 前端轨迹 | `W/modules/chat/trajectory/trajectory-adapter.ts`、`components/trajectory/TrajectoryInspector.vue` | 已由 messages/tool calls 展示过程，模型未产出消息时未必有失败记录，factory 也不在消息中；扩现有 Inspector 即可 |
| 日志 | Runtime 观测模块用 stdlib logging+extra；GraphHarbor worker 用 structlog；API `core/observability/logging.py:log_event` 用 JSON | “已有 structlog”不证明应用 extra 字段会出现在实际 stdout；01 明确检查真实 JSON 输出，不替换全仓日志框架 |

### 需人工裁决的安全差异

已安装 post41 `production_worker.py` 的失败路径把 `str(exc)` 写入 Thread error 与 lifecycle.error.message，并调用 `logger.exception`。平台 `_redact_event_value` 主要识别敏感键，不能证明异常字符串内部的 prompt、响应正文或 token 都被清除。生效 HTTP 错误标准要求未知原文不公开；SSE 是 draft，流内形状仍需单独核实。

这是当前代码与安全意图的差异，先记录，不在本轮自行改变权限或契约。建议 03 经人工评审后在 Platform 公共出口做有限投影；GraphHarbor 自有日志是否需要上游修复/采集侧治理另列评审结论，不能宣称本项目几处修改就实现全栈日志零泄漏。

## 同事方案逐项结论

| 建议 | 结论 | 本项目处理 |
|---|---|---|
| classify_exception | 采纳设计，调整边界 | 放 `observability/errors.py`，只在模型调用上下文分类；结构化 code 优先、有限文本兜底、未知固定码，详见 01 |
| error_tracking_fields | 本期不采纳供应商格式 | 输出稳定安全 JSON 字段；将来确实接 Datadog 且采集端需要时再做出口映射 |
| 新建 ModelErrorMiddleware | 采纳最小实现 | 只观察本次 handler 调用及原样抛错；复用官方 AgentMiddleware/TracePolicy，不自建 OpenSWEMiddleware 基类 |
| 写 Thread last_model_error | 不采纳原实现 | 用 Run 关联日志与现有 trace；无需新增 Thread 写授权、HTTP 自调用或最后错误槽位 |
| 放 fallback 内侧 | 采纳，同时包住 timeout | `RuntimeConfig -> 已有 fallback/retry -> ModelError -> Timeout -> provider`；参考官方顺序且测调用数/原异常 |
| startup 追踪 | 采纳目标，替换实现方式 | 构图局部计时，明确 graph/factory duration；OTel 使用公共时间 API，Langfuse 真实耗时放结构化记录，不伪造回放条 |
| LangSmith trace URL 回写 | 纠正事实，本期不引入 LangSmith | open-swe 当前是查询时生成 URL；我们保留 Langfuse、采用服务端 trace ID 安全摘要，外链默认不开放 |
| 当前状态“run 开始/structlog 已具备” | 部分成立 | 需补真实 start 事件和 JSON 字段落地；不以 logger 类型或类名推断采集效果 |
| 优先级中 | 作为整体排期参考 | 已有追踪，无需从零搭 APM；离线无诊断/错误原文出口优先于完整时间线、Collector 和成本看板 |

## 更广泛的生产化对照，本轮不开发

| 领域 | 当前已有 | 可借鉴/待独立验收 | 本轮决定 |
|---|---|---|---|
| 装配与探测分离 | get_agent 组合根、受管 Context、schema-only | factory 失败局部可诊断、探测无外部资源副作用 | 02 覆盖诊断；不引入通用 Agent Builder |
| 执行韧性 | deadline/调用限额、SDK 重连、GraphHarbor lease/durable queue | 当前模型超时和 worker 基础设施重试之间的作用边界；副作用防重 | 测不回归；重试策略修改另评审 |
| 沙箱与凭据 | workspace scope、Docker、BYOK、审批、LocalShell 开发模式 | 工作区失联不静默丢弃、并发/重启/生产隔离真实验收 | 沿现有专项，不迁移 provider 管理矩阵 |
| 人工参与 | interrupt/resume、多动作审批 | 超时/失败后正确终态与可恢复入口 | 验证本期不会误标；不改审批协议 |
| 子任务 | 只读角色、并发限制、namespace 历史 | 子任务错误定位、独立权限、归属标识 | 01/03 只补观测，不放开通用 shell 子 Agent |
| 长任务质量 | Deep Agents 摘要、Todo、Skills、记忆 | 完成校验、压缩连续性、证据/产物验收 | 接续 DearFlow 效果审计，不以可观测性等同完成可靠性 |
| 外部事件与通知 | 平台 Web/定时任务入口 | 幂等 dispatch/受控触发通用思想 | 不迁移 GitHub/PR/Slack/Linear/Reviewer/profile 属性和完成 webhook |

## 参考快照

以下 SHA-256 指向本轮读取的工作树文件，用于未来复核差异，文件名相对 `O/`：

```text
7fd3d670b24fd3f294757904322debdd8c3897eaeed8850d526f568eb0032e85  agent/utils/errors.py
ea1f0b984bd22e5bbee397d4d19ebe9024125724cc070845753eda00919d6252  agent/middleware/model_errors.py
f945356385e155a8f2a18a5d33ab6d63b1f314f964c4468e0530c04c9fa632f7  agent/utils/startup_trace.py
ae351e64abea8f7eed851ac6ee50a0afc24e15097929848b25a908030db319e0  agent/utils/langsmith.py
beb88ae8db70a2f46ab95a806583b4325afd86a377c080e842b82806b297613c  agent/completion.py
2e18fb2817e10bb722eb60cf6e43b193b4089bce5c8de0bc32f2439d368903cd  agent/server.py
e474c79223c1e7a3f582c037bd39fb52fe89737e7c967ce06a8d111c50c9b2a7  agent/middleware/model_fallback.py
5580163c9d0403e92bb3c1f0ceda32e13c63175ad6fa8de6c2471b2c3ca07f10  agent/middleware/model_call_timeout.py
722678a568f0c63b490a98f8b2a87572a84133c64f4efd9b503294b00efae8d2  agent/middleware/prepare_run.py
533d055c97c778f0a3d17fd9a0eb67920cd2c1f3037448fb1ec18226b683c6ee  agent/dashboard/threads/summary.py
```

官方参考：[middleware 顺序](https://docs.langchain.com/oss/python/langchain/middleware/custom#execution-order)、[ModelFallbackMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/model_fallback/ModelFallbackMiddleware)。已安装 Langfuse 的 `CallbackHandler(trace_context=...)`、`Langfuse.create_trace_id(seed=...)`、`create_event`、`mask_otel_spans` 与 LangChain `TracePolicy/omit_payload` 均已通过签名/导入核查。查询侧已确认 `langfuse.api.client.AsyncLangfuseAPI`、`AsyncTraceClient.list/get`、`AsyncObservationsClient.get_many` 和 `request_options` 可用，无需在线程池中包装同步查询；尚未验证新装配行为或服务端查询兼容性。

## 本轮验证证据

在 Runtime 服务目录执行，`RUNTIME_PYTHON` 指向可用的 Python 3.13 Runtime 解释器；PYTHONPATH 指向本工作树 `src`，没有借用主工作树业务源码：

```bash
env -u LANGFUSE_ENABLED -u OTEL_EXPORTER_OTLP_ENDPOINT -u OTEL_EXPORTER_OTLP_TRACES_ENDPOINT \
  PYTHONPATH="src" "$RUNTIME_PYTHON" -m pytest \
  "tests/observability" "tests/middlewares/test_runtime_middleware.py" \
  -q -m "not integration and not e2e"
```

结果：`49 passed, 5 warnings in 16.09s`。warnings 为既有 SWIG 类型 DeprecationWarning。此结果只证明已有测试基线；其中离线测试当前明确期待不装 callback，未来按 01 调整这一行为及断言。本轮未跑 open-swe、真实模型、浏览器、生产日志采集或新接口测试。
