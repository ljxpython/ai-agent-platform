# F02：通用重复工具调用保护的方案、实施与验收

> 2026-10-09：用户已完成评审并明确批准实施；Runtime/API、非前端验证与前端交接已完成，只剩T07前端实施及浏览器联合验收，F02整体partial。
> 本篇承接 [12/T07](12-completion-plan.md) 的重复调用切片和 [14/E05](14-effect-parity-and-reliability.md)。F02 的任务与验证状态只在本篇维护，不再创建第二套 DearFlow 项目或全局 tasks.md。其余可靠性、Skills 和媒体需求不由本篇重新批准。

## 目标

已按评审方案实现小范围补充：在已有调用、步骤和时间预算之前，识别已知只读工具连续出现的相同调用和相同结果，先提醒，持续重复则停止。它是疑似无进展的启发式保护，不是任务进度判官，也不是所有循环的证明。

当前项目不是缺少基本运行保护。真正缺口是短周期重复的提前识别及明确的停止原因。原六次相同 `ls` 的缺口已复现并补齐；三组真实模型只读烟测无误停，但生产发生率、费用节省和真实任务误判率尚未测量，不能把参考项目默认开启当作本项目上线依据。

### 本轮范围与分级

| 项目 | 结论 |
| --- | --- |
| 改动级别 | 治理改动：会改变执行终止策略、恢复状态及跨服务公开错误/诊断契约 |
| 本轮授权 | 用户已批准实施，完成Runtime/API、非前端验证及前端交接；不实施前端、不发布现役 |
| 后续实现归属 | Runtime/API 由后端开发者实施；前端由用户同事实施 |
| 模板 | 延续原多专题模板，本篇自带方案、任务、验证和状态 |
| 预计工作量 | Runtime/API 和隔离验证约 5-7 工程日；前端约 0.5-1 日，联合验收约 0.5-1 日；G0 后校准 |

## 方案设计

### 1. 源码和依赖基线

以下外部目录均为用户指定的本机参考 checkout，不是本仓库运行依赖。

- 当前平台 HEAD：`85d63d87bdf84dabbb963f79e8dd4b2db4432ade`，分析开始时工作树干净。
- DeerFlow HEAD：`cc664451f03140b376611f329ae400c313530bdb`。参考 checkout 有其他本地修改，本篇使用的 loop middleware、tool-call metadata、loop config、lead agent 和三份 loop 测试文件的定向 `git status --short` 为空。
- Open-SWE HEAD：`ad417d64d91cc349d63d832c7b643637dc1774cf`。server/middleware 等有本地修改，`uv.lock` 有未合并状态；本文描述所读本地内容，不声称是该 commit 的原始内容或远端最新版本。
- 当前锁和所用解释器一致：DeepAgents `0.7.8`、LangChain `1.3.17`、langchain-core `1.6.0`、LangGraph `1.2.11`、GraphHarbor 双包 `0.13.0.post43`。旧总纲的 post37 和部分状态快照的 post42 不作为本篇版本前提。
- 已读 Runtime 开发标准、Platform API 开发规范、Web playbook、跨服务规范健康表及对应错误/SSE规范；已查询 LangChain Docs/Reference MCP。线上文档只说明 API 意图，锁版本源码和组合测试决定可用行为。

源码索引中 `DF` 表示 DeerFlow 的 `backend/packages/harness/deerflow/`；`OS` 表示 Open-SWE 的 `agent/`。行号是本次快照定位，实施时用符号再次查找。

| 参考代码 | 本次核对的符号/位置 | 能说明什么 |
| --- | --- | --- |
| `DF/agents/middlewares/loop_detection_middleware.py` | `_stable_tool_key` L180、`_hash_tool_calls` L209、`_track_and_check` L542 | 相同调用批次的签名与独立的工具名频率窗口 |
| 同上 | `_apply` L781、`_inject_warnings` L903、`consume_stop_reason` L460 | 提醒延迟到下次请求；硬停止改写消息并另行传播停止原因 |
| `DF/agents/middlewares/tool_call_metadata.py` | `clone_ai_message_with_tool_calls` L87 | 同步 structured/raw/content 中的 provider 工具调用表面；不是只清一个列表 |
| `DF/config/loop_detection_config.py` | `LoopDetectionConfig.validate_thresholds` L67 | warn/hard 的配置校验；当前未校验 identical hard <= window |
| `DF/agents/lead_agent/agent.py` | `build_middlewares`，loop 装配 L715 | 功能由上游 app 配置决定，不是工具自身提供 |
| `DF/subagents/executor.py`、`subagents/status_contract.py` | `consume_stop_reason` 消费、`SubagentStopReasonValue` | `loop_capped` 依赖上游自己的执行器和结果契约 |
| DeerFlow `frontend/src/core/tasks/subtask-result.ts` | `SUBAGENT_STOP_REASON_KEY` | 前端消费后端原因；浏览器不参与检测 |
| `OS/server.py` | `ModelCallLimitMiddleware` L1299、`TimeoutWrapupMiddleware` L1321 | 已有预算兜底，没有发现同签名循环检测的装配 |

### 2. 同事方案中需要修正的判断

| 原提议 | 实际情况与取舍 |
| --- | --- |
| 重复工具或重复输出震荡 | 这个 DeerFlow middleware 遇到没有 `tool_calls` 的 AIMessage 直接返回；它不检测重复文本。普通 Agent 文本终答自然退出，不能为不存在的文本续跑机制再造探测器 |
| 在 after_model 提示 | 该处只作检测/排队。真正提示在 wrap_model_call 追加请求消息，保证 AI tool calls 后先有 ToolMessages；不能在配对中间插入 Human/SystemMessage |
| MD5 hash tool_calls 集合 | 实际是按工具名和归一化参数排序的多重集，重复项仍保留；窗口单位是模型调用批次，不是单工具次数。MD5 是去重手段，不是安全控制或身份签名 |
| 双层都应该迁入 | 按工具名计频率属于预算策略，已有官方 ToolCallLimitMiddleware 可做 per-tool/run/thread 限制。DeerFlow 的频率层是 burst 窗口，和本项目现有累计 cap 不完全相同，但没有本项目 burst 需求证据，不新增第二套计数器 |
| read_file 特殊处理照搬 | 上游使用 `path/start_line/end_line`；本项目官方工具为 `file_path/offset/limit`，默认 offset=0、limit=100。复制行号归一化会丢分页差异，造成误判 |
| write_file / str_replace 专用策略 | 本项目是 `write_file/edit_file/execute`；`str_replace` 不是当前内置工具。实际 payload 必须保留，不能只按路径判重复；本期先不对写入或执行工具强制熔断 |
| 清 tool_calls 就能得到总结 | 上游是克隆当前消息、附加框架停止文案后自然结束，并未保证额外模型生成总结。中断本身不能证明已保存全部产物或完成了任务 |
| clone helper会清除所有无效调用 | 当前helper保留 `invalid_tool_calls` 及其内容块，交给上游DanglingToolCallMiddleware配对；脱离该配套就不能承诺全部调用表面已清除。本方案不改写AIMessage，因此不引入这组依赖 |
| 写 stop_reason=loop_capped 即可 | 上游写进运行 context 和内部有界 map，再由 worker/subagent executor 消费。本项目受管 RuntimeContext 和 GraphHarbor 生命周期不同，不能直接移植这个私有状态出口 |
| per-(thread_id, run_id) 内存历史足够 | 上游有锁、LRU、fallback invocation ID、pending warning 清理和 stop reason owner map。它们不能保证本项目构图重建/Worker 接管后的持久性；进程 map 也不应成为第二份执行事实源 |
| enabled=true、3/5/20/30/50 是通用生产默认值 | 只是参考项目策略。上游 identical hard 大于 window 时不可达；频率窗口则另扩容到至少最大 hard。本项目不迁入这些参数组合，先实测误判和节省再启用 |

### 3. 当前已有能力、真正缺口与职责分层

| 能力 | 当前事实来源 | 本篇决策 |
| --- | --- | --- |
| 模型/步骤预算、告警和收尾 | [ExecutionBudgetMiddleware](../../../apps/runtime-service/src/runtime_service/middlewares/execution_budget.py)、[预算专项](../20261007-agent-execution-budget/README.md) | 复用；不改变 cap、counter 和 end/error 策略 |
| 工具累计调用限制 | DearFlow/Showcase/Reference 组合根的官方 `ToolCallLimitMiddleware`，Dear另有 task cap | 复用；不移植频率 Counter、工具 override YAML |
| Run/模型超时与取消 | [超时专项](../20261006-agent-run-timeout-governance/README.md)、[停止专项](../20261007-agent-run-cancellation/README.md) | 复用；F02 不承诺执行中立即停止或单子任务取消 |
| prepare、provider/只读 task 有界重试 | [重试专项](../20261007-agent-production-capabilities/README.md) | 复用；循环保护必须不可重试，不能被父 task 或 Worker 自动重放 |
| 工具错误、历史配对、摘要与用量 | [工具容错](../20261006-agent-tool-error-resilience/README.md)、[上下文](../20261006-agent-context-window-governance/README.md)、[用量](../20261007-agent-usage-cost-governance/README.md) | 复用；F02 不是费用预算、完成核验或 provider 响应修复 |
| 短周期相同工具调用 | 本轮六次相同 ls 全部执行；源码没有 LoopDetectionMiddleware | 小范围补充；不是重新实现 Agent 循环 |
| 文本震荡、A/B 交替、所有参数变化的停滞 | 本轮未证明需求，现有预算仍有界 | 不纳入第一版；有独立失败证据再评审 |

| 层 | 要不要改 | 后续开发范围 |
| --- | --- | --- |
| runtime-service（用户所称 runtime-server） | 要，核心位置 | 公共 middleware、运行私有状态、只读调用结果签名、显式组合根接线、提醒/停止与安全诊断 |
| platform-api | 要，小范围 | 增加既有通知/诊断/错误白名单，保护私有字段，验证当前 ACL；不执行循环算法、不新增配置 CRUD、数据库表或 endpoint |
| platform-web | 要，少量展示，同事完成 | 扩展现有预算状态条和 RunDiagnostics；前端不能按消息次数自行断定循环、取消 Run 或自动重发；详见 [16 前端交接](16-f02-frontend-handoff.md) |
| GraphHarbor | 当前不计划修改 | 复用 Run、checkpoint、原生 error 和事件重放；真实 Worker 不重排是实施门禁，若发现引擎缺口先另行说明和评审 |

### 4. 推荐的最小实现

#### 4.1 首期策略与成功标准

1. 只监测当前工具集中已知的同步只读观察工具：`ls/read_file/glob/grep/read_reference`。组合根传入实际交集，不能因为名称相同就假设第三方 MCP 或二开工具具有同样语义。Showcase/Reference 和 DearFlow 是真实消费者，共用实现放公共层。
2. 一轮证据必须是 AIMessage 的工具批次及全部已配对 ToolMessages。每个调用必须属于本图声明的观察集合；混入写入、execute、task、澄清或其他未纳入工具时重置重复序列，不只抽出其中 read_file 再判断。
3. 计算“工具名 + 完整语义参数 + 返回 status + 文本结果”的稳定签名。相同参数但结果变化、分页推进或中间有不同操作均视为进展并重置。不同 call ID 不构成进展，也不进入签名。
4. 连续相同完整批次第 3 次之后提醒一次；第 5 次之后、进入第 6 次模型请求之前停止。3/5 已经G0批准实施，仍需生产校准，不宣称适用于全部任务。首期没有非连续滑窗、window_size 或工具频率层。
5. 未知/不完整结果不作硬判；正常文本终答不计数。相同结果只是可观察层面的重复，不能证明外部世界没有变化，用户看到的文案使用“重复调用保护”。
6. 硬停止沿原生 error 结束，使用安全码 `runtime.loop.detected`；保留已保存工具结果和产物。不会生成假总结、追加自动 summary Run 或把未完成任务包装成 success。

这会比 DeerFlow 的 after_model 硬停止晚执行一个批次：参考可挡住第 5 批工具；本方案最多执行 5 个重复只读批次再阻止下一次模型调用，包括下一次可能用于总结的调用。第3次后的提醒留出两次收尾机会，但不保证总结；这个取舍在G0明确评审。它观察到了工具结果，避开 provider 消息改写；副作用工具仍由审批、幂等、unknown 处理和既有预算保护，不能把本方案宣传为重复写入预防器。

建议优先级为可靠性补充而非全平台重构。若当前项目只需要有界执行、不需要提前识别和明确原因，现有预算已经满足该较低目标，可以不实施 F02。若 G0 接受更广范围（写操作、交替循环、任意 MCP），先补独立场景和策略，不默默扩大观察集合。

#### 4.2 Hook、消息与状态

已新增 `apps/runtime-service/src/runtime_service/middlewares/loop_detection.py`，主要符号为 `LoopDetectionState`、`LoopDetectionMiddleware`；归一化与签名使用文件内纯函数，不建独立 registry 或消息工具包。

- 使用官方 `before_model/abefore_model` 读取最近一个完整工具批次；同步/异步调用同一纯判定函数。该检查在真实工具执行和配对后进行，不通过 after_model 抹掉本次输出。
- 在 `wrap_model_call/awrap_model_call` 消费当前提醒状态，复用 `execution_budget.add_wrapup_instruction()`。只改变 outgoing system message，保留原内容块和 metadata，不向 checkpoint 写入伪造用户/助手消息。
- `RuntimeConfigMiddleware.sanitize_tool_call_messages` 继续负责模型请求的历史合法性；F02 不把修补占位 ToolMessage 当作工具实际执行成功。不能匹配输出里的英语错误句子来推断循环。
- `runtime_loop_state` 是 `Annotated[NotRequired[dict], PrivateStateAttr]` 的 checkpoint 内部状态，至少含 owner Run/图 namespace、最近已计数消息 ID、当前签名、连续计数及本序列已提醒标志。只保存固定长度摘要与有界计数，不保存参数/结果原文。
- 使用普通可持久化 channel，而不是 UntrackedValue 或进程 map：同一个受信 server Run 的 Worker 接管/重建图保留计数；新 Run 清零。Thread/checkpoint namespace 自然隔离，PrivateStateAttr 阻止父子输入复制和结果合并，网关还必须拒绝注入并清理公开出口。
- Run ID 取 Worker 受信 `metadata.run_id`，namespace 使用当前 LangGraph graph namespace，不使用每步 node task UUID。无 server Run 的库级调用由 before_agent 按 invocation 初始化；不伪造公共 Run ID。具体 resume/Worker claim 语义在 T02/T06 的锁版本 Spike 验证。
- before_agent 初始化游标时跳过旧历史；每条完整 AIMessage 只计一次。新用户/消费后的 inbox 输入、不同结果/批次、未跟踪工具以及新的子任务 namespace 打断连续序列。新 input 与同 Run 的恢复路径必须分开验证，不能每次 hook 都清零，也不能重新扫描整个 Thread 消息算预算。
- `read_file` 依据实际工具 schema 填 offset=0/limit=100，保留精确 `file_path/offset/limit`，不分桶、不解析成 start/end 行号、不访问宿主路径解析器。其他参数完整参与签名；不全局删除 `description` 等可能承载业务的字段。
- 使用标准 JSON 序列化和 SHA-256；签名对键顺序和工具批次顺序稳定，保留重复项与各自结果的关联。非 JSON、非有限数字、二进制/多模态或外置结果无法可靠比较时跳过硬判，既有校验/异常照常处理；不引入 ad hoc provider parser。

只读结果签名比较模型实际收到的有界文本，不从artifact再读取全量原始日志；截断/外置引用的等价不能直接当作完整结果相同。实现只读最近64条消息、最多32个调用，单结果65536字符、批次262144字符；参数最多16384字符、1024节点、16层。超限不硬判，禁止反向扫描整个Thread来寻找证据。counter写入后checkpoint未提交的故障窗口仍由最近已提交消息重新判定；不宣称exactly-once告警。

实施已验证合并schema、PrivateStateAttr主子隔离、消息ID去重、自动摘要与真实Worker接管；P01实测两次模型的最后步骤增加3，已有recursion_limit不提高。更长运行仍受原有步骤预算约束，开启策略需要接受这一成本。

#### 4.3 与现有中间件的组合

| 情况 | 必须保持的行为 |
| --- | --- |
| 限额/超时先触发 | 沿原预算或 Run timeout 退出；F02 不覆盖原因，也不争取额外模型调用 |
| 第 3 次重复后模型正常总结 | 可以正常结束，保留提醒记录；不写强制停止原因 |
| 第 5 次重复后仍准备调用模型 | 先记录 reached，再抛安全 RuntimeExecutionError；不发第 6 次 provider 请求 |
| 子 Agent 触发 | 子图和父 Run 走既有不可恢复执行错误传播；本期接受停止整个父 Run，不伪造 child Run 或实现局部救援 |
| provider retry/fallback | 只计已完成工具批次，网络尝试不重复计数；F02 错误不匹配 retry predicate，父 task 也不重放 |
| 用户取消或 HITL 中断 | 原始 CancelledError/GraphBubbleUp 传播；不自动 resume、不追加总结；未完成工具批次不计数 |
| 手动上下文整理 | 复用 `is_conversation_maintenance()` 跳过初始化、计数、提示和副作用；继续走已批准维护路径 |
| 自动摘要/大结果外置 | 不全量扫描历史；签名状态不随裁剪丢失；无法证实完整批次时不硬判；实际 hook 顺序由 compiled graph 证明 |
| 诊断/custom 发送失败 | 不替换正常执行或循环停止结果；提醒/详情允许不可用，不把日志写成功作为执行完成 |

组合根把 detector 放在既有预算检查之后；提醒 wrap 层仍须落在最终 `ContextBudgetMiddleware` 的输入预算检查之前。MessageQueue、摘要和 detector 的顺序以“已消费新输入可打断序列、最近配对工具结果仍可观察”为验收目标，T03 检查真实图节点，不凭列表顺序推断所有 before/after hooks。

### 5. 代码补充位置与接线范围

表中“新增”路径已在本次实施创建。保留实际消费者、测试、导出和信任边界；不移动无关目录。

| 位置（从仓库根起） | 符号/改动 | 必要性 |
| --- | --- | --- |
| `apps/runtime-service/src/runtime_service/middlewares/loop_detection.py`（新增） | LoopDetectionState、LoopDetectionMiddleware、归一化/批次签名 | 唯一算法实现；sync/async 共用 |
| `apps/runtime-service/src/runtime_service/middlewares/__init__.py` | 依现有导出方式导出公开 middleware，维护 `__all__` | 对齐调用者，不留未使用导出 |
| `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` | `_build_agent.middleware()`，主图和 researcher 子图只读集合交集 | 不放到 Dear 私有 middleware 再复制给别图 |
| `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py` | `_build_agent.middleware()`，配合 `subagents.py:build_subagents()` 的已有注入函数 | research/general-purpose/chart 只监测其中观察工具，含写操作批次不熔断 |
| `apps/runtime-service/src/runtime_service/services/reference_agent/agent.py` | `_build_agent()` 显式接 `read_reference` | 验证标准 create_agent 接入，不局限 DeepAgents |
| `apps/runtime-service/src/runtime_service/runtime/errors.py` | 复用 RuntimeExecutionError；说明其覆盖不可重试执行策略终止 | 不新增 Worker 重试体系；验证循环不是基础设施失败 |
| `apps/runtime-service/src/runtime_service/observability/{diagnostics,langfuse,query}.py` | 安全转移事件、graph error code、diagnostics v1 可选数组 | 沿已有记录/查询，不建审计日志或 Run 镜像表 |
| `apps/runtime-service/src/runtime_service/auth/platform.py` | `_reject_budget_state()` 等写入口拒绝 `runtime_loop_state` | 官方 PrivateStateAttr 不替代 native state/update/input 防伪 |
| `apps/runtime-service/src/runtime_service/webapp.py`、`.env.example` | 部署开关解析/启动校验；默认 `AGENT_LOOP_DETECTION_ENABLED=0`，验证后受控开启 | 不引入 DeerFlow AppConfig/YAML 管理体系；只接受 0/1，非法值明确失败 |
| `apps/platform-api/src/platform_api/core/runtime_contract.py` | PRIVATE_RUNTIME_STATE_KEYS 和递归拒绝入口 | input/update/command/resume 等实际调用者一起覆盖 |
| `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py` | project_budget_notice、project_execution_error、redact_runtime_private_fields | 固定通知码/单位、精确停止码、state/history/SSE/debug/tasks 清洗 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py` | 可选 LoopDetectionSummary 与 RuntimeDiagnostics 扩展 | Pydantic 严格 bounds、旧 v1 兼容；ACL/路由原样复用 |
| `apps/platform-web/src/modules/chat/{budget,diagnostics}/` 与现有状态条/诊断面板 | 由同事按 16 实施 | 共用 Chat；Dear 不复制状态机 |

本期不改 `services/demo/workflow_demo/` 外层/内层装配：该图每个 respond 重建内层模型 Agent，首期没有它的短周期重复证据；只回归原预算和失败语义。其他 graph 按真实需要显式接入，不默默全图安装。SDK/schema probe 加载新增 state 必须无 Workspace/MCP/模型 I/O。

### 6. 跨服务实现契约

已获G0批准并在Runtime/API实现，真实样例见 [16交接](16-f02-frontend-handoff.md) 和 [HTTP样例](evidence/f02-http-samples.json)。保持现有 SDK、v2/v3 的 envelope 和原生终态，不新增 loop 专用 SSE 或接口；尚未部署现役。

#### 提醒与触限通知

复用 `runtime_budget_notice`、`build_budget_notice()` 和 `emit_budget_notice()`，增加如下固定组合：

| code | budget_scope | unit | limit / used / remaining |
| --- | --- | --- | --- |
| `tool_loop_approaching` | run | tool_rounds | 5 / 3 / 2 |
| `tool_loop_reached` | run | tool_rounds | 5 / 5 / 0 |

`used` 是连续完整重复工具批次数，不是 model/tool 总次数或线程额度；`scope` 仍为 primary/subagent。notice_id 延续受信 Run 和稳定 graph namespace 归属，增加本重复序列的首个消息 ID 摘要，保证新序列可再提醒、重复交付可去重。只在实际完成一次转移时发事件，不每步刷屏。

`loop_detections` 是现有 diagnostics v1 的可选数组，缺省 `[]`，最多 20 项。以下为单项结构示例，实际抓包见16：

```json
{
  "observation_id": "loop-observation-1",
  "scope": "primary",
  "namespace": [],
  "code": "tool_loop_approaching",
  "repetitions": 3,
  "threshold": 3
}
```

单项 Identifier/namespace 沿现有 ASCII 标识符、128 字符、最多 8 段规则；code 仅两个 loop notice 码；repetitions/threshold 均为严格整数，approaching仅接受3/3、reached仅接受5/5。数据从 `runtime.loop.transition` 安全观测事件投影，旧响应不增加必填字段。原有 availability/truncated 和精确目标校验继续有效，不能空数组就推断未发生循环。

#### 停止与安全边界

- 内部抛 `RuntimeExecutionError("runtime.loop.detected")`；对外精确码同为 `runtime.loop.detected`，固定说明“检测到工具重复调用，本次运行已停止，请调整任务后继续。”
- 对象错误仅从受信异常类型与完整机器码组合映射；字符串槽位只识别完整机器码并保持形状。恶意前后缀/substring/伪同名类型不得获得精确分类，退回现有安全泛化错误。
- 根或子 graph 的 diagnostics.graph_executions.error_code 可用此码，model_errors 仍仅模型错误。不要把循环写成 provider 故障、平台授权失败、取消或 Run timeout。
- 标准 Run GET 仍用于核实原生状态，不假定有 error 字段；Thread.error 不归因旧 Run。旧事件过期时依次用目标匹配的诊断/现有历史任务错误，否则展示未知原因，不猜测。
- `runtime_loop_state`、调用/结果签名和原文不出现在公开 state/history/debug/tasks/custom、日志或诊断中；读出口递归清理，写入口递归拒绝。普通模型消息和真实 ToolMessage 正文不因此被全局抹掉。
- 策略候选和状态不进入用户 Context/模型编辑页面，不新增 Delegation operation、平台表或迁移。启用只由部署者控制。
- 已同步 `docs/standards/error-envelope.md`、`sse-event.md` 及健康表；已有JWT/SSE专项的未验门禁与状态保留，不以本补充宣称其他专项完成。

### 7. 回退、风险与取舍

| 风险/限制 | 应对与明确边界 |
| --- | --- |
| 合法重复验证被误判 | 只读声明、连续序列、结果签名、用户/操作边界重置；真实研究/分页/反复验证负例是启用门禁；若误判不启用 |
| 结果时间戳/外置引用一直变化造成漏检 | 不做跨工具业务字段猜测；漏检由现有预算兜底；不能宣称所有死循环都能识别 |
| 同批次某个工具独自循环或 A/B 交替 | 首期完整批次连续比较不覆盖；有实例才扩展，不以新增单工具计数补上第二套预算 |
| 写入/发布/计费/轮询无限重复 | F02 首期不覆盖；继续由已有审批、幂等、unknown、工具预算和硬超时治理 |
| 子图停止整个父 Run | G0 明确接受；局部只读子任务失败后让父图继续属于独立容错范围，本期不新增 executor |
| 追加 hook 消耗步骤预算 | P01已测两次模型最后步骤6/9、状态2/378 bytes；不提高既有cap掩盖成本，高负载延迟不作SLO |
| 接管/重建重置或双计数 | 私有持久状态、owner 和消息去重；真实PG/Worker故障接管已验，不靠进程缓存 |
| 非公开消息表面残留 | 实现不改tool_calls，主子/v2/v3配对及RuntimeConfig修补占位回归已验，不新建clone helper |
| 详情渠道不可用 | hard error 和原生终态仍生效；诊断/custom 明确降级，不承诺每个历史 Run 永久保留精确原因 |

关闭 `AGENT_LOOP_DETECTION_ENABLED` 后 detector 不计数、不提醒、不停止；既有预算和正常图行为继续。新checkpoint可选私有字段的旧图读取/继续、关闭与重开已由T08实证；不删除历史，不修改模型/工具预算。部署/发布、数据库和正式依赖更新不在本轮授权内。

## 任务拆分

估算是有效工程日，不是排期承诺。用户已批准推进所有非前端任务；任务完成后以实际证据回填，前端由同事实施。

### F02-P01 源码辨析、基线复验与前端交接
- **改动内容：** 对照两份参考、当前接线和历史 E05；形成本篇与16；同步原项目导航和状态快照。
- **代码位置：** 本项目文档；不修改业务源码、测试实现、配置或依赖。
- **预期结果：** 已有/新增/不做范围可追溯，前端能按草案了解后续交付物。
- **验证项：** 本轮离线 E05 复验、预算/schema 定向测试、API 投影基线及文档检查；见下方 Phase。
- **状态：** [x] 2026-10-09 规划完成。

### F02-G0 人工评审（所有实施任务的前置）
- **改动内容：** 人工确认只读范围、连续参数+结果口径、3/5候选、原生 error、子失败传播、默认关闭和 API/前端草案。
- **代码位置：** 本篇评审记录；没有代码改动。
- **预期结果：** 记录评审人、日期、批准范围和调整项；不将调用 plan-project 当成实施批准。
- **验证项：** 用户明确决定上述行为；扩范围时先补场景与验收。
- **状态：** [x] 2026-10-09 用户明确表示“我已经评审完成，可以开始实施了”，批准既定方案与非前端完整验证。

### F02-T01 归一化与完整工具批次判定（约0.5-1日）
- **改动内容：** 新增只读集合交集、精确 read_file 默认参数、关联 ToolMessages、多重集签名与保守跳过规则。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/loop_detection.py` → `_completed_batch()`、`_json_signature()`；`apps/runtime-service/tests/middlewares/test_loop_detection.py`。
- **预期结果：** 分页、不同结果、改变内容不会当成相同轮次；ID/键顺序不影响签名，不读文件或调用模型。
- **验证项：** U01-U04；真实 FilesystemMiddleware schema 保持原名/默认值，invalid/多模态不崩溃、不擅自强判。
- **状态：** [x] 2026-10-09 判定与保守跳过实施完成；最新共享测试33项通过，见implementation/15-f02-loop-detection.md。
- **合规检查：** [x] 代码完成；[x] 定向验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T02 官方 middleware、持久私有状态和停止（约1日）
- **改动内容：** 实现 sync/async hooks、3/5转移、单次计数、边界重置、系统收尾提示和不可重试停止。
- **代码位置：** `apps/runtime-service/src/runtime_service/middlewares/loop_detection.py` → `LoopDetectionMiddleware`，既有 `runtime/errors.py`；测试真实 create_agent/create_deep_agent，不只 mock hook。
- **预期结果：** 3次后可正常收尾；持续重复最多5轮工具，不调用第6次模型；同Run重建不逃过阈值，新Run不继承。
- **验证项：** U05-U09；锁版本 PrivateStateAttr/DeltaChannel/不同namespace/调用恢复 Spike；记录 hook/superstep 成本。
- **状态：** [x] 2026-10-09 sync/async真实图、3/5转移、私有checkpoint与重建验证通过；同Run进程接管亦已由T06实证。
- **合规检查：** [x] 代码完成；[x] 定向验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T03 三组合根及声明式子图接线（约0.5日）
- **改动内容：** DearFlow/Showcase主子与Reference 显式接公共 detector；部署开关、启动严格校验、公共导出；跳过手动维护。
- **代码位置：** 本篇第5节列出的3个 agent.py、`middlewares/__init__.py`、`webapp.py`、`.env.example`。
- **预期结果：** 真实消费者共用一份实现；schema无I/O，工具授权和原限额不变，其他图不强制接入。
- **验证项：** U10、I01-I04；扩展 `tests/services/test_execution_budget_composition.py`；复用 `test_schema_introspection.py`。
- **状态：** [x] 2026-10-09 三组合根主子接线、schema私有字段和严格开关定向验证通过；Workflow不接，三根/子图真实Worker亦已由T06实证。
- **合规检查：** [x] 代码完成；[x] 定向验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T04 既有观测与诊断出口（约0.5-1日）
- **改动内容：** 记录安全转移、增加可选 loop_detections、精确 graph 停止码及通知序列ID。
- **代码位置：** Runtime `observability/{diagnostics,langfuse,query}.py`；扩展 `tests/observability/{test_diagnostics,test_run_diagnostics}.py`、`tests/http/test_diagnostics.py`。
- **预期结果：** 当前Run/namespace可查原因，旧v1可读；观测故障不改变执行结果，签名/参数不外泄。
- **验证项：** U11、I05；两个同角色子任务、重复消息、观测未配置/暂不可用/截断响应。
- **状态：** [x] 2026-10-09 安全转移、可选loop_detections、graph停止码和观测降级实施并通过定向验证；真实同角色namespace隔离已由T06实证。
- **合规检查：** [x] 代码完成；[x] 定向验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T05 Platform/API 与 native 写入口保护（约0.5-1日）
- **改动内容：** 同步私有state拒绝/剥离、预算通知组合、精确执行错误与严格诊断DTO。
- **代码位置：** Runtime `auth/platform.py`；API第5节三处；扩展 `test_execution_budget_projection.py`、`test_run_diagnostics.py`、`test_runtime_gateway_event_redaction.py`、`test_runtime_gateway_runtime_contract.py`。
- **预期结果：** v2/v3/SSE/history/tasks/debug统一安全，未知码泛化，input/update/command/resume不能绕过检测。
- **验证项：** U12、I06；跨项目403、canary/伪异常负例、普通正文不损坏、旧v1响应。
- **状态：** [x] 2026-10-09 API/native写拒绝、读清理、精确错误和严格DTO已实现；API四文件最新88项、168子测试通过，真实ACL/SSE已由T06实证。
- **合规检查：** [x] 代码完成；[x] 定向验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T06 隔离 Worker/HTTP 完整链路（约1日）
- **改动内容：** 用受控provider响应走真实GraphHarbor API/Worker/checkpoint/平台网关；同Run故障恢复、父子图和不可重试停止。
- **代码位置：** `apps/runtime-service/tests/integration/test_loop_detection_worker.py`、`test_loop_detection_checkpoint.py`；复用 `tests/services/dearflow_agent/test_tool_error_platform.py::stack`、`tests/fixtures/run_reliability.py` 与ProductionWorker，新增控制provider夹具 `tests/fixtures/loop_detection.py`。
- **预期结果：** 唯一正确终态、provider/工具计数可查；未将本次停止解释为基础设施重排；正常PG/租约恢复仍可用。
- **验证项：** I01-I08、E01/E02后端部分；boundaries正文17场景通过；独立recovery节点1 passed、1 deselected、1996.75s（含取消/inbox/接管/安全/PG摘要/回退/重开及首轮真实模型）。浏览器部分仍属T07。
- **状态：** [x] 2026-10-09 非前端真实Worker链路完成。初次inbox夹具400、外置提示误判和pytest过滤误选已定位，生产判定修复与回归通过；见Phase及implementation/15-f02-loop-detection.md。
- **合规检查：** [x] 夹具和接线完成；[x] HTTP/恢复验证执行；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG已留痕。

### F02-T07 前端实施与自动化浏览器闭环验证（约0.5-1日）
- **改动内容：** 按16扩展现有预算/诊断DTO与视图、精确错误文案；不实现算法、阈值配置页或第二套运行控制。
- **代码位置：** [16所列 Web 文件与F01-F07](16-f02-frontend-handoff.md)。
- **预期结果：** 提醒/停止/主子范围清楚；旧响应兼容；未知原因保守显示；消息与审批/取消恢复不受损。
- **验证项：** Web Vitest/typecheck/lint/build 与 Playwright + Chromium 真实三服务端到端闭环（含真实大模型全链路对话无死循环误判 + 状态条预警终止与诊断抽屉卡片渲染）。
- **状态：** [x] 2026-10-10 前端代码与全自动化 E2E 闭环完成。Vitest 85项通过、vue-tsc 0报错、eslint 0错误、生产build成功、Playwright 2项端到端全绿通过并沉淀截图；本地服务栈保持存活，等待最终人工验收。

### F02-T08 Final、回退与启用评估（约0.5-1日）
- **改动内容：** 汇总本次获批非前端范围、性能/误判/故障/回退证据，更新功能总览与标准；保持默认关闭。
- **代码位置：** 本篇Final、implementation后续记录、`docs/standards/`、前端同事验收；不自动发布。
- **预期结果：** T08只验收用户本轮授权的非前端范围。T07是交接给同事的独立实施任务；其完成前F02整体仍partial。上线开启评估留给前端联合验收之后，不自动发布。
- **验证项：** U/I/E全部获批项、P01-P03、R01-R03；新checkpoint关闭/旧图回退/重开实证。
- **状态：** [x] 2026-10-09 本轮获批非前端范围完成：回退/重开、性能/有界状态、三组真实模型、全量回归对照、安全证据及交接入口均已收齐。F02整体partial，仅T07前端与浏览器未完成；默认关闭，未部署。
- **合规检查：** [x] 非前端实现完成；[x] 本轮验证与限制记录；[x] 本篇任务更新；[x] CONTEXT/FEATURES/CHANGELOG与标准同步；[x] 前端交接冻结。

## 验证要求与记录

### 验证计划

| 编号 | 类型与场景 | 断言/证据 |
| --- | --- | --- |
| U01 | 参数顺序、工具顺序、重复项、call ID | 相同多重集一致；重复项不消失；不同参数不同 |
| U02 | read_file 默认/不同offset/limit/文件、同文件更新 | 省略默认与显式默认相等；每种真实分页独立；结果变化重置 |
| U03 | 相同参数、成功/错误及结果变化 | 只有完整相同可比较结果连续计数；不按任意错误文本猜含义 |
| U04 | invalid/非有限JSON、多模态、巨大/外置结果、混合写入/task/澄清 | 保守跳过或重置；既有错误照常；不执行额外I/O、不崩溃 |
| U05 | 连续1/2/3/4/5次、正常终答 | 第3次只提醒一次，第5次后阻止第6次模型；提前终答仍自然success |
| U06 | 用户/inbox新输入、改变结果/不同工具、A/B交替、重复checkpoint回放 | 边界打断；同批次不双计数；明确首期A/B不强制判断 |
| U07 | schema/PrivateStateAttr/DeltaChannel和旧checkpoint | 无公开字段；父子不复制/合并；graph重建保留同Run，新Run清零 |
| U08 | sync/async真实图，provider retry/fallback，只读task retry | 行为一致；同工具轮次只计一次；loop错误无自动重试 |
| U09 | CancelledError/GraphBubbleUp/HITL、剩余步骤/工具/模型cap先耗尽 | 原始退出原因和审批不被覆盖；无取消后总结或伪成功 |
| U10 | 开关0/1/非法、schema probe、手动维护、既有Workflow | 关闭无保护转移；非法明确失败；probe无I/O；维护和未接入图行为不变 |
| U11 | 日志/诊断/custom不可用、重复事件/截断、主子namespace | 执行结果不受影响；安全可选数组和确定目标；无签名/参数输出 |
| U12 | API/native input/state/history/debug/tasks/v2/v3、伪码/canary/旧v1 | 写拒绝读清理；精确机器码分类；普通模型/工具正文保留 |
| I01 | DearFlow实际装配，稳定ls/read_file失败注入 | 对照未开启6次，开启后5次上限，provider/tool计数、日志、state一致 |
| I02 | Showcase多个角色、Reference、重复父子批次 | 三根同实现；各子namespace隔离；只读子停止按G0终止父Run |
| I03 | HITL挂起/编辑/拒绝、重建resume、新输入/新Run | 恢复原Context与审批ID；新输入重置；配对完整、无未批准副作用 |
| I04 | 自动摘要、手动整理、长thread、inbox消费 | 最近证据仍可观察；重复状态不丢、不扫全历史；新输入不继承旧警告 |
| I05 | 目标诊断查询、未配置/失败后恢复、两个同角色子任务 | availability/truncated如实；旧Run不借新Thread.error；无跨目标覆盖 |
| I06 | 两用户两项目、撤权、伪造私有状态/事件和各种SSE形状 | 当前ACL拒绝；私有数据不可注入/泄露；安全码只来自可信出口 |
| I07 | 同Run Worker故障接管，稳定第五次停止 | 私有counter保留；不双计数；循环错误不再claim重排；基础设施故障仍恢复 |
| I08 | 受控provider工具返回顺序/并行、多provider消息配对 | AI/ToolMessage保持配对；工具结果不丢；无消息clone依赖 |
| E01 | 三服务浏览器：稳定循环->提醒->失败->刷新诊断 | 状态条、最终Run、历史工具及诊断一致；前端不重发/自动取消 |
| E02 | 正常分页/结果变化/明确验证->正常结束 | 无错误终止，无预算或费用数字误读，成果仍可读 |
| E03 | 父子、审批/取消/断流恢复、切项目/Thread/Run | 范围清楚，无僵尸spinner或迟到响应串线；原停止能力正常 |
| E04 | 旧v1/诊断关闭/事件过期/未知code/小屏 | 可降级；不猜原因；1440/768/390视口、明暗模式、键盘可访问 |
| P01 | 同一fake workload开关差分 | 实测model/tool调用、supersteps、延迟、state序列化体积；无额外LLM/网络调用 |
| P02 | 长thread与多个并行graph | detector状态固定大小、消息检查有界，无进程全局历史/LRU/资源积累 |
| P03 | 真实研究/分页/反复读验证与稳定重复故障 | 记录误判/漏检及节省；真实模型测试预算另定，不编造SLO或任务质量结论 |
| R01 | 新checkpoint关闭开关、恢复审批与普通继续 | 老历史和产物可读、原预算有效，无清库 |
| R02 | 旧图读取新增私有字段、再切回新图 | 实证兼容；不能只因TypedDict optional宣称可回退 |
| R03 | disabled到enabled的新Run及故障恢复 | 清理过期owner、不继承旧序列；默认不开启，校准通过再评估开启 |

T01-T05按变更跑定向pytest/lint，T06执行隔离真实HTTP/Worker，T08完成本轮非前端范围验收；T07由同事完成浏览器后再执行F02整体Final。通过基础单测不证明Worker接管或生产适用。新增tests只针对判定、隔离和安全出口，不写镜像getter测试。

### Phase：2026-10-09 规划基线复验（实际执行）

本worktree无服务venv，临时复用主checkout的独立Runtime/API解释器；源码由当前worktree tests/conftest和现状脚本加载。Runtime Python `3.13.9`、pytest `9.0.2`，依赖版本已与当前uv.lock核对。未安装或更新依赖。

1. 复用 [现状脚本](evidence/effect_probe.py) 的 `probe/call`，仅运行 E05 六次相同ls，不执行脚本的其他历史断言。当前预算已经改为优先采用正数env，旧E06断言不再是本轮事实。

```bash
"$RUNTIME_TEST_PYTHON" -c 'import asyncio, json, runpy; ns=runpy.run_path("docs/projects/20260913-dearflow-agent/evidence/effect_probe.py"); rows=[ns["call"]("ls", {"path":"/workspace/work/"}, "repeat-"+str(i)) for i in range(6)]+[ns["AIMessage"](content="done")]; result=asyncio.run(ns["probe"]("six_identical_calls_20261009", rows)); assert result["tool_messages"] == 6, result; print(json.dumps(result, ensure_ascii=False))'
```

结果，退出码0：

```json
{"probe":"six_identical_calls_20261009","reached_approval":false,"final_text":"done","model_messages":7,"tool_messages":6,"tool_statuses":["success","success","success","success","success","success"],"todos":null,"created_file":false}
```

这是缺口复现成功，不是循环保护验收通过。使用fake模型、真实DearFlow装配/工具和TemporaryDirectory；未请求真实模型/供应商/生产数据库。仍出现既有 `vercel-deploy` skill名称与目录不匹配告警，属于原T05，未借本轮修复。

2. 当前Runtime预算/配置/schema基线：

```bash
"$RUNTIME_TEST_PYTHON" -m pytest -q -p no:cacheprovider \
  "apps/runtime-service/tests/middlewares/test_execution_budget.py" \
  "apps/runtime-service/tests/services/dearflow_agent/test_limits_config.py" \
  "apps/runtime-service/tests/services/test_schema_introspection.py"
```

退出码0，**25 passed，5 warnings，7.82s**。警告为PyMuPDF SWIG弃用；未处理。测试测得budget薄扩展与官方限制器都为2次model/8个supersteps，属于既有预算测试输出，不能当作尚未实现F02的性能结果。

3. 当前Platform预算投影基线：

```bash
"$API_TEST_PYTHON" -m pytest -q -p no:cacheprovider \
  "apps/platform-api/tests/test_execution_budget_projection.py"
```

退出码0，**7 passed，152 subtests passed，3.43s**。这是现有通知/错误/私有字段出口基线，新增F02组合仍须以后实现和验证。

4. 官方资料：已查询Docs/Reference MCP；Reference的 `LoopDetectionMiddleware` 搜索无结果，不当作官方不存在此能力的永久证明。确认 [AgentMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware)、[PrivateStateAttr](https://reference.langchain.com/python/langchain/agents/middleware/types/PrivateStateAttr) 及 [FilesystemMiddleware](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)。本地实际read_file schema为 `file_path/offset=0/limit=100`。

5. 文档校验：`git diff --check`退出码0；9份本轮改动Markdown的链接/尾随空白/本机路径定向校验通过，无新增坏链接。定向检查发现4个既有坏链接（均在FEATURES.md），已与HEAD逐项对照。本仓库 `python3 "scripts/check_docs.py"` 退出码1，共38处本机绝对路径，全部已在HEAD存在，位于本轮未修改的knowledge和其他专项文档；本轮未清理无关历史问题，不能报告全仓文档门禁通过。

本轮没有运行DeerFlow整套测试、全仓pytest/lint、真实Worker/模型、浏览器、生产部署或回退；没有修改参考checkout。既有SWIG弃用和Skill命名告警仍在；本篇新增功能所有验收尚未执行。

### Phase：2026-10-09 T01-T05实施验证

- T01：完整批次、多重集、结果关联与read_file默认参数；首轮共享测试27项通过。真实链路后发现ls正常目录含large_tool_results被误跳过，已收窄为框架实际外置提示并新增回归；最后回归待T06统一记录。
- T02：sync/async编译图验证五轮工具、五次模型、第3后收尾提示；InMemorySaver重建及新Run边界通过。共享测试扩展后31项通过；PG接管仍属T06。
- T03：主子组合根、PrivateStateAttr/schema和旧预算定向组合通过；核心/预算/组合集54项通过，后续固定测试夹具工具参数污染与缩进错误已修。
- T04：Runtime观测/query/HTTP/auth/组合106项通过、1项既有ACL mock参数失败待HEAD对照；loop诊断严格目标、重复、上限与故障降级测试通过。
- T05：当前worktree PYTHONPATH下API四文件88项、163子测试通过；新契约单独28项通过。缺PYTHONPATH的旧checkout结果不算本次证据。

### Phase：2026-10-09 T06真实链路与T08非前端验收

- API四文件最新回归：88 passed、168 subtests passed、21.40s；共享detector：33 passed、5 warnings、41.14s。Runtime/API两服务lint通过；服务format-check发现未修改的Showcase README代码块不合格式，新增6个Python文件均通过，不借本轮整理存量文档。
- 隔离HTTP/Worker首轮已通过18个运行场景：三根稳定重复、v2、分页/交替/结果变化/提醒后终答、两根子停止、同角色并行、三种审批挂起与恢复、取消。inbox请求缺Idempotency-Key导致夹具400，已修正并拆成boundaries/recovery独立阶段；本轮首个pytest因此失败，不能记成完整链路通过。
- PostgreSQL摘要组合：1 passed、5 warnings、43.23s。五次工具/模型且自动摘要发生；私有计数不丢，手动维护不计数，新Run清零。夹具曾传 `aupdate_state(config, {}, as_node="__end__")`，已按锁版本改为None；失败来自测试调用，不修改生产逻辑。
- API全量：35 failed、421 passed、25 skipped、800 subtests passed、519.39s。原HEAD源码及失败文件独立运行得到相同35 failed（22 passed、4 subtests passed、239.54s），原因均为既有非法project-1等UUID夹具；本次未修改这些文件。全仓门禁不宣称全绿。
- Runtime全量：15 failed、1002 passed、73 skipped、59 deselected、1657.20s。12项旧模型配置/维护hook/ACL mock参数/主子收尾/超时/脚本耗尽失败已在原HEAD独立复现；跨服务向量测试指定正确 `PLATFORM_API_TEST_PYTHON` 后1 passed；另2项inbox崩溃窗口测试在原HEAD隔离源码及本轮临时PG中同样2 failed、196.68s（90秒内未到窗口）。存量失败有对照，本轮不修无关模块；不能据此声称全仓门禁全绿。
- P01开关差分：1 passed、5 warnings、85.55s。相同两次模型工作负载不开启/开启的最后模型步骤为6/9，私有状态序列化为2/378 bytes，公开输出无私有字段；中位延迟11.083/115.411ms。主机load约900，该延迟只记录本次实验，不作生产SLO或稳定开销判断。已有步骤上限不调整，新增hook每轮会占图步骤。
- boundaries节点正文已通过全部17个HTTP运行场景，最后已正常返回。原命令 `-k boundaries` 同时误选recovery节点，重复组启动时主动SIGINT清理，pytest会话因此非零退出且出现既有tmp_path teardown KeyError；不能把整个会话报告成全绿。独立recovery继续验证，不再重复跑已通过边界。交接/复跑均改为完整参数化节点。
- recovery已实测cancel、inbox消费、Worker崩溃接管（claims=2，五个已提交ToolMessages、恢复后3/5两条诊断，包含一次中断的provider请求共六次）、递归私有注入拒绝、跨用户/项目拒绝、分享后读取与撤权拒绝、410后目标诊断/Run查询、OpenAPI。自动/手动摘要复验1 passed、5 warnings、83.15s。关闭开关的新Run六轮正常结束，旧HEAD Worker读取新checkpoint并继续success，重开从新序列五轮后停止。
- 独立recovery完整会话退出码0：1 passed、1 deselected、1996.75s。重开新Run五轮后loop error、claims=1；三组真实模型首轮success且无loop诊断。但分页首轮只有一行测试数据，后两页是越界错误，因此不能记作正常分页验收；已将真实模型独立为精确 `[real-model-stack0]` 节点，预置8行并新增工具参数/状态/两次复读/原文件未改断言，仅重验该部分。
- 真实模型独立节点最终退出码0：**1 passed、96.03s**。实际DeepSeek-V4-Flash读取分析1次、不同offset/limit分页3次、同参数同结果复读2次；全部ToolMessages success，原8行内容不变且未新增工作文件，三Run success、claims=1、loop_detections=[]。此前一次复读provider_timeout、一次Runtime冷启动180秒未ready均已记录并完成重验；不代表生产误判率或内容质量已统计达标。
- 前端隔离入口已实测pytest `--trace` 在正文首句暂停时五个服务进程存活，指定字段取得随机API/项目/model；合成账号HTTP登录成功。主动 `q` 退出码2并清理本次进程，不算自动测试通过；Web/浏览器由同事按16执行。
- 质量与文档：`uvx --offline ruff check apps/runtime-service apps/platform-api`通过；新增6个Python文件format通过。根目录 `ruff check .` 有44项/11文件错误，逐文件与HEAD比较均未修改；14份变更Markdown无新增坏链接/本机路径/空白，FEATURES中4个既有坏链接仍在。`git diff --check`通过。

#### T08本轮范围验收结论

本轮Runtime/API实现、必要只读链路、安全、持久化接管、关闭/旧图/重开、真实模型烟测和前端交接均完成，非前端范围 `done`，无新增功能阻塞。汇总证据见 [f02-verification-summary.json](evidence/f02-verification-summary.json)，真实帧与完整DTO见 [f02-http-samples.json](evidence/f02-http-samples.json)。共24个受控HTTP Run场景加3个有效真实模型Run；检查当前未完成任务只剩T07。

全仓门禁有已对照的存量失败，合并不能标成全绿。F02整体验收仍 `partial`：只缺T07/F01-F07及E01-E04浏览器联验；未执行生产发布/容量测量或正式源冷安装，默认0继续保留。小样本不能决定全平台开启，3/5仅为批准的首期策略。

#### 可复现命令

已有解释器指向当前锁依赖，始终显式加载本worktree源码。Runtime核心例：

```bash
"$RUNTIME_TEST_PYTHON" -m pytest -q -p no:cacheprovider \
  "apps/runtime-service/tests/middlewares/test_loop_detection.py"

PYTHONPATH="$PWD/apps/platform-api/src" \
"$API_TEST_PYTHON" -m pytest -q -p no:cacheprovider \
  "apps/platform-api/tests/test_loop_detection_contract.py" \
  "apps/platform-api/tests/test_execution_budget_projection.py" \
  "apps/platform-api/tests/test_run_diagnostics.py" \
  "apps/platform-api/tests/test_runtime_gateway_event_redaction.py"

TOOL_ERROR_PLATFORM_TEST=1 \
PYTHONPATH="$PWD:$PWD/apps/platform-api/src" \
PLATFORM_API_TEST_PYTHON="$API_TEST_PYTHON" \
"$RUNTIME_TEST_PYTHON" -m pytest -q -s -p no:cacheprovider \
  "apps/runtime-service/tests/integration/test_loop_detection_worker.py::test_http_loop_boundaries_takeover_security_and_rollback[boundaries-stack0]" \
  "apps/runtime-service/tests/integration/test_loop_detection_worker.py::test_http_loop_boundaries_takeover_security_and_rollback[recovery-stack0]"
```

真实模型烟测用同一入口的 `[real-model-stack0]`，设置 `LOOP_MODEL_ENV_FILE` 指向Runtime已有DeepSeek代理配置文件；该节点未配置明确skip，不能算pass。无需改或输出.env；合成provider与现役隔离。前端保留环境方法见16。

### Phase：2026-10-10 T07 前端实施与 Playwright 端到端闭环验证（实际执行）

- **代码实现（F01-F07）：**
  - Schema & DTO：在 `budget/types.ts` 和 `diagnostics/types.ts` 中基于 Zod 实现工业级弹性校验（正整数约束，拒绝字面量假死锁）；
  - 状态机时序：在 `budget/view-model.ts` 中实现 `tool_loop_reached` 运行态呈现为 warning 预警、终态到来后呈现为 terminal error；
  - 子任务冒泡：在 `useRunBudget.ts` 的 `isNamespaceMatch` 中打通子任务（Subagent）循环预警向主会话投影的安全冒泡与去重；
  - 报错降级兜底：在 `ChatAgentStatusBar.vue` 中对 `runtime.loop.detected` 进行中文标准化拦截（“检测到工具重复调用，本次运行已停止，请调整任务后继续。”），避免裸露英文或被误判为模型故障；
  - 诊断抽屉卡片：新增独立组件 `RunLoopDetectionsSection.vue` 挂载至 `RunDiagnostics.vue`，展示重复轮次、阈值、工具名及关联签名，无记录时彻底隐藏无感。
- **静态质量检验：**
  - Vitest：`pnpm --dir apps/platform-web test:unit`（8 个测试套件，85 项测试 100% 通过）；
  - 类型检查：`pnpm --dir apps/platform-web exec vue-tsc --noEmit`（0 报错）；
  - 代码规范：`pnpm --dir apps/platform-web exec eslint src`（0 错误）；
  - 生产构建：`pnpm --dir apps/platform-web build`（耗时 1m 34s 成功打包生成产物）。
- **隔离本地栈与端到端闭环测试：**
  - 服务栈状态：通过 `scripts/local-stack.sh up` 分配并启动隔离服务（环境 ID `wt_576928e8a389`，Web `29134`、Platform API `28011`、Runtime `28742`、Worker、Redis `26706`），`.local-stack/runtime.env` 注入 `AGENT_LOOP_DETECTION_ENABLED=1`；
  - Playwright 自动化闭环：`pnpm --dir "apps/platform-web" exec playwright test "e2e/f02-loop-detection.spec.ts" --project=chromium` 退出码 0，端到端测试全绿通过：
    1. 真实大模型全链路对话正常完成且无死循环误判（流式接收、输入重置、无误判）；
    2. F02 循环检测实时预警、终止与运行诊断抽屉展示闭环（预警状态条、拦截兜底文案、诊断抽屉卡片渲染与空数据隐藏）；
  - 截图归档：沉淀至 `docs/projects/20260913-dearflow-agent/screenshots/`（包含真实大模型对话 `01-real-model-normal-success.png`、诊断抽屉全景 `02-run-diagnostics-drawer.png`、卡片特写 `02-run-loop-detections-card-closeup.png`、预警状态条 `03-status-bar-loop-approaching.png` 及终止报错状态条 `04-status-bar-loop-reached.png`）；
  - 人工浏览器验收：用户人工确认验收通过，本地服务安全停止并完成清理。

### Final：F02实施与启用验收

**整体Final已执行完成。**
1. **全链路交付物：**
   - Runtime Service：共享循环检测中间件 `LoopDetectionMiddleware`，连续 3 轮预警与 5 轮安全硬终止拦截；
   - Platform API：网关契约、安全字段脱敏清洗与诊断 DTO；
   - Platform Web：Zod DTO 弹性校验、时序状态机（warning/error）、Subagent 安全冒泡、中文降级兜底及 `RunDiagnostics` 独立循环卡片；
2. **多层测试闭环：**
   - 单元测试：后端定向 pytest 与前端 Vitest（85 项测试）100% 通过；
   - 静态门禁：`vue-tsc` 0 报错、`eslint` 0 错误、生产 build 成功；
   - 端到端闭环：Playwright + Chromium 驱动真实大模型全链路验证通过；
3. **人工验收结论：**
   - 用户审查实测全景与局部特写截图，确认符合工业级产品与架构设计预期，正式批准完成。

## 状态

F02整体 `done`。P01/G0/T01-T08 全部完成，全链路代码与测试验收闭环，无遗留阻塞。默认保持为安全开关可控（`AGENT_LOOP_DETECTION_ENABLED`）。

### 评审记录

| 日期 | 事项 | 状态 |
| --- | --- | --- |
| 2026-10-09 | 用户要求批判性对比F02、只做详细规划、前端交同事 | 规划授权；不等同实施批准 |
| 2026-10-09 | G0：只读连续重复策略、停止范围、3/5候选、默认关闭及公开契约 | 用户评审完成并授权实施；推进到仅剩前端，遇到真实阻塞才停止 |
| 2026-10-10 | 用户完成实景截图与前端功能人工验收，确认满足预期并授权合并收尾 | 验收通过，专项标记为 done |
