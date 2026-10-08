# Agent 运行准备幂等与有界重试 - 整体方案

本方案于 2026-10-07 获用户批准。非前端实现、验证与交接 `done`，整专项 `partial`；前端由同事实施。用户明确要求本次不使用 Docker，故验证采用本机已有 PostgreSQL/Redis 和原生进程。

## 背景

当前 Agent 的图、模型解析、工具装配、工作区、MCP、子 Agent、错误反馈、调用限额和诊断已具备生产基础，但各组合根的可靠性接线不完全一致：Reference 有显式模型/只读工具重试，DearFlow/Showcase 主要依赖 SDK 默认重试和 GraphHarbor Worker 恢复；工作区和 Skills 各自有操作级幂等，却没有统一的“本次运行已完成哪些准备”记录。

open-swe 提供了可借鉴的两个模式：`BasePrepareRunMiddleware` 的 checkpoint latch，以及只针对 `task` 子 Agent 的选择性重试。其业务身份、外部集成、sandbox 代理、dispatch 封装不能直接迁移。

## 目标

1. 任意 Agent 可通过一项通用 middleware/组合约定记录完成的准备步骤，并在同一恢复身份、配置和资源仍有效时复用已 checkpoint 的结果。
2. 只对有证据的 provider/transport 瞬时失败和只读子任务重试，限制尝试次数、退避和总耗时，保留中断、取消、权限、未知缺陷和写入结果不确定性的真实语义。
3. 让 Platform API 和 Web 可以安全呈现 prepare/retry 摘要，但不把执行策略搬进控制面或浏览器。
4. 通过隔离故障注入证明“Runtime middleware 重试”和“GraphHarbor Worker 基础设施重排”各自只负责一次。

## 不变量

- 状态标记只记录可序列化的 fingerprint、schema/revision 和已完成组件；不保存 token、API key、路径中的凭据、模型对象或任意异常正文。
- 每次 factory 仍执行身份、context hash、project/thread/graph scope、工具 allowlist 和当前凭据授权；prepare latch 不能绕过安全校验。
- `_prepare()` 发生的外部写入必须使用当前已有的 workspace marker、技能 snapshot、CAS 或服务端 idempotency key；新操作若没有幂等依据，不得接入 skip。
- 对于有写入/部署/外部提交副作用的 `task`，不启用自动重试；不把整个父 Run 当作重试单元。
- 取消、`GraphBubbleUp`、`RuntimeAuthError`/`RuntimeResolutionError`、`RuntimeWorkspaceError` 和未分类程序缺陷不转成“可继续”的普通 ToolMessage。
- provider 错误摘要只使用既有有界 `observability.errors` 和 error-envelope，不透传异常 `str()`、body、headers、凭据或绝对路径。

## 方案设计

### 1. Runtime 公共 prepare 契约

新增位置优先放在 `apps/runtime-service/src/runtime_service/middlewares/` 的通用模块（暂定 `run_prepare.py`；实现前核对是否已有等价模块，避免重复）。不在 `dearflow_agent/` 下复制给单一 Agent。

公共接口为 `RunPrepareState`（扩展官方 `AgentState`）和 `RunPrepareMiddleware`（扩展官方 `AgentMiddleware`）。两处 `WorkspaceMiddleware` 已复用该组件的 latch，保留服务自己的 scope 校验和 backend 调用；不建立可注册的 prepare 插件框架。

私有状态 `runtime_prepare` 是最多 16 个固定 component 名到 64 字符 fingerprint 的映射，使用 `NotRequired[Annotated[..., PrivateStateAttr]]`。同一 component 的新 Run 替换旧记录，不能按 Run 无限追加。首次或老 checkpoint 没有字段时执行准备；失败不写标记。多个组件按既有 before-agent 节点顺序写回，必须保留其他组件已有标记。

`abefore_agent(state, runtime, config)` 执行顺序：

1. 每次先校验 scope/context 和资源路径；这些校验在 latch 外。
2. 从可信执行信息确定 Run/namespace，结合 resolved `config_hash`、component 固定名、prepare revision，canonical JSON + SHA-256 生成 fingerprint。
3. 已提交 marker 匹配且 backend 必需资源完整，返回 None 并记录 reused；对象绑定仍由本次 factory 完成。
4. marker 缺失/不匹配或资源缺失，执行已有幂等 prepare；缺目录允许重建，用户修改的文件不能被覆盖。篡改、symlink、scope/digest 不符必须终止，不能用“重新准备”掩盖。
5. 成功后更新该 component marker 并记录 prepared/repaired；后续 checkpoint 由 LangGraph 负责。

fingerprint 包含 schema revision、可信 Run ID、tenant/project/thread/graph、当前 checkpoint namespace、component、resolved `config_hash` 和 prepare revision。不能包含每次 hook 的 task ID、时间、token 或最后一条消息：它们会随恢复/构图变化。资源 digest 仅用于已有不可变快照，不把全工作区内容纳入 hash。

Run ID 优先 `runtime.execution_info.run_id`，缺失则用 GraphHarbor Worker 覆盖注入的 `config.metadata.run_id`，复用当前 `MessageQueueMiddleware` 的读取惯例。两者同时存在但不一致时拒绝；没有身份的普通离线调用执行幂等 prepare 但不 latch，不生成随机 invocation 来伪装可恢复。新用户调用、审批 resume 和 fork 通常会产生新 Run，允许重新准备；资源本身继续幂等。Worker 对同 Run 重排必须保留身份，由实际 worker 测试确认。

`PrivateStateAttr` 隐藏输入/输出 schema，不是授权措施，Thread state/history 仍可能包含字段。复用 Platform `core/runtime_contract.py` 的 `PRIVATE_RUNTIME_STATE_KEYS`/`reject_private_runtime_state()`，加入 `runtime_prepare` 后，现有 Run/Protocol/state 写入口拒绝伪造；`adapters/langgraph/sdk_client.py` 的 `redact_runtime_private_fields()` 在 state/history/SSE 中剥离该字段。禁止另写一套 guard，也不在公开错误中反射客户端值。

准备步骤的最小分类：

| 组件 | 复用条件 | 失败处理 |
| --- | --- | --- |
| workspace layout/marker | scoped root、版本 marker、非 symlink、必需目录存在 | `RuntimeWorkspaceError` 终止；不自动改写用户文件 |
| Skills snapshot | 当前执行的 snapshot ref 存在、digest 匹配、目录非 symlink | 保留现有 `_restore()` 的缺失/篡改终止规则；恢复不能读取“今天的 Skills”替换旧快照 |
| prompt rendering | 纯函数且 `prompt_hash`/revision 相同 | 可直接复用字符串或每次重算；不做外部副作用 |
| model/MCP/credential | 当前授权、ref、连接健康；不把密钥放 state | 每次 factory 按安全边界解析；连接失败不靠 latch 隐藏 |

首期只给 Showcase/DearFlow 的 workspace 准备接 latch，两处 backend 增加轻量 `is_prepared()` 检查必需目录/marker，校验仍在每次 hook 执行。Skills 的原子 snapshot/_restore 保持现有语义并纳入回归，不再套第二个 latch。没有真实消费者的 prompt 快照/远程 sandbox token 缓存不开发。这样至少两个现有 Agent 使用同一公共机制，新 Agent 可以用相同 middleware 扩展点接入。

### 2. 重试策略

新增 `apps/runtime-service/src/runtime_service/middlewares/retry.py`：typed 瞬时错误 predicate、`RuntimeModelRetryMiddleware` 和 `DelegatedTaskRetryMiddleware`。两个薄扩展分别继承官方模型/工具 retry，仅增加请求角色筛选、安全计数记录和终止边界；退避、jitter、sleep、异常控制流和 retry 循环全部用官方实现。

显示分类沿用 `observability.errors.classify_exception()`，重试裁决禁止依赖它的文本兜底。正向匹配已安装的标准 `ModelError` 子类、provider SDK 类型和 `httpx.TransportError`；HTTP 仅白名单 `{408, 429, 500, 502, 503, 504, 529}`。409/425、501/505、未知状态或仅有同名异常不启用。权限、数据验证、graph interrupt/cancel 和 workspace 故障优先排除。

#### 模型调用

- 使用官方 `ModelRetryMiddleware` 的薄扩展，接入 DearFlow/Showcase 主模型与不能整体重放的写操作子 Agent 的单次模型调用。
- 首期每个失败单元最多 1 次重试（总 2 次），`initial_delay=1s`、`backoff_factor=2`、`max_delay=10s`、`jitter=True`；Reference 保持现有显式测试适配和只读工具策略，不另叠一层。
- `retry_on` 只接受 typed `ModelRateLimitError`、`ModelConnectionError`、`ModelTimeoutError` 和匹配前述 HTTP 白名单的 `ModelAPIError`/provider transport 错误；`ModelAuthenticationError`、`ModelPermissionDeniedError`、`ModelInvalidRequestError`、context 超限不重试。标准 `ModelAPIError` 范围比 HTTP 白名单宽，须同时检查可靠 status；不能只有 `is_retryable=True` 就放行。
- DearFlow/Showcase 受管执行模型构造显式 `build_model(..., max_retries=0)`，其动态 model_builder 也一致；suggestions/图片等独立 build_model 调用者不改。
- DearFlow 的 `MemoryContextMiddleware(model)` 和 `build_skill_tools(workspace, model)` 实际共用当前模型，不能声称 SDK 参数修改对它们没有影响。有这些真实内部消费者时，组合根保留原 SDK 策略的辅助模型对象，只给 graph 主/子执行传 retry=0 的模型；不改变记忆/技能的预算，也不使用 model_copy 修改已初始化 client。无这些消费者的 graph 不额外构建对象。
- 无法支持 max_retries=0 的 provider 不启用 middleware retry，不能声称总尝试数受控。旧 provider/引用权限照常校验，不能给失败的业务模型偷偷换默认模型。
- 当前模型超时为每次 provider attempt 的上限（默认 600s）；两次最多约 1201.25s，不改变已有 worker Run deadline。本地示例 Run deadline=1800s，部署示例=300s；真实 Run deadline 先到则立即停止，可能不足两次，不能为了重试延长 Run 配置。
- 当前 `ModelCallTimeoutMiddleware` 抛 builtin TimeoutError。实施时只把该 hook 自己的 `asyncio.timeout` 到期标准化为 typed `ModelTimeoutError`，使用 timeout context 的 expired() 区分真实 provider/其他 TimeoutError，避免把任意 builtin 超时视作模型 transient。这让只读 child 的 deadline 可由父 task 重试，同时给无 owner 路径避免 Worker 误重排的明确类型。
- 模型一旦向外发送 content、reasoning 或 tool-call delta，不再自动重试该调用；保留一次失败尝试并向外终止。T05 先用当前 callbacks/streaming 验证每次调用的 emitted 标记可准确归属，薄扩展只在未公开任何 delta 时进入下一次官方 retry。不得拼接两次部分回答、清掉已发 token 或靠延迟所有流事件来伪造可重试性。无法实现/证明此 guard 的调用路径不启用自动 retry，必须在评审/验证中说明。

#### 子 Agent task

- `DelegatedTaskRetryMiddleware` 只接受 `task` 且 `request.tool_call.args.subagent_type` 命中组合根固定的只读角色集合，随后调用官方 `awrap_tool_call()`；官方 `tools=["task"]` 本身不能筛选角色，因此需要这一个请求级筛选。
- DearFlow 的工厂函数叫 `researcher()`，但实际 `subagent_type` 是 `general-purpose`，且被代码覆盖为只读；Showcase 的 `research` 才是同名只读角色。Showcase `general-purpose` 可以写/execute，绝不能沿用 DearFlow 的名字白名单。策略由每个 graph 的组合根传入，禁止全局按角色名判断。
- 只读角色不能含写文件、execute、部署、图片/图表提交和未知 MCP 工具；研究工具本身会缓存证据，但当前结果按内容 hash 落盘，可重入性仍须验。用户/LLM 不得提供“只读”属性；组合测试核对完整工具闭包。
- 这些角色的 SDK retry=0、模型 middleware retry=0，失败由父 task 统一最多尝试 2 次。其他子角色只做单次模型调用重试，不做 task retry；避免 2 × 2 放大。
- transient 耗尽的只读 task 返回安全 `ToolMessage(status="error")`；未知缺陷、授权、资源故障继续抛出。context/prompt 的模型可修复错误仅在同一只读角色集合内，由 retry 外层现有 `ToolErrorMiddleware(on_error=on_tool_error)` 选择性转换，因为非匹配异常不会调用 `on_failure`。角色筛选在拿得到 request 的 `on_tool_error` 入口完成，复用组合根同一集合；写角色或未声明角色的 delegation 失败传播，不默认允许父模型重发已可能执行写入的 task。
- 不承诺子图 exactly-once。尚未公开任何子图 delta 时，重试可能重复只读查询，并留下两次内部尝试观测；保持官方 namespace/tool_call_id/history 语义，不拼接两次结果成一次成功。真实 graph/worker 测试必须证明最终配对、计数和取消正确。
- 只读 task 一旦已公开子图模型 content/reasoning/tool-call delta，同样禁用整 task 重试。此时 predicate 返回 False，官方 `on_failure` 不会执行；请求筛选后的薄扩展精确捕获已确认的 transient 终止，复用安全内容构造返回一个原 tool_call_id 的错误 ToolMessage，记录实际 attempts、outcome=failed。若首次尝试就已出流，attempts=1；若第二次尝试才出流失败，attempts=2。权限、资源、中断、取消和未知异常仍传播。任何成功的子图工具也须有可重入依据；首次接线故障用例在首个对外 delta 前触发，不把“只读”当成流式重复安全的保证。

#### Run/Worker

- 不为整个 GraphHarbor Run 添加 `RetryPolicy` 或重新 POST。Platform 已用同一个 `Idempotency-Key` 对提交去重，GraphHarbor Worker 已负责基础设施失败的 lease/requeue。
- 主模型/写 child 的模型重试耗尽，或因已有公开 delta 而禁止 retry 后，薄扩展把已确认的 provider/模型 deadline 错误封装为 `RuntimeExecutionError`（新增到 `runtime/errors.py`，继承现有安全 `RuntimeErrorBase`），只携带稳定 code，保留原异常作 cause。其外层类型不能是 builtin TimeoutError/ConnectionError/OSError，避免 post41 Worker 再把 provider 耗尽当基础设施重排。只读 child 的 raw typed 模型错误保留到父 task owner 处理，不能提前封装成不可重试 Runtime 错误。
- 原始数据库、checkpoint、lease、进程或未知异常不经过该转换，保留 Worker 既有行为。单次模型 deadline 耗尽是执行失败；整个 Run deadline 仍是原生 timeout，用户停止仍是 cancelled，中断仍是 interrupted。

### 3. 错误与诊断

Runtime 复用 `tools/errors.py`、`observability/errors.py`、`observability/query.py`。新增本地/Langfuse metadata 事件 `runtime.prepare.completed`、`runtime.retry.completed`，不新增自定义 SSE 控制事件。retry 薄扩展通过 handler closure 计数调用次数，在最终结束时记录总尝试数和结果，不复制官方 retry 循环，也不猜测实际退避耗时。

diagnostics v1 增加两个可选、各最多 20 条的数组 `preparations`/`retries`；冻结字段见交接文档。旧 payload 缺失时有效并取空数组；继续采用现有 100 observations、50 trace、2s 查询预算和 truncated 标记。schema_version、安全 metadata 白名单、Pydantic/OpenAPI 已同步，Web Zod 由同事扩展；无记录不能填“0 次失败/准备成功”。retry 在 partial stream 后被阻止时记录实际 attempts、outcome=failed；不要声称 exhausted。attempts 单指 middleware handler，不代表整个 Run 的模型调用总数，也不因出现 delta 重置为 1。

默认不公开每次 provider retry 的原始错误文本。未知/未授权/取消等仍按现有 error-envelope 和 Run 状态出口处理。诊断字段缺失时保持旧 DTO 兼容：Runtime 不记录就返回 null/空数组，Platform 不为旧记录补猜测值。

### 4. 组件接线

| Agent/graph | 准备接线 | 重试接线 | 备注 |
| --- | --- | --- | --- |
| `reference_agent` | 先作为行为基准；不重复添加已有 read_reference/model retry | 保持现有 | 验证 middleware 顺序和重试总数 |
| `dearflow_agent` | workspace latch；Skills snapshot/_restore 原机制保持 | 主模型 1 次；`researcher()` 定义的只读 `general-purpose` task 1 次、其模型不重试 | 同名角色在 Showcase 是写操作角色，必须按 graph 配置 |
| `showcase_demo` | workspace latch/目录有效性；schema-only probe 不创建资源 | 主模型 1 次；research task 1 次、其模型不重试 | general-purpose/chart-agent 不做 task retry；验证本机 local 与共享目录逻辑，Docker 执行不在本轮验证范围 |
| 其他 graph | 不自动套用 | 不自动套用 | 由 graph owner 以 middleware/tool allowlist 显式选择 |

组合根文件：`apps/runtime-service/src/runtime_service/services/{reference_agent,dearflow_agent,demo/showcase_demo}/agent.py`。所有接线必须通过现有 `middleware()` 局部函数和组合根，不改 DeepAgents 核心、不建全局 Builder。

### 5. Platform API

做公共边界投影、标记防注入和回归：

- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/diagnostics.py`：增加两组可选摘要，使用 Literal/严格非负整数并保持 `extra="ignore"` 的安全投影。
- `apps/platform-api/src/platform_api/core/runtime_contract.py`：加入私有 key，复用现有 reject helper 覆盖 `_normalize_payload()`、Protocol 输入、`update_thread_state()`；检查所有入口，不改正常输入契约。
- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py`：在既有私有字段投影中剥离 prepare 标记，覆盖 state/history/SSE；不重写 sanitizer。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`：已有 guard/diagnostics 查询通常只需回归；只有入口遗漏有实证时才修调用点，不加入自动 retry。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py`：不新增运行控制 endpoint；若新增字段，沿现有 diagnostics 路由 no-store 和授权链路返回。
- `apps/platform-api/tests/test_run_diagnostics.py`、`tests/test_run_requests.py`、`tests/test_runtime_delegation.py`：覆盖安全字段、授权、幂等和恢复。

### 6. Platform Web

前端只消费平台 DTO，不读取 Runtime 内部状态，不自己 retry。复用：

- `apps/platform-web/src/services/threads/diagnostics.service.ts`：保持目标 ID 校验、`x-project-id`、取消与错误解析。
- `apps/platform-web/src/modules/chat/diagnostics/types.ts`：以可选字段扩展 Zod；未知字段继续 strip。
- `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue` 和 `useRunDiagnostics.ts`：在既有模型调用失败/启动阶段区域加入“准备复用/重试次数/重试耗尽”摘要，缺省时隐藏，不增加新的运行状态机。
- `TrajectoryTimeline.vue`/`TrajectoryInspector.vue`：首期仅回归普通轨迹/子图历史，不新增 attempt 标记数据模型；所有摘要集中到 RunDiagnostics。

具体字段和验收流程写在 [frontend-handoff.md](frontend-handoff.md)，由同事实现后回填真实截图/浏览器证据。

## 链路影响

```text
Platform Web 诊断展示
        -> Platform API diagnostics-read + Run/Thread 归属校验
        -> Runtime diagnostics metadata projection
        -> GraphHarbor Run/checkpoint/Worker
        -> Runtime factory -> prepare middleware -> model/tool middleware -> graph
```

### 契约变化

已增加 v1 可选诊断数组及保留字段防注入。Runtime/Platform API 已同步，前端交接已冻结；对应落点：

1. Runtime 安全投影和单元测试；
2. `apps/platform-api` Pydantic DTO/OpenAPI、脱敏测试；
3. `docs/standards/error-envelope.md` 或 `docs/standards/sse-event.md`：本次未改变其格式，不新增事件；保留既有标准状态；
4. Platform Web Zod 类型和旧数据兼容测试待同事实施，交接文档已完成。

任何状态字段改变都必须保留未知提交/重复提交/恢复不覆盖 config 的既有规则。

## 风险和依赖

| 风险 | 应对 |
| --- | --- |
| checkpoint 标记覆盖不了副作用未提交窗口 | 操作级 idempotency/CAS/marker；故障注入在副作用后杀进程 |
| SDK、middleware、Worker 多层重试放大 | 明确每层预算；设置 client max_retries；对每条失败链记录实际 attempt；单一 owner 测试 |
| 只读判断被业务工具绕过 | 工具名 allowlist + 角色 middleware；未知工具拒绝接线；组合测试枚举写工具 |
| 诊断泄露异常正文或内部路径 | 复用 safe_fields、DTO strict bounds、SSE error redaction；canary 回归 |
| 新字段破坏旧记录/前端 | Optional + null/empty fallback；v1 schema 兼容测试 |
| GraphHarbor post41 行为升级 | 锁定当前包；先离线测试，真实升级另开项目 |
| 生产环境没有真实 provider/worker | 先完成离线、ASGI、隔离 GraphHarbor 和故障注入；未具备条件的真实链路明确 partial/block，不宣称 done |

## 回退方案

每个 Agent 的新增 middleware 由组合根局部装配，回退时恢复旧接线和该 Agent 原先的 SDK retry 设置，不新增控制台开关。出现重复写入、重试风暴、错误泄露时保留既有调用限额/Worker 恢复。既有 checkpoint 中的安全 marker 不需要删除；实际旧图忽略新私有字段的行为必须测试。Platform/Web 新增字段 optional，允许先保留新展示、回退 Runtime；防注入规则保留。

## 实施顺序

1. 先完成人工 G0 评审，确定 prepare key、provider retry allowlist、尝试总数和诊断字段。
2. 在 Runtime 写公共纯函数/状态契约和最小故障测试；不先改三个组合根。
3. 以 Showcase/Research 只读路径为样本接线；通过后接 DearFlow；Reference 保持基准。
4. 加 Platform 安全投影和 Web 交接字段；由同事完成页面。
5. 分阶段验证：Runtime 定向 → Platform API → Web 类型/单测 → 三服务真实短链 → 故障注入 → Final 门禁。
6. 仅所有任务和关键链路完成后，运行 `verify-change` 记录四态结论；治理项目不得自批生产发布。

## 后置：自主唤醒

只有同时满足以下条件才另开任务：存在明确产品工具/消费者；平台能用数据库原子 compare-and-set 预留“用户消息代际 + 次数”预算；每次 wakeup 使用普通 `Idempotency-Key` 和受权 run-create；取消、删除、权限撤销、重复 cron 有明确结果；多 Worker 不依赖进程内 lock；前端能展示“系统触发”且停止/恢复语义不混淆。默认预算、窗口和用户体验需要人工评审，不能直接照搬 open-swe 的 10 次常量。
