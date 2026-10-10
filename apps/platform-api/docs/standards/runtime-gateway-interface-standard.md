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
| GET | /threads/t/runs/r/completion | 当前权限下读取持久安全终态摘要 |
| GET | /threads/t/runs/r/usage | 授权读取 Run Token/成本与分页调用明细 |
| GET | /threads/t/usage | 授权读取已采集 native Runs 的 Thread 合计 |
| GET | /threads/t/runs | 列表，支持limit/offset/status/select |
| GET | /threads/t/runs/r/join | 等待Run |
| GET | /threads/t/runs/r/stream | 重连Run事件 |
| POST | /threads/t/runs/r/cancel | 显式取消 |
| POST | /threads/t/cancel | 会话固定目标停止，持久受理 |
| GET | /threads/t/stop-requests/{stop_id} | 查询安全停止回执与报告 |
| GET | /threads/t/stop-requests | 分页回查停止动作 |

completion 的独立 router 还提供当前用户 feed/read，路径和验证见下文；现有原生代理矩阵与 completion 契约测试分别覆盖。未列出的上游能力不能因为SDK有方法就当作平台接口，完整LangGraph Server等价性另行验收。

## 运行完成与私有通知（2026-10-09 用户批准）

独立 `presentation/completion_http.py` 提供 `GET /api/langgraph/threads/{thread_id}/runs/{run_id}/completion`、`GET /api/runtime/run-notifications`、`POST /api/runtime/run-notifications/{event_id}/read`。原生 Run 查询和当前 Thread ACL 校验目标；available/pending/unsupported/expired 不替换实时 Run 状态。feed 只含当前用户/项目的 error/timeout，共享读取者可看历史但不代写已读；删除/撤权后不展示旧摘要，全部响应 private,no-store。

内部 `POST /api/runtime/internal/run-completion` 使用原始正文 HMAC、独立服务器 key 和提交后 ACK；origin、event、receipt 全属 Platform 数据库，不查引擎 SQL。GraphHarbor post44 持有通用终态/Outbox，Runtime 持有纯安全 projector；平台身份策略、模型码和文案不进入 GraphHarbor。默认关闭，配置与前端交接见 [完成通知专项](../../../../docs/projects/20261009-agent-production-capability-extension/README.md)。

## 文档文件契约

原有 `PUT /threads/t/files/uploads/{sha256}?file_name=...` 接收 raw bytes，单文件 20 MiB；DOCX/PPTX 使用标准 OOXML MIME，响应仅 `version/path/file_name/mime_type/size_bytes/sha256` 六字段 FileRef v1。平台只做当前项目/Thread 授权、Delegation 和透传，结构解析归 Runtime；上传成功不代表已解析。

`GET /threads/t/files/content?path=...` 保留认证下载、原字节、private/no-store、nosniff 与 attachment；回退 Office 写入口也须保留已接收文件的 GET MIME/哈希读取路径。fork 继续沿后端授权工作区复制，前端不新增复制或解析状态存储。实际工具字段与前端接续验收见 [F10 交接](../../../../docs/projects/20261010-agent-document-reading/frontend-handoff.md)。

## 身份与参数

请求携带平台认证与 `x-project-id`。Thread归属必须匹配项目；启动/恢复重新检查当前Agent、Graph、模型、工具与成员授权。委托scope.operation区分read和run-create。

委托使用短时v2/HS256 JWT；Gateway与Catalog各自按当前请求签发，service account必须携带当前`credential_id`，用户不得携带。非法签发输入统一走安全`503 runtime_delegation_not_configured`，上游401对外映射`502 runtime_delegation_rejected`，不表示平台用户登录失效。已接受Run不因委托到期自动取消；SSE不持续重鉴权，重连/审批/取消新请求重新核对当前权限。31项operation及验证边界见[Delegation 标准](../../../../docs/standards/delegation-jwt.md)。消息入口额外转发同一请求已有的`read`委托供Runtime内部原生Run回查；Runtime核对身份、租户、项目、凭据和Thread绑定后才使用该委托，消息operation自身仍不得访问原生资源。该修复的现役真实链路尚未验证，见[消息回查专项](../../../../docs/projects/20260927-message-run-read-delegation/README.md)。

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

## 计划审批（2026-10-09 用户批准）

新 Run 接受严格 bool `context.plan_mode` 或 `config.configurable.platform_runtime.plan_mode`，冲突拒绝。只对显式支持图与 capability=true 启用，cron 禁止。四档 execution_mode 与三档 access_policy 保持独立；前端只能请求增加规划限制，不能设置执行 ID 或批准状态。

Context 双端为 v6，API 从项目/Thread/幂等身份生成 plan_execution_id 并保存 RunRequests。input.respond 复用原请求配置和执行链，重新核对当前人类、Thread approve ACL、Agent/模型/工具授权及计划 ID/revision/hash；没有新计划审批路由。服务账号不能回复计划。相同 actor/body 的重复回复复用 resume:<interrupt_id>，不同决定或 actor 冲突，unknown 只重试原请求。

每个新 Run 读取当前受授权 state，阻止切 graph/新 key/false 绕过 active 或待审计划；普通 Run 因此增加一次 scoped state 读取，含历史 checkpoint 再读历史。规划及 fork bootstrap 期间 update_state 拒绝，待审必须先处理当前 interrupt。新执行/fork/含计划历史不能复用旧批准，bootstrap 只在合法规划 checkpoint 持久后清除；不能公开修改该标记。

state/history/SSE 仅投影有限 agent_plan，私有执行链/绑定/原始 runtime_plan 不公开；无计划键可缺失，未批准时批准人/时间省略，批准人只含 user_id。awaiting_review 以真实 interrupt 为准，公开投影不能用来恢复授权。九个 runtime.plan.* 仅精确安全码投影，异常正文不透出。DTO、HTTP错误与同事验收见 [前端交接](../../../../docs/projects/20261008-agent-plan-mode-governance/frontend-handoff.md)。

API/Runtime v6 成对发布。旧版本不能保护计划 Thread 时先保留当前执行约束并禁用相关 Agent，停止/对账后保留计划和数据；不把卸载 middleware 或 plan_mode=false 当作回退。当前仍未部署现役。

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

## 会话停止与报告（2026-10-07 用户批准）

三条入口在源码和隔离环境实现，正式 Runtime 配套接入仍 blocked，未部署现役。POST `/threads/{thread_id}/cancel` 要求平台身份、x-project-id、当前 `project.runtime.execute` + Thread edit；正文严格 `{}`，Idempotency-Key 必填且1–128字符，UUID/未知正文/query均严格校验。202只证明持久受理，同 actor/credential/project/thread/key 重试返回同 stop_id；正文不接受 run_ids、配置、模型或提示词。保留已有单 Run cancel。

detail/list GET 要求当前 `project.runtime.read` + Thread read；200/no-store，列表 limit 默认20、1–100，cursor不透明且最多256字符；按 requested_at/stop_id倒序。重连、刷新或多端使用这些回执，不靠页面内存判断已停止。POST传输失败先保留原scope/body/key重试；不能按列表时间接近猜归属或用新key重扫目标。

Gateway签发 `thread-stop`/`thread-stop-read`，仅访问Runtime内部同Thread自定义入口；公开 `StopRequest` v1字段白名单以[实际DTO](../../src/platform_api/modules/runtime_gateway/application/run_control.py)为准，校验归属/枚举/UUID/时间/计数，非法上游502，auth_facts/engine_receipt/lease不公开。

phase为accepted/stopping/stopped/no_active_run/confirmation_unavailable/rejected。target_count/execution_stopped/队列计数取证前可null；has_pending_interrupts是引擎接受边界的审批快照，当前审批仍由SDK/state确认。stopped/no_active_run必须execution_stopped=true且有confirmed_at/report；资源pending/unconfirmed保持confirmation_unavailable，不伪装全部已清理。ACK、Run interrupted与工具退出不能互相替代。

报告仅读取固定目标的已提交checkpoint/工具回执/成果，不运行模型、原Agent或注入AIMessage；最多20 checkpoints、30 progress（20计划+10工具）、20成果。truncated表明报告有界，不截断完整停止目标；uncertainties明确checkpoint/进度/外部结果/资源清理未知。成果仍通过现有授权预览/下载入口，报告不输出宿主路径。

Runtime后台对旧固定目标inbox做checkpoint对账，consumed保留、其余user_stopped；后来的新Run不属于旧Stop。Stop不删除工作区、不停止独立Terminal/detached任务、不抹掉审批；显式resume仍绑定当前interrupt ID并复用服务端原执行快照。Runtime存储503按既有契约公开502 `stop_storage_unavailable`，提交超时仍是未知。前端状态机/代码落点/F01–F10见[实现版交接](../../../../docs/projects/20261007-agent-run-cancellation/frontend-handoff.md)。

## Run Token 额度保护（2026-10-09 用户批准）

Token 额度沿现有 `runtime_budget_notice` v1 custom，固定 `unit=tokens_total`、`budget_scope=run`、`scope=primary`。三码为 `token_budget_approaching`、`token_budget_exhausted`、`token_budget_unverifiable`；used/remaining 为非负安全整数或 null，unknown 的 remaining 必须 null。额度通知属于 native 根 Run 全树，不是各子任务余额，不替代原生终态确认。

`TokenBudgetExceededError` / `TokenBudgetUnverifiableError` 及其完整机器码精确投影为 `runtime_token_budget_exhausted` / `runtime_token_budget_unverifiable`，正文和堆栈不公开；JSON、普通 SSE、Protocol/v3 的 tools/tasks/lifecycle/debug/checkpoint 错误槽位一致。两个码是 HTTP200 数据/流内的执行失败原因，不触发登出或撤权，不按任意字符串子串猜触限。

Run Usage v1 新增可选 `token_budget`：max/warn、known_used/remaining、coverage 和 stop_code；旧响应省略或 null 均兼容，Thread Usage 不扩展。自然最终回答用量达到/超过 cap 时 stop_code 可 null，不能仅按 used>=max 推断失败。沿原 usage-read、Thread ACL 与 no-store，不新增权限或 endpoint；`token_budget/token_budget_policy/token_budget_stop_code` 在客户端写入/普通 Runtime 状态出口拒绝或剥离，专门 Usage DTO 是安全摘要出口。

实际 DTO/schema、HTTP 样本与前端任务见 [F01 交接](../../../../docs/projects/20260913-dearflow-agent/16-token-budget-frontend-handoff.md)。后端默认关闭；部署变量不等于公开 Agent 配置，不新增 AgentEditor 表单。

## 变更验证

### 上下文维护（2026-10-06 用户批准）

模型目录 CRUD 增加 nullable 正整数 `context_window_tokens`，null 清除、省略更新保留；当前受信内部 model-config 携带容量，浏览器不能通过 Run 上传可信容量。

DearFlow/Showcase 的当前 Thread capabilities 返回 `conversation_offloading`，结合 Runtime feature flag 和 comment ACL。现有 commands/runs/runs-stream 接收 `config.configurable.platform_runtime.offload_conversation=true`（标准 context 位置也接受，冲突拒绝），通过同一前置校验启动空输入维护 Run；禁止消息/附件/checkpoint override、活动 Run、未决 interrupt 和待发消息。pending 状态不可确认返回 503；最终并发由 GraphHarbor reject。

复用 Idempotency-Key/run_requests/取消和审计，维护不 claim 队列、不执行普通模型/工具/MCP/子图/记忆后处理。Context 当前双端为 v6，省略/false 同 hash，存量 v4/v5 服务端快照重新授权后升级；cron/resume/queue 禁止携带维护标志。

公开 custom 与 Thread state 只保留有界整理状态；私有摘要、session 和归档 files 不公开，所有 input/state update 拒绝注入。普通成果文件保持原访问语义。真实契约和前端待办见 [交接](../../../../docs/projects/20261006-agent-context-window-governance/frontend-handoff.md)。功能开关默认关闭，未部署现役平台。

新增路由更新显式清单，覆盖scope、授权拒绝、字段过滤与参数；业务语义由run_requests/SDK/事件测试以及[真实验收](../../../../docs/projects/20260910-platform-api-refactor/implementation/13-backend-acceptance-closeout.md)证明。router替身不能替代真实执行，前端适配见[交接](../../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。

## Run 诊断查询（2026-10-06 用户批准）

GET `/api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics` 沿当前项目 Runtime read + Thread read授权，先以原生 `read` 确认Run存在及归属，再签发Thread绑定的 `diagnostics-read` 调用Runtime内部只读入口。查询Langfuse不占平台数据库事务，不增加模型调用，也不回写Thread metadata。

200响应使用实际 `RunDiagnostics` v1 DTO/OpenAPI，并带 `Cache-Control: no-store`。`run_status`来自原生Run；模型失败记录只是调用尝试，graph/startup不能证明最终错误分类时 `error_code=null`。`request_id`是本次查询，`correlation.execution_request_id`是原执行。`trace.url`首期固定null，未知字段删除，非法上游DTO安全502。

2026-10-07 用户批准的运行可靠性增量：v1 可选 `preparations`/`retries` 各最多20项，旧响应默认空数组；attempts 严格为1或2，表示单个调用单元总次数。失败尝试不能覆盖原生 run_status，不新增自动重发或 retry endpoint。`runtime_prepare` 加入共享私有状态拒绝/剥离规则，客户端不能伪造；普通 ToolMessage artifact 保真。字段和前端验收见 [交接](../../../../docs/projects/20261007-agent-production-capabilities/frontend-handoff.md)。

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

独立前缀 /api/scheduled-tasks：GET/POST 列表与创建、POST /preview、GET/PATCH/DELETE /{task_id}、POST /{task_id}/pause、/resume、/trigger，以及 GET /{task_id}/runs，共 10 条。普通 /api/langgraph 的通用面23条与新增会话Stop 3条保持独立。字段与 HTTP 状态见 [前端交接](../../../../docs/projects/20261005-scheduled-agent-tasks/frontend-handoff.md)。

请求需平台身份与 x-project-id；定义和历史按 tenant/project/owner 私有隔离。cron-read/write 不能代替执行 payload 的 run-create；手动触发必须 Idempotency-Key，复用 run_requests、Thread reservation 和正常受管 Run，不推进计划时间。

GraphHarbor 为唯一定义/调度/Run 事实源。平台 metadata 保存产品定义，无 cron/occurrence 表或第二套 worker；Runtime 内部预览复用原生 parser，历史先 SQL 过滤后分页，审计补拒绝原因。

Runtime 图构造前以 HMAC 调用 POST /api/runtime/internal/scheduled-authorization，每个 Run 一次聚合核验身份/凭据/项目/Agent/模型/Thread；拒绝留痕且保留定义，回查不可用拒绝。批准后刷新当前角色/模型引用/工具限制。运行中不周期重验；暂停/删除不取消已接受 Run；无人值守审批失败。平台 HMAC 与 GraphHarbor 通用生产签名的责任边界见 [方案](../../../../docs/projects/20261005-scheduled-agent-tasks/plan.md)。

定时任务原post41隔离验收保留；平台Runtime当前锁定并安装GraphHarbor post42，超时/取消及匹配版本回退隔离链路通过，未部署现役或远端平台。Delegation标准整体仍为draft，消息内部Run回查的现役验收另行完成。
