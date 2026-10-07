# 02 启动阶段追踪

## 目标

回答“首个模型调用前为什么慢、卡在哪一步、失败发生在构图还是执行”，将 factory/准备阶段按本次 durable Run 关联到现有追踪。无需 01 的模型分类或 03 的页面，也能独立完成阶段日志与 OTel 验收。

**状态：** 后端已完成（done），S01-S04及本专题Final于2026-10-07完成；2026-10-06用户已批准。页面和浏览器联合验收由同事接续。

## 方案设计

### 取舍

采用构图局部 `StartupDiagnostics` + 官方计时/追踪 API。局部对象在本次 `get_agent` 内创建，随 callback 明确交接；不用模块级 Thread 字典、LangSmith RunTree、私有 callback run_map 或图执行代理。

两种输出保持区别：本地结构化日志和 OTel 可以精确保存真实阶段起止；Langfuse 通过公开观察 API即时记录阶段，与 graph callback 使用相同受信 trace ID。若 SDK 不能可靠表达某个阶段的图形条，保留准确 `started_at/ended_at/duration_ms`，不倒放或伪造真实 span 时序。

### 覆盖阶段

| 阶段名 | 当前代码位置 | 需要记录什么 |
|---|---|---|
| `factory.context_resolution` | 四个正式服务 `agent.py:get_agent` 的 Context hash/resolver | 解析耗时；安全失败码；身份未验证时不保留用户自填 scope |
| `factory.memory_policy` | DearFlow `get_agent` 的 `memory_allowed` | 能力查询耗时；不记录 memory 正文/用户问题 |
| `factory.mcp_tools` | DearFlow `get_agent -> load_mcp_tools` | 工具装配耗时；有界工具数量；不输出 token/endpoint/header |
| `factory.model_connection` | `runtime/modeling.py:fetch_model_connection` 的调用块 | 受信模型连接兑换耗时；失败阶段；不输出连接配置 |
| `factory.model_build` | `build_model/apply_reasoning` 的调用块 | 模型构建耗时；目录 model_id；probe 不初始化凭据 |
| `factory.workspace` | Showcase `create_workspace` / DearFlow `DearWorkspaceBackend/build_backend` | backend 类型和阶段耗时；没有真正启动容器时不能叫 sandbox.boot |
| `factory.agent_compile` | `create_agent/create_deep_agent/build_graph` 调用块 | 图编译耗时；固定 graph_id；不导出完整 config/prompt |
| `factory.total` | 完整 `get_agent` 执行分支 | factory 总耗时，允许包含上述阶段之间未单独命名的工作 |
| `node.model_prepare` | Workflow `model_agent_for` 内部 fetch/build | 发生在图执行时，不计入 factory.total，仍关联同一 durable Run |

不迁移 repo instructions/GitHub token/sender/profile/admin_thread 等 open-swe 业务阶段。定时任务执行前授权已有 `scheduled_execution` 包装器，此处先不改其语义；本期 factory.total 从服务组合根开始，不承诺含 cron 授权、排队或全部 API RTT。后续确需测授权，采用该包装器自己的安全事件另行记录。

### 时钟与记录

新文件 `apps/runtime-service/src/runtime_service/observability/startup.py` 已实现：

- `StartupDiagnostics`：本次 factory 的局部时间记录和受信关联字段。
- `StartupDiagnostics.phase(name)`：context manager；UTC 起止时间用于展示，`time.monotonic_ns()` 差值用于 duration。
- `StartupDiagnostics.finish()`：汇总总耗时与已完成阶段，交给本地日志和可用 exporter。失败/取消时同样结束，不吞执行异常。

名称只接受固定阶段集，最多 16 条阶段记录/一次构图，metadata 只含 scalar 白名单；记录上限不影响实际阶段执行。重复同阶段用 ordinal 区分，无 run/thread/user metric label，不保留请求正文。

捕获 BaseException 仅用于 finally 计时与资源结束；异常/取消必须重新抛出。logger/span start/span end 失败各自隔离，不能在观测初始化异常时重新执行 factory。直接被进程杀死时可能没有结束记录，标记“不完整”，不能假报 zero duration 或成功。

### 身份与 Run 关联

- 验证 Delegation facts、Context 和 Thread scope 后才装入 tenant/project/model 等字段；factory入口先取时间戳，不能先信任 config.metadata 的业务身份。
- 使用 Worker 对 `config.metadata.run_id` 的真实注入及 `configurable.thread_id`。callback 自身 `run_id` 单独保存，不能用 Thread ID 为 phase key。
- 一个 Thread 的两次 Run、两个项目中相同请求参数、多个并行子任务互不共享 collector；schema/probe 路径完全不创建远程观测资源。
- 无 native Run ID 的本地直接调用仅记录无 durable Run 的局部日志，不生成假 UUID、不冒认平台 Run。已有注入模型测试显式给合法测试身份。
- 对签名身份拒绝等验证前失败，只记录固定 graph_id/安全拒绝事件；不产生基于未验证 tenant 的 trace。平台已有请求审计用于定位这类拒绝。

### Langfuse 与 OTel 的落点

| 通道 | 计划实现 | 真实保证 |
|---|---|---|
| 本地 JSON | `runtime.startup.phase_completed`、`runtime.startup.completed`，失败阶段记安全error_type；不猜provider码 | 关闭两种远程导出仍可按已记录 ID 查日志 |
| Langfuse | 复用01的 `trace_id_for` 和显式 `CallbackHandler(trace_context={"trace_id": ...})`；公开create_event前绑定session | 同一 native Run 的 startup 与模型/工具回调在同 trace；基础设施再执行可以有多个根 observation，不声称“一 Run 仅一次执行” |
| OTel | `OTelDiagnosticsCallback` 接受显式 startup 记录；用公共 start_time/end_time API生成 `runtime.execution` 父 span、`runtime.startup` 和原 graph 执行 span | execution 父 span从 factory开始，startup child在其真实区间，graph child仍保持原图执行计时；没有 API跨服务父 context |

OTel 模型/工具语义目前由 Langfuse负责，本期不重建全节点 span系统。OTel trace ID 与 Langfuse trace ID未统一时分别命名；`platform_trace_id` 仍是日志关联属性，不强行改为任何 exporter 的 trace ID。

Langfuse使用已安装公共 API，无需等待 graph根callback才有trace容器；每个阶段退出记录准确时间。阶段/总计通过公共 create_event 写入 schema_version/event/name/ordinal/outcome/真实UTC起止及duration_ms，供03按白名单读取；能精确表示时再沿公共 start_observation 生成图形span，不为timeline另造回放机制。context/span属性和错误原文受01的统一脱敏规则保护；独立实施02时至少自带安全字段过滤和Exporter故障隔离，不能依赖01已上线。

factory抛错、尚未生成graph时：局部总诊断和可用 startup trace正常结束并记录失败；OTel单独生成 `runtime.startup` 根，不能虚构 graph.started。成功时 callback得到相同collector/trace关联，应用原有 `graph_duration_ms` 不悄悄改为包括factory的耗时。

### 代码落点与调用者

| 文件 | 函数/拟新增符号 | 补充内容 |
|---|---|---|
| `observability/startup.py`，新增 | `StartupDiagnostics.phase/finish` | 局部生命周期、精确计时和安全阶段列表 |
| `observability/langfuse.py` | `_new_callback/with_langfuse_tracing` | 可选显式 startup/trace_context；保留原有已有callback，不双绑同一SDKhandler |
| `observability/otel.py` | `OTelDiagnosticsCallback.on_chain_start/on_chain_end/on_chain_error` | 真实父子时间、factory完成记录和清理 |
| `services/reference_agent/agent.py:get_agent` | 服务唯一组合根 | fetch/build/compile阶段与失败finally |
| `services/demo/showcase_demo/agent.py:get_agent` | 服务唯一组合根 | Context/model/workspace/compile阶段 |
| `services/dearflow_agent/agent.py:get_agent` | 服务唯一组合根 | memory policy/MCP/model/workspace/compile阶段 |
| `services/demo/workflow_demo/agent.py:get_agent/model_agent_for` | 工厂及节点内准备 | 区分factory和node阶段 |
| `graphs/*.py` | 现有 `scheduled_execution` 包装 | 本期只做回归，仍是薄注册入口；不把受信事实解析挪入通用追踪builder |

## 任务拆分

### S01 局部阶段计时，预计0.5人天

- [x] **改动内容：** 实现局部 collector、固定阶段、单调时钟/UTC记录和异常finally。
- **代码位置：** 拟新增 `observability/startup.py:StartupDiagnostics`。
- **预期结果：** 同Thread不同Run不串线，失败/取消记录准确，无全局phase缓存。
- **验证项：** 实际 `tests/observability/test_diagnostics.py` 包含时钟跳变、各固定阶段失败/取消、并行collector与数量上限。
- **状态：** done。

### S02 四个正式Graph埋点，预计0.5人天

- [x] **改动内容：** 只包当前真实I/O/compile块；探测跳过，失败时有factory.total。
- **代码位置：** 上表四个 `services/.../agent.py`，调用之前完成身份校验。
- **预期结果：** 不增模型调用/工具加载次数，不改变构图与调度结果，Workflow节点计时不混入factory。
- **验证项：** 现有服务组合测试+每个失败阶段一条注入测试+probe无网络断言。
- **状态：** done。

### S03 官方追踪关联，预计0.5人天

- [x] **改动内容：** Langfuse显式trace_context，OTel execution/startup/graph时间范围；处理无父图的factory失败。
- **代码位置：** `observability/langfuse.py:_new_callback/with_langfuse_tracing`、`observability/otel.py:OTelDiagnosticsCallback`。
- **预期结果：** 可按durable Run找到startup和graph，保留原callback与业务异常。
- **验证项：** 内存SpanExporter精确时间/父子关系；Langfuse mock及真实平台capture验证trace一致；再执行两轮Run隔离。
- **状态：** done。

### S04 专题Final、性能与文档，预计0.5人天

- [x] **改动内容：** 正常/失败/取消/Exporter关闭的完整链路与成本实测；更新观测架构说明。
- **代码位置：** `tests/observability/test_diagnostics.py`、正式Graph组合测试、`scripts/verify_agent_observability.py`。
- **预期结果：** 阶段时间可解释、资源清理、无隐式网络同步阻塞。
- **验证项：** 下表全部完成，单列本专题Final。
- **状态：** done，2026-10-07；最终原生Run链路和SDK安全证据见Final及验收记录。

## 验证要求与记录

| ID | 层次 | 场景与预期 |
|---|---|---|
| SV01 | 单元 | UTC时钟跳变而monotonic递增；duration不负、不按UTC差值计算 |
| SV02 | 单元 | 固定phase名/数量/metadata上限；没有输入正文或绝对路径 |
| SV03 | 组合 | model connection、MCP、workspace、compile各失败；只有真实阶段，原异常保留 |
| SV04 | 组合 | 构图中取消；所有本次phase闭合，CancelledError传播；不残留后续Thread数据 |
| SV05 | 组合 | 同Thread连续两Run、不同项目并行、多子任务；collector/trace隔离 |
| SV06 | 组合 | schema探测/图发现无网络、无模型调用、无workspace初始化、无远程追踪 |
| SV07 | 集成 | 正常平台Run：startup与模型/工具同Langfuse trace，metadata.run_id吻合 |
| SV08 | 集成 | factory在graph前失败：日志/trace可查，原生Run错误，不虚构graph开始或成功 |
| SV09 | 安全/故障 | exporter constructor/span start/end/flush故障；执行次数、审批、取消语义不变，payload无canary |
| SV10 | 性能 | 预热后相同隔离任务A/B至少50次，记录p50/p95 factory、首模型/首token、graph耗时、导出队列和内存 |

性能当前没有已批准SLO；先记录开启/关闭诊断的增量及异常点，不临时编造“生产达标”阈值。确认无额外业务网络调用、每Run固定上限阶段/日志、无全局缓存增长即可作为结构门禁；延迟阈值交人工根据实测确定。

计划执行：

```bash
uv run pytest "tests/observability" "tests/services/reference_agent" \
  "tests/services/showcase_demo" "tests/services/dearflow_agent" \
  "tests/runtime/test_scheduled.py" -m "not integration and not e2e" -q
uv run ruff check "src/runtime_service/observability" "src/runtime_service/services"
uv run ruff format --check "src/runtime_service/observability" "src/runtime_service/services"
```

### Phase记录

| 任务 | 日期 | 实际Phase证据 |
|---|---|---|
| S01 | 2026-10-06 | test_diagnostics：UTC跳变时monotonic duration正确，七个factory阶段各失败/取消原样抛出；三collector独立/16阶段上限通过。 |
| S02 | 2026-10-06 | 四graph、DearFlow模式/子任务、workflow、MCP及schema回归纳入240 passed；probe不初始化业务资源。 |
| S03 | 2026-10-06 | OTel内存exporter验证execution/startup/graph父子与区间；失败无虚构graph；Langfuse真实SDK event验证同trace/session和无canary。 |

合规检查：collector仅本次构图持有；不使用Thread缓存、私有RunTree或图代理；不增加模型次数。SV10微基准关闭远程导出，远程队列证据与A/B增量分开记录，不能用本地结果声称生产总耗时达标。

### Final记录

2026-10-07：**本专题后端Final done**，命令/版本/成本和限制见 [后端验收](implementation/02-backend-verification.md)，原始结果见 [证据JSON](implementation/backend-runtime-evidence.json)。

- SV01-SV06/SV09：单调计时、UTC跳变、阶段数量、取消原样传播、局部collector和probe隔离已验；SDK/exporter故障及安全断言见独立测试。MCP两个原预算用例最终复跑2 passed，未调整生产超时。
- SV07/SV08：隔离原生Worker正常Run与startup/graph同trace；factory失败Run `3fcd3bc4-d52d-43db-9d24-393bc17b521f`为error/partial，有失败model_build阶段、无graph观察。同Thread两Run和并行research子任务没有共享collector或trace。
- SV10：同任务预热3次后baseline/enabled各50次，关闭远程导出；factory p50/p95分别121.835/160.091ms与140.384/268.138ms；首模型、首token、graph及Python峰值均在JSON中。tracemalloc、顺序测量和同进程负载会影响结果，不宣称生产耗时达标。
- 导出队列饱和与OTLP HTTP503使用实际SDK/exporter测试；公开有限计数器保留。SDK没有本次可用的公开队列深度接口，未依赖私有队列读取或虚构线上队列容量。

教学文档已更新。无后端阻塞，启动阶段页面及浏览器联合验收仍未实施。
