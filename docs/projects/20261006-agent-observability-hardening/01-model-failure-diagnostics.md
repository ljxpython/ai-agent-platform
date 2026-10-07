# 01 模型错误诊断

## 目标

从真实模型异常提取稳定原因，离线可记录、远程导出可降级；同时区分一次模型调用失败和图退出。独立完成本专题无需 02 的阶段耗时或 03 的查询页面。

**状态：** 后端已完成（done），E01-E05及本专题Final于2026-10-07完成；用户于2026-10-06批准。整项目仍待同事的前端实现和浏览器联验。

## 方案设计

### 文件与职责

路径相对仓库根目录，Runtime 前缀为 `apps/runtime-service/src/runtime_service/`。

| 文件 | 既有/拟新增符号 | 具体改动 |
|---|---|---|
| `observability/errors.py`，新增 | `classify_exception`、`model_error_fields` | 有限模型异常分类和安全字段；不放入表示契约/鉴权错误的 `runtime/errors.py` |
| `observability/diagnostics.py`，新增 | `log_diagnostic` | 用 stdlib logging 输出显式 JSON，确保字段实际进入 stdout；只服务 Runtime 诊断，不建全仓日志框架 |
| `middlewares/model_errors.py`，新增 | `ModelErrorMiddleware.awrap_model_call` | 测量一次 handler 调用；失败分类和安全记录，重新抛出同一异常 |
| `middlewares/__init__.py` | 显式 export | 按当前方式导出新 middleware，避免隐式 import 链 |
| `observability/langfuse.py` | 现有 `with_langfuse_tracing`、`_RuntimeDiagnosticsCallback`、`initialize_langfuse`；拟新增 `record_diagnostic_event` | 本地回调独立装配；根开始/结束安全事件；补关联字段；以公共 create_event 导出安全分类；利用已安装 SDK span mask 清除错误原文 |
| `observability/otel.py` | `OTelDiagnosticsCallback.on_chain_error` | 使用安全 exception attributes，移除直接记录未脱敏异常的路径；不改变 exporter 故障隔离 |
| `services/reference_agent/agent.py:get_agent` | middleware 列表 | 加到已装 fallback/retry 的内侧、timeout 外侧 |
| `services/demo/showcase_demo/agent.py:get_agent.middleware` | 父/子公共列表 | 父 Agent 和声明式子 Agent 都装配 |
| `services/dearflow_agent/agent.py:get_agent.middleware` | 父/子公共列表 | 主 Agent 和 researcher 都装配，保持原权限/限额 |
| `services/demo/workflow_demo/agent.py:get_agent.model_agent_for` | 节点内模型 Agent | 装到动态创建的内部 Agent，不只包外部 workflow 根图 |

本专题不改 GraphHarbor，不推广生产 fallback、不增加 provider SDK 重试，也不修改 RuntimeAuthError/RuntimeResolutionError 的契约。

### 分类规则

`classify_exception(exc)` 只由模型调用边界使用。先处理预期控制流，再检查有限结构化 provider code，随后使用明确类名/HTTP 状态，最后用有界精确短语兜底。结构化 code 与宽泛文本冲突时采用结构化 code；具体优先级用下表和参数化测试冻结。

| 机器码 | 识别条件 | 不能推出的结论 |
|---|---|---|
| `provider_rate_limited` | status 429、明确 rate_limit code/RateLimitError | 不自动重发请求 |
| `provider_overloaded` | status 529、明确 overloaded code | 不等同上下文过长 |
| `context_too_long` | context_length_exceeded 等精确 provider code/受限已知短语 | 不是所有 400/413，也不自动清理会话 |
| `model_unavailable` | model_not_found/model_not_available等精确code，或已安装SDK的OpenAIModelNotFoundError | 普通404不据此归类，也不等同项目权限被撤销 |
| `provider_auth_failed` | 模型调用中的 401/AuthenticationError | 不触发平台登出 |
| `provider_access_denied` | 模型调用中的 403/PermissionDeniedError | 不撤销 Thread/项目授权 |
| `provider_timeout` | 模型 SDK timeout 或本次 ModelCallTimeoutMiddleware 产生的 TimeoutError | 不是任何图/工具 TimeoutError，也不等同 Run timeout |
| `provider_unavailable` | provider 5xx 或明确 APIConnectionError/连接失败 | 不是工具网络失败 |
| `model_call_failed` | 未匹配的模型 handler 异常 | 固定兜底，不把未知异常类名当无限机器码 |

body 为 dict 时只取有限 `error.code/type`，再取顶层 code/type；允许空/字符串/异常 SDK 对象，不能任意递归 provider payload。检查异常链最多 3 层且去重；文本分析最多 2048 字符、不得输出。通用 `APIError/APIStatusError` 无状态和 code 时保守兜底，不照搬“都是 unavailable”。

`CancelledError`、KeyboardInterrupt/SystemExit、LangGraph `GraphBubbleUp`/interrupt 不算模型故障，立刻重新抛出，不增加模型失败数。分类/记录自身报错必须 fail-soft，保留原模型异常及 traceback；禁止 `raise NewError(...)` 替换执行异常。

### 安全记录

固定事件：`runtime.model_call.failed`、`runtime.graph.started`、`runtime.graph.completed`、`runtime.tool.failed`。导出故障沿既有有限类别Counter统计，不新增逐token或补偿事件。

实装字段：schema_version、event、graph_id、durable `run_id`、thread_id、受信 request_id/platform_trace_id/tenant_id/project_id、callback_run_id 或 model_call_id、scope（primary/subagent）、有界 namespace、有界模型名、code、error_type、provider_status、duration_ms。不采集provider请求编号、任意provider code或stack定位片段。

- 不输出 `str(exc)`、provider body、HTTP headers、原始 stack、prompt、tool args/result、凭据、宿主绝对路径；不能把截断当脱敏。
- `logger.exception`/`exc_info=True` 不用于新的provider诊断日志；排障按Run/trace/namespace关联。
- 保留有限维度计数；run/thread/user ID 不作为 metric label。已有 Counter 是进程级诊断，不声称跨进程 Prometheus 指标或完整费用账本。
- 通过已安装 Langfuse `mask_otel_spans` 去除 SDK 生成的异常 message/stack/status_message 等属性；`_mask` 继续处理 input/output。先验证实际 exporter 输出，再确认字段白名单，避免假设 mask 覆盖一切。
- OTel ERROR 状态只含稳定 code/类型；exception event 用安全 attributes，不能把原异常交给 `record_exception` 后再声称脱敏完成。

### 分类如何到达查询接口

分类不能只存在于日志，否则 03 无法读取。本专题在现有 `langfuse.py` 中增加最小 `record_diagnostic_event`：模型 middleware 的一次失败、根图完成和工具失败分别通过已安装 SDK 的公共 `create_event` 写入安全 metadata。仅使用已初始化的进程 client，关闭导出时直接跳过；不用 HTTP 自回写、同步 flush、新队列或后台补偿。

- 模型事件固定 `name=runtime.model_call.failed`，包含 schema_version/event/code/error_type/provider_status/duration_ms、受信 scope、durable Run 及有界 namespace；不传 input/output 或 status_message。
- 根图事件固定 `name=runtime.graph.completed`，outcome 为 `success/failed/timeout/cancelled/interrupted`。其 error_code 仅在能证明根异常来源时填写，否则为 null；不使用此前一次模型失败代填。
- 构造 middleware 时显式传入本次已验证的诊断上下文；不从浏览器 metadata 猜身份，也不在模型错误后兑换第二次凭据。
- 与graph callback共用 `trace_id_for`：`runtime:v1:tenant:project:run` 的SHA256前16字节，显式trace_context；02复用并加入startup。无受信Run身份时仅本地记录，不建立远程业务trace。
- 03 只读取带本期 schema/event 白名单的诊断 event，并核对 observation 自身的 scope/run；旧 SDK generation 的原始错误文字不会在查询时重新分类。单次失败不同时按 event 和 SDK generation 重复计数。

Langfuse event 的时间表示记录发生时间；真实模型耗时取 duration_ms，不将零长度 event 冒充整个模型调用的 span。公共 create_event 和日志各自 fail-soft，执行异常及模型调用次数保持原样。

### 装配与身份

```text
RuntimeConfig/已有校验
  -> 已有 ModelFallback/ModelRetry（只在原本已配置的入口）
    -> ModelErrorMiddleware
      -> ModelCallTimeoutMiddleware
        -> provider
```

诊断必须看到 RuntimeConfig 最终选择的模型；不能把它放外侧后永远记录初始默认模型。诊断位于 deadline 外侧，捕获转换后的 TimeoutError。fallback 内部每次 handler 调用都单独记录，fallback 成功不生成最终失败。

- trusted scope 从已验证 Delegation facts 构造，不能取浏览器填的 tenant/project/user。
- durable Run ID 从当前 worker 提供的 `config.metadata.run_id` 读取，必要时核对 configurable 中的实际服务端值；config 顶层 run_id 常是 callback UUID，不能混用。
- 父/子调用都归属同一 durable Run，子任务用现有 namespace/callback 关系定位；无法证明归属时省略，不能编造 child Run ID。
- 无执行身份的 schema/probe 路径不调用模型、不创建 exporter/client，也不生成虚假的 Run 事件。
- 既有其他 demo 的 `with_langfuse_tracing` 消费者获得统一 callback 修复；仅它们真实包含模型边界且有测试时装配模型 middleware，不把业务观测绑到模块名判断。

### 尝试与图退出

模型 middleware 只产生 `model_attempt` 证据。根 callback 的 graph completion 是 `graph_execution` 证据，仍不是 GraphHarbor 持久化终态；worker 的 drain、重试或租约切换可能产生多个图执行。

例如主模型 429 后备用成功：保留一条模型失败证据，native Run success，页面不能红色标记最终失败。又如模型恢复后工具失败：根异常是工具错误，不能沿用刚才的 provider 分类。GraphBubbleUp、正常审批和用户取消不计入 provider 错误。

本地事件无需写 Thread/Run metadata，也不调用 Agent Server 自己的 HTTP API。需要跨刷新查看时由 03 从已有 trace 获取安全观测；导出关闭时继续有本地诊断，但查询显示 disabled。

## 任务拆分

### E01 安全模型分类，预计 0.5 人天

- [x] **改动内容：** 实现有限分类及安全字段，冻结优先级/兜底和 provider 与平台鉴权区别。
- **代码位置：** 拟新增 `apps/runtime-service/src/runtime_service/observability/errors.py:classify_exception/model_error_fields`。
- **预期结果：** OpenAI-compatible、Anthropic/DeepSeek 和未知异常可稳定分类，不外发原文。
- **验证项：** 实际 `tests/observability/test_diagnostics.py` 参数化矩阵，含 SDK实际异常、冲突code/status、循环cause与canary。
- **状态：** done。

### E02 模型观察 middleware，预计 0.5 人天

- [x] **改动内容：** 观察一次调用、分类、安全日志、取消/控制流放行和原异常保留。
- **代码位置：** 拟新增 `middlewares/model_errors.py:ModelErrorMiddleware`；`middlewares/__init__.py`。
- **预期结果：** 每次可观察模型 handler 失败一条证据；诊断失败不修改业务结果。
- **验证项：** 同步图/异步图执行使用当前 middleware 支持范围；timeout 外包、fallback 成功/全失败、取消和 logger 故障。
- **状态：** done；实际为异步模型边界，未新增同步调用实现。

### E03 本地回调和导出安全，预计 1 人天

- [x] **改动内容：** 独立装本地诊断；受信关联字段和 JSON；安全分类 create_event 与 graph 共用 trace_context；Langfuse 原生 span mask；OTel 安全 exception event。
- **代码位置：** `observability/langfuse.py:with_langfuse_tracing/_RuntimeDiagnosticsCallback/initialize_langfuse`、`observability/otel.py:OTelDiagnosticsCallback`，拟新增 `observability/diagnostics.py:log_diagnostic`。
- **预期结果：** 双导出关闭仍有 start/completion/tool 诊断；任一 exporter 构造或调用失败不取消本地诊断；取消原样传播。
- **验证项：** 改 `test_disabled_returns_original_graph_without_sdk` 的行为断言；保留原有 49 项基线相关用例；真实 stdout JSON、span exporter canary 与一次失败只返回一条模型诊断的查询契约。
- **状态：** done。

### E04 正式入口与子 Agent 装配，预计 0.5 人天

- [x] **改动内容：** 显式加入四个正式 graph 的实际模型边界，包括父/子/动态 workflow 节点；不改现有 fallback 策略。
- **代码位置：** 上述四个 `services/.../agent.py:get_agent`，DearFlow/Showcase `middleware()`，Workflow `model_agent_for()`。
- **预期结果：** 运行模式覆盖完整，probe 不接外部资源，RuntimeConfig 选择后的模型名准确。
- **验证项：** `tests/services/reference_agent/test_agent.py`、`tests/services/showcase_demo/test_agent.py`、`tests/services/dearflow_agent/test_agent.py/test_subagents.py`；新增最小 middleware 顺序组合用例。
- **状态：** done。

### E05 专题 Final 与文档，预计 0.5 人天

- [x] **改动内容：** 独立完整回归本专题，更新教学文档“常驻/完整 OTel”错误描述。
- **代码位置：** `tests/observability/`、`tests/middlewares/`、四个 graph 组合测试；`docs/architecture/05-runtime-service/concepts/12-runtime-observability-langfuse-and-otel-pipeline.md`。
- **预期结果：** 达到以下门禁，独立报告 01 done，整项目状态仍按 README 联合范围。
- **验证项：** 离线可运行测试 + 真实 Worker/provider stub 失败链路 + stdout/导出内容核查。
- **状态：** done，2026-10-07；最终原生Run链路和SDK安全证据见Final及验收记录。

## 验证要求与记录

| ID | 层次 | 场景与必须满足的结果 |
|---|---|---|
| EV01 | 单元 | 429/529/400-context/401/403/5xx/连接/timeout/未知；有限码与顺序正确 |
| EV02 | 单元 | None/string/dict body，超长信息，异常链循环，异常属性读取抛错；保守兜底且无原文 |
| EV03 | 组合 | fallback 成功、retry 成功、全失败；调用次数不增，保留每次可观察失败，终态不误判 |
| EV04 | 组合 | 模型 deadline 超时可记录；用户取消/GraphBubbleUp/HITL 不产生 provider 错误 |
| EV05 | 组合 | 模型恢复后工具/授权错误退出；不引用旧模型失败作终态原因 |
| EV06 | 组合 | 父/多个并行子任务、两项目多个 Run；scope/namespace 不串线 |
| EV07 | 组合 | 导出全关、单开、双开、SDK初始化失败、503/队列满；业务结果和本地诊断不受影响 |
| EV08 | 安全 | canary 位于 error message/body/cause/stack/header；本地 JSON、OTLP、Langfuse 导出均无原文 |
| EV09 | 集成 | 隔离真实 Runtime API/Worker + 本地 provider stub 注入错误，确认 durable run_id 与 stdout关联，Langfuse安全event可读且与graph同trace |
| EV10 | 回归 | 正常对话、工具、研究子任务、审批/拒绝/恢复、定时任务、不产生模型调用的 schema探测正常 |

从 Runtime 目录的计划命令（新增测试实施后才存在）：

```bash
uv run pytest "tests/observability" "tests/middlewares" \
  "tests/services/reference_agent" "tests/services/showcase_demo" \
  "tests/services/dearflow_agent" -m "not integration and not e2e" -q
uv run ruff check "src/runtime_service/observability" "src/runtime_service/middlewares"
uv run ruff format --check "src/runtime_service/observability" "src/runtime_service/middlewares"
```

阶段验证仅记录 E01-E04 对应门禁；Final 在所有任务完成后单独记录。集成配置使用隔离数据库/Redis namespace 和本地 stub，不重启现役平台。实际启用的真实 provider 至少各一条成功与受控失败/超时 smoke；缺环境必须单列未验，不能用 stub 代替生产 provider 结论。

### Phase 记录

| 任务 | 日期 | 实际Phase证据 |
|---|---|---|
| E01 | 2026-10-06 | test_diagnostics 的9类码、冲突优先级、循环异常及SDK异常测试通过；最新整个文件34 passed/5 warnings。 |
| E02 | 2026-10-06 | 同一异常对象、记录故障、取消/HITL、fallback成功/全失败、retry恢复和timeout组合通过；恢复后工具失败保留独立证据且graph不沿用模型code。 |
| E03 | 2026-10-06 | 关闭导出本地回调、OTel安全event、Langfuse真实内存exporter的session.id/trace/无canary通过；既有观测测试纳入240项回归。 |
| E04 | 2026-10-06 | Runtime主定向回归240 passed/1 skipped/5 deselected；四入口、父子隔离、模式、workflow、schema及定时任务覆盖。 |

扩展DearFlow回归：103 passed/32 skipped/3 deselected，另3项测试进程启动/导入超时；跨服务向量独立复跑通过，MCP两项先完成扩大测试预算的核验，再于2026-10-07按原45/60秒预算复跑2 passed。原始超时记录保留，skip不计为pass。

合规检查：用户评审已记录；保留原异常、未新增恢复/Thread回写/诊断存储；真实导出脱敏及语义组合有可执行测试。源码说明见 [实施记录](implementation/01-backend-runtime.md)。

### Final 记录

2026-10-07：**本专题后端Final done**。实际命令、版本、stdout/SDK导出安全断言和完整结果见 [后端验收](implementation/02-backend-verification.md)，原始DTO与Run ID见 [证据JSON](implementation/backend-runtime-evidence.json)。

- EV01/EV02/EV08：最新诊断文件35 passed；已安装SDK的模型不存在类型与普通404分开分类，canary不进入本地诊断、OTel或Langfuse SDK exporter。
- EV03/EV05/EV06/EV09：真实API/Worker完成429失败、fallback成功、恢复后工具失败、两个并行research子任务、同Thread两Run；模型调用证据与图/native终态分开。原生fallback Run `cb98d0da-261f-4e21-addb-1b901c6fd719` success且保留429记录。
- EV04/EV07/EV10：timeout/取消/HITL/exporter构造/503/队列饱和由组合和实际SDK测试验证；隔离原生HITL/取消无provider错误，关闭导出仍完成正常Run。四组合根和原审批/恢复/定时相关回归见Phase，不把未启用真实provider测试当作通过。
- 已配置DeepSeek代理成功与受控不存在模型失败均通过；Anthropic没有真实配置，未做线上smoke。GraphHarbor自有私有原异常日志仍按R05排除。

无后端阻塞；前端展示与浏览器端语义仍须F01-F04/FV01-FV10完成，整项目保持partial。
