# Runtime网关标准

普通 Run 网关公开前缀为 `/api/langgraph`，入口见[router](../../src/platform_api/modules/runtime_gateway/presentation/http.py)。Platform负责身份/项目授权、参数决议、幂等记录和受控转发；GraphHarbor持有执行事实，Runtime负责图、模型与工具。GraphHarbor不实现平台业务JWT。

## 当前公开面

下列路径相对前缀；t表示 `{thread_id}`，r表示 `{run_id}`，实际请求必须替换为ID。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /info | Runtime信息 |
| POST | /graphs/search | Graph搜索 |
| POST | /graphs/count | Graph计数 |
| POST | /threads | 创建Thread |
| POST | /threads/search | 搜索Thread |
| POST | /threads/count | Thread计数 |
| GET | /threads/t | 读取Thread |
| DELETE | /threads/t | 删除Thread |
| GET | /threads/t/state | 读取state，支持subgraphs/checkpoint_id |
| POST | /threads/t/state | 更新state |
| POST | /threads/t/history | 读取checkpoint历史 |
| POST | /threads/t/runs | 创建或恢复Run |
| POST | /threads/t/runs/stream | 创建并订阅Run |
| POST | /threads/t/commands | Protocol命令 |
| POST | /threads/t/stream/events | Protocol事件订阅 |
| GET | /threads/t/runs/r | 读取Run |
| GET | /threads/t/runs/r/diagnostics | 授权读取安全诊断摘要 |
| GET | /threads/t/runs/r/usage | 授权读取 Run Token/成本与分页调用明细 |
| GET | /threads/t/usage | 授权读取已采集 native Runs 的 Thread 合计 |
| GET | /threads/t/runs | 列表，支持limit/offset/status/select |
| GET | /threads/t/runs/r/join | 等待Run |
| GET | /threads/t/runs/r/stream | 重连Run事件 |
| POST | /threads/t/runs/r/cancel | 显式取消 |

此处通用面共23条；完整矩阵还独立覆盖文件、消息、Dear 等自定义入口，由[test_runtime_gateway_http_matrix.py](../../tests/test_runtime_gateway_http_matrix.py)与路由注册集合校验。未列出的上游能力不能因为SDK有方法就当作平台接口，完整LangGraph Server等价性另行验收。

## 身份与参数

请求携带平台认证与 `x-project-id`。Thread归属必须匹配项目；启动/恢复重新检查当前Agent、Graph、模型、工具与成员授权。委托scope.operation区分read和run-create。

委托使用短时v2/HS256 JWT；Gateway与Catalog各自按当前请求签发，service account必须携带当前`credential_id`，用户不得携带。非法签发输入统一走安全`503 runtime_delegation_not_configured`，上游401对外映射`502 runtime_delegation_rejected`，不表示平台用户登录失效。已接受Run不因委托到期自动取消；SSE不持续重鉴权，重连/审批/取消新请求重新核对当前权限。28项operation及验证边界见[Delegation 标准](../../../../docs/standards/delegation-jwt.md)。消息入口额外转发同一请求已有的`read`委托供Runtime内部原生Run回查；Runtime核对身份、租户、项目、凭据和Thread绑定后才使用该委托，消息operation自身仍不得访问原生资源。该修复的现役真实链路尚未验证，见[消息回查专项](../../../../docs/projects/20260927-message-run-read-delegation/README.md)。

产品Agent执行键为graph_id，标准SDK字段仍为assistant_id；平台不创建/同步上游Assistant。Graph/Tool刷新是有限超时HTTP，普通目录只读快照；schema从远端读取，不扫描宿主源码。

model_id使用平台模型记录UUID，不是provider:model或模型名称。默认值按项目→Agent→本次显式参数覆盖，仍受策略约束。Agent公开context为model_id、temperature、max_tokens、top_p；不能从客户端注入身份或内部模型引用。

公开运行config只允许recursion_limit（1–1000，默认1000）。内部委托与模型引用由服务端构造，模型凭据不进入浏览器、Run快照或普通日志。Runtime通过受信内部接口按当前权限兑换连接；master key只由Platform持有。

`__graphharbor_run_budget` 是Worker私有attempt执行数据。标准Run、Protocol及恢复/配置归一化递归拒绝客户端提供该键；SDK查询、history和SSE出口递归过滤。不公开`metadata.execution_budget`，不新增预算接口、JWT claim或SSE事件。每次Worker领取刷新attempt预算，浏览器重连不刷新；正式post42已发布/锁定/隔离验收，见[运行超时专项](../../../../docs/projects/20261006-agent-run-timeout-governance/README.md)。

## 幂等与审批

新动作使用新的 `Idempotency-Key`，同动作重试保留原key。相同key和内容复用原Run，不同内容返回409；没有key的标准请求是独立动作。HTTP超时表示结果未知，先查询原Run，不用新key盲重发。

run_requests只保存请求摘要、授权/config快照和Run关联，不存消息或执行终态。并发执行首期使用reject，由Agent Server原子裁决，不在平台再造活跃运行锁。

标准恢复示例：

```json
{"assistant_id":"showcase_demo","command":{"resume":{"interrupt-id":{"decisions":[{"type":"approve"}]}}}}
```

从当前state读取真实interrupt ID与动作，decisions必须与动作对应，不能硬编码全批准。恢复不允许覆盖input/config/context；多个interrupt使用ID映射。Protocol `/commands` 的input.respond共用授权与恢复路径，id为整数，不是HTTP幂等键。恢复产生新Run ID，父Run关联保留；重复/过期/异项目审批拒绝。

## SSE、错误与取消

平台公开HTTP错误结构、上游状态转换和pending恢复字段见[错误出口标准](../../../../docs/standards/error-envelope.md)；流内事件仍按SSE专项处理。

授权和上游状态校验在发送200前完成。JSON/SSE移除内部runtime_model_ref、预算计数/时钟/latch；SSE敏感键脱敏。Thread.error、state/history tasks错误、tasks/lifecycle/error帧及debug task_result的error使用固定安全消息，保留原生状态、事件ID/seq与正常消息/工具正文。原生 Run GET 不包含 error 字段，不能由最新 Thread.error 推断历史 Run 原因。网络chunk不等于完整事件，客户端使用SDK或正确SSE解析器。

精确的 GraphRecursionError、ModelCallLimitExceededError、ToolCallLimitExceededError、RunTimedOut 分别投影为 `runtime_graph_step_limit_reached`、`runtime_model_call_limit_reached`、`runtime_tool_call_limit_reached`、`runtime_run_timeout`；字符串和未知异常保持安全泛化，Provider TimeoutError 不等于 Run 超时。

默认普通 stream modes 包含 custom；预算 custom 为 `runtime_budget_notice` v1，网关只保留安全字段。Reference/Workflow end 人工消息的 `additional_kwargs.runtime_budget_notice` 可辅助历史解释，通知不改变原生 success/error/timeout 状态。写入口递归拒绝预算私有键及通知伪造，包含 input/update/command/resume。具体 schema 与同事验收见[预算交接](../../../../docs/projects/20261007-agent-execution-budget/frontend-handoff.md)。

普通 Run 需要在创建时 `stream_subgraphs=true` 才回放子图事件；Protocol 沿已有 scoped namespace/depth 订阅。预算通知包含真实 run_id，但外层 params.run_id/seq 可能缺省，客户端用官方 Run 投影和 SSE 游标关联。DearFlow/Showcase child=error 可沿父图传播，不承诺父 Run 继续。

join stream支持stream_mode、last_event_id和cancel_on_disconnect参数，但当前只允许cancel_on_disconnect=false，true被拒绝。订阅断开不取消Run，必须显式cancel。重连先读Run/state和interrupt，不自动重新发送消息或批准。

Protocol lifecycle可能规范化为completed；Run JSON保留上游状态，不能将两者机械替换。平台cancel保持HTTP200 `{"ok":true}`；默认只表示受理。停止确认需目标Run的 `execution_stopped=true` 终态事件，或同一路径JSON body `{"wait":true,"action":"interrupt"}` 成功。路由只读取body，不转发SDK query wait/action；GET interrupted/cancel_requested仍可能处于清理中。

原生GraphHarbor默认wait=false为202空body，wait=true确认成功200/null，未确认503；平台保留既有ACK形状，将上游未确认503映射为502，网络等待超时为504，客户端保持待核实。`execution_stopped=false/lease_fenced=true` 仅证明旧执行不能再持久写入，不保证实际进程或外部操作退出。JSON/history/SSE脱敏保留上述公开停止事实，私有预算仍过滤；前端接入见[交接](../../../../docs/projects/20261006-agent-run-timeout-governance/frontend-handoff.md)。

Worker attempt到期保持`timeout/reason=timeout`，SDK completed不能覆盖。模型/provider超时沿graph既有retry/fallback，未恢复则error；DB瞬时故障可pending/retry并产生新attempt，Worker不因模型超时整图重试。用户停止保持`interrupted/cancel_requested`，HITL保持`interrupted/hitl_interrupt`并由interrupt事实确认。连接结束、HTTP超时和cancel ACK不能替代Run终态。

401重新认证，403检查权限，404检查资源与项目，409检查幂等或并发，5xx/超时核实提交结果。不得在HTTP 200后伪装前置失败。

## 变更验证

### 上下文维护（2026-10-06 用户批准）

模型目录 CRUD 增加 nullable 正整数 `context_window_tokens`，null 清除、省略更新保留；当前受信内部 model-config 携带容量，浏览器不能通过 Run 上传可信容量。

DearFlow/Showcase 的当前 Thread capabilities 返回 `conversation_offloading`，结合 Runtime feature flag 和 comment ACL。现有 commands/runs/runs-stream 接收 `config.configurable.platform_runtime.offload_conversation=true`（标准 context 位置也接受，冲突拒绝），通过同一前置校验启动空输入维护 Run；禁止消息/附件/checkpoint override、活动 Run、未决 interrupt 和待发消息。pending 状态不可确认返回 503；最终并发由 GraphHarbor reject。

复用 Idempotency-Key/run_requests/取消和审计，维护不 claim 队列、不执行普通模型/工具/MCP/子图/记忆后处理。Context 双端为 v5，省略/false 同 hash，存量 v4 服务端快照重新授权后升级；cron/resume/queue 禁止携带维护标志。

公开 custom 与 Thread state 只保留有界整理状态；私有摘要、session 和归档 files 不公开，所有 input/state update 拒绝注入。普通成果文件保持原访问语义。真实契约和前端待办见 [交接](../../../../docs/projects/20261006-agent-context-window-governance/frontend-handoff.md)。功能开关默认关闭，未部署现役平台。

新增路由更新显式清单，覆盖scope、授权拒绝、字段过滤与参数；业务语义由run_requests/SDK/事件测试以及[真实验收](../../../../docs/projects/20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)证明。router替身不能替代真实执行，前端适配见[交接](../../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。

## Run 诊断查询（2026-10-06 用户批准）

GET `/api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics` 沿当前项目 Runtime read + Thread read授权，先以原生 `read` 确认Run存在及归属，再签发Thread绑定的 `diagnostics-read` 调用Runtime内部只读入口。查询Langfuse不占平台数据库事务，不增加模型调用，也不回写Thread metadata。

200响应使用实际 `RunDiagnostics` v1 DTO/OpenAPI，并带 `Cache-Control: no-store`。`run_status`来自原生Run；模型失败记录只是调用尝试，graph/startup不能证明最终错误分类时 `error_code=null`。`request_id`是本次查询，`correlation.execution_request_id`是原执行。`trace.url`首期固定null，未知字段删除，非法上游DTO安全502。

远程关闭返回disabled/not_configured，无记录返回unavailable/not_recorded，观测连接/超时返回unavailable/backend_unavailable；均不影响Run。权限拒绝、Runtime delegation拒绝、上游结构错误保持现有Envelope。Runtime查询100 observations、50 trace、2秒总预算，实际契约和交接见 [专项](../../../../docs/projects/20261006-agent-observability-hardening/03-run-diagnostics-query.md)。

## Run/Thread 用量查询（2026-10-07 用户批准）

两个 Usage GET 使用当前 Runtime read + Thread ACL；Run 级先原生 `read` 确认存在与归属，再签发 Thread-bound `usage-read`。Runtime 重查当前 ACL 后从自己的数字 ledger 汇总，Platform 不连接 Runtime 数据库、不扫描 messages 计费。HTTP 等待不占平台 SQL 事务，响应 `Cache-Control: no-store`。

Run `limit=1..200`（默认50）、不透明 keyset cursor；summary 不随明细页变化。Thread 默认全部已采集 native Runs，可选成对 UTC `created_from/created_to`，左闭右开、最多90天；该窗口不是保留期。DTO/OpenAPI 固定 v1，金额是12位小数 string；input 含缓存、reasoning 属 output 子项，缓存 read/write/TTL 分桶计价。缺 usage/价格明确 unknown/partial，不补零；无采集记录为 not_recorded。

新增 nullable catalog `pricing_json`，原 model CRUD 支持可空六费率 USD/百万 Token；PATCH 不传保留、null 清空、对象完整替换，服务端生成 UUID version。调用保留完整历史快照，目录变价/删除不改旧成本。Runtime 采集默认关闭，关闭后历史仍可读；数据库失败为授权后的200 unavailable，坏 DTO 502、网络503/504及401/403/404保持标准错误。

冻结 schema、状态样本、联调和交接见 [Usage 前端报告](../../../../docs/projects/20261007-agent-usage-cost-governance/04-frontend-handoff.md)。隔离验证已执行，现役服务未部署，前端待同事。

### Dear Agent 治理资源（P6）

`GET/POST /api/langgraph/threads/{thread_id}/dear/{resource}`仅允许`memory`。
平台先验证项目读/写权限、线程归属、Dear graph与项目Agent启用关系，再签发
`dear-governance-read`或`dear-governance-write`短时委托，调用Runtime的
`/internal/threads/{thread_id}/dear/{resource}`。不得直接代理用户自填tenant/user或证据裁决。
Runtime保有记忆私有表和revision规则；GraphHarbor不实现此业务。记忆更新冲突保持409。

技能管理改为不依赖会话的 `/api/langgraph/dear/skills`（列表、详情、正文、上传、更新、启停、删除）。
委托 operation 为 `dear-skills-read/write`，thread_id 为空，assistant_id 固定为 dearflow_agent；
平台校验项目读写和 Agent 目录授权，Runtime 从签名身份提取 tenant/project/user。
当前技能使用不透明 revision 做 CAS；旧 thread skills 入口不兼容，memory 保留。
完整契约见 [前端交接](../../../../docs/projects/20260919-skills-page-improvement/07-frontend-handoff.md)。
具体字段与前端限制见[Dear P6交接](../../../../docs/projects/20260913-dearflow-agent/frontend-handoff.md)。

## 工具治理（2026-09-20）

Runtime 代码声明工具上限；工具 Catalog 仅展示。Platform 从 runtime_tool_restrictions 求项目/用户拒绝并集，签发 delegation_version=2、false-only tool_overrides 和 tool_policy_version。每次具体操作重新求值，查询失败不签空规则。浏览器的 tools/enable_tools/授权字段拒绝；旧工具策略接口已退役。管理接口及前端接入见[交接文档](../../../../docs/projects/20260920-runtime-optional-tool-resolution/frontend-handoff.md)。

## 定时任务产品接口（2026-10-05）

独立前缀 /api/scheduled-tasks：GET/POST 列表与创建、POST /preview、GET/PATCH/DELETE /{task_id}、POST /{task_id}/pause、/resume、/trigger，以及 GET /{task_id}/runs，共 10 条。普通 /api/langgraph 的通用面23条保持独立。字段与 HTTP 状态见 [前端交接](../../../../docs/projects/20261005-scheduled-agent-tasks/frontend-handoff.md)。

请求需平台身份与 x-project-id；定义和历史按 tenant/project/owner 私有隔离。cron-read/write 不能代替执行 payload 的 run-create；手动触发必须 Idempotency-Key，复用 run_requests、Thread reservation 和正常受管 Run，不推进计划时间。

GraphHarbor 为唯一定义/调度/Run 事实源。平台 metadata 保存产品定义，无 cron/occurrence 表或第二套 worker；Runtime 内部预览复用原生 parser，历史先 SQL 过滤后分页，审计补拒绝原因。

Runtime 图构造前以 HMAC 调用 POST /api/runtime/internal/scheduled-authorization，每个 Run 一次聚合核验身份/凭据/项目/Agent/模型/Thread；拒绝留痕且保留定义，回查不可用拒绝。批准后刷新当前角色/模型引用/工具限制。运行中不周期重验；暂停/删除不取消已接受 Run；无人值守审批失败。平台 HMAC 与 GraphHarbor 通用生产签名的责任边界见 [方案](../../../../docs/projects/20261005-scheduled-agent-tasks/plan.md)。

定时任务原post41隔离验收保留；平台Runtime当前锁定并安装GraphHarbor post42，超时/取消及匹配版本回退隔离链路通过，未部署现役或远端平台。Delegation标准整体仍为draft，消息内部Run回查的现役验收另行完成。
