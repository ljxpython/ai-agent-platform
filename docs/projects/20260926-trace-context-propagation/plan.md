# 跨服务链路追踪 - 实现契约

> 状态：方案就绪、实现未开始。本文替代旧讨论稿；不采用独立派发审计行、虚构 202 或重新包装全部响应正文的旧建议。

## 1. 范围与闭环定义

本期固定为请求 → 提交 → Run → 既有观测的关联闭环。已有观测启用并成功导出时，能从平台请求找到提交和 Run、定位下游观测，也能从 Run 反查关联请求。不承诺观测关闭、进程崩溃或导出失败时记录完整。

| 服务/组件 | 本期行为 |
|---|---|
| platform-api | 平台内部编号、现有委托关联字段、提交关系、审计查询、SSE 连接日志 |
| platform-web | 只验证现有错误编号消费与响应头访问；不改页面、展示或交互 |
| Runtime/GraphHarbor | 代码、配置、依赖、数据库、观测组件全部不改；只核验现有执行与导出 |
| 非目标 | 完整 W3C/OTel span、追踪库、Collector、观测平台、前端追踪页、后台补偿任务 |

不改变权限、幂等、审批、取消和 Run 状态判断。编号只关联事实，不是授权凭证。

## 2. 编号与生命周期

| 字段 | 明确规则 |
|---|---|
| request_id | API 为每个进入请求上下文的 HTTP 请求生成一次 uuid.uuid4().hex，32 位小写十六进制 |
| trace_id | 保留平台既有字段；本期等于 request_id，不解释为 OTel trace ID |
| platform_trace_id | JWT/下游 metadata 字段名，取当前 context.request.trace_id |
| submission_id | 已有 run_requests.id；同一幂等提交复用 |
| thread_id | 已授权的实际 Thread ID |
| run_id | 服务端实际返回或已保存的 Run ID；未知时省略 |
| parent_run_id | 既有审批恢复关系，不按时间推断 |
| interrupt_key | 现有提交中的 interrupt 标识，可能是集合摘要，不假称单个 interrupt ID |

HTTP 重试、SSE 重连、审批、取消分别生成新编号；同一提交通过 submission_id 关联多次 HTTP 尝试。忽略外部 x-request-id/x-trace-id 作为内部编号来源，不回显、不记录外部原值；本期不解析或透传 traceparent/tracestate/baggage 建立关联。

编号不进入幂等摘要、context_hash、授权判定或命令正文，不为追踪改变保存的执行快照。JWT 只填现有 request_id/platform_trace_id 两个可选 claim，版本、权限、TTL、算法、密钥机制不变。

成功、业务错误、401/403、422、安全 500 和 SSE 握手均返回内部 x-request-id/x-trace-id；错误正文已有 request_id 时与响应头一致。代理提前拒绝、外层 CORS 直接处理的预检不在应用编号保证内。

## 3. 当前工作树核查与精确入口

2026-09-26 重新静态核查，以下均为现状缺口，不代表改动已实施。路径均相对仓库根目录：

| 文件/符号 | 现状与实施要求 |
|---|---|
| apps/platform-api/src/platform_api/core/context/runtime.py::_request_id / _trace_id / build_request_context | 现状接受外部头；改为平台生成一次，后续只读同一上下文 |
| apps/platform-api/src/platform_api/entrypoints/http/middleware/request_context.py::request_context_middleware | reset 的 finally 目前只包围 return；扩到完整异常及取消路径 |
| apps/platform-api/src/platform_api/main.py::create_app | 增补 CORS expose_headers 两个编号头，保留已有 Origin 策略及配置 |
| apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::get_runtime_gateway_service | 当前读取未可靠赋值的 state.platform_trace_id；初始 read 与 scoped 闭包均改读 RequestContext |
| apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py::build_forward_headers | 当前外部 x-request-id 可优先；改为仅使用显式传入的平台编号 |
| apps/platform-api/src/platform_api/modules/runtime_catalog/presentation/http.py::get_runtime_catalog_service | Catalog 独立委托入口，传递当前请求关联字段 |
| apps/platform-api/src/platform_api/modules/runtime_catalog/bootstrap.py::build_runtime_catalog_service | 沿现有工厂转交可选 request_correlation |
| apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py::RuntimeCatalogService._runtime_headers | 将关联字段填入现有委托；保留本轮开始前用户的 service/test 改动 |
| apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py::RuntimeGatewayService | launch_runtime_run、cancel_thread_run 及其调用入口补可选关系回调 |
| apps/platform-api/src/platform_api/modules/audit/http_resolution.py::_resolve_metadata | 扩充写入白名单 |
| apps/platform-api/src/platform_api/modules/audit/service.py::AuditService.list_events | 扩充读取白名单及查询参数传递 |
| apps/platform-api/src/platform_api/modules/audit/contracts.py / router.py / repository.py | query contract、路由校验、授权后精确查询 |
| apps/platform-api/src/platform_api/entrypoints/http/middleware/audit_log.py::audited_body_iterator | 现状流取消/异常改写为 499/500；保留实际已发送 HTTP 状态，传输结果另记 |
| apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py::RuntimeStreamingResponse | 复用真实发送与 shielded aclose 路径记录 opened/closed |

Runtime 只读证据：apps/runtime-service/src/runtime_service/runtime/auth.py 已允许 request_id/platform_trace_id；observability/langfuse.py、observability/otel.py 有 metadata 消费路径。受信上下文到真实 worker 及导出仍待 T7 验证。不得把静态路径当作整条链路已通。

## 4. 请求上下文与 HTTP 日志

- _request_id 无条件生成；_trace_id 返回该编号。build_request_context 每请求只构造一次。
- 使用 request.state.platform_context 和既有 state.request_id；不新增第二份未同步的 state.platform_trace_id。
- set/reset 置于完整 try/finally，覆盖正常返回、普通异常、取消；普通异常复用[错误响应专项](../20260926-error-response-contract/plan.md)安全 500 构造，取消继续抛出。
- ContextVar token 只能由创建它的任务重置。流迭代若需绑定上下文，在迭代任务自行 set/reset；回调捕获当前 HTTP 请求的安全标量，不依赖可能已退出的中间件 ContextVar。
- 生命周期事件改为 http.response.ready：仅表示取得响应对象，记录状态码与响应准备耗时；SSE opened/closed 另记。
- 不为追踪重新包装全部 HTTP body；不改变现有 HTTP metrics 计时口径。
- 已发送 200 后异常或断连，审计 status_code 保留实际 200；result/close_reason 描述传输结果，不能据此判断 Run 失败。仅修正既有审计迭代器的状态记录，不新增迭代器、审计行或事务机制。

## 5. 两处委托签发入口

### 网关

get_runtime_gateway_service 从 context.request 捕获 request_id、trace_id，构造 request_id/platform_trace_id。初始 read 委托及 delegation_headers_factory 均传两字段；向 Runtime 的 x-request-id 使用相同内部编号。闭包仅属于当前 HTTP 请求，不跨请求缓存。

沿现有调用链覆盖 read、run-create、审批、取消及其他已有 scoped 委托，不修改 operation 选择、policy、权限、TTL 或资源约束。

### Catalog

presentation → bootstrap → RuntimeCatalogService 增加可选 request_correlation，仅包含 request_id/platform_trace_id；_runtime_headers 签发时填入。非 HTTP 调用可不传，不生成虚假请求编号。工厂原参数保持兼容。

build_forward_headers 不得从浏览器头回退取关联编号：显式 request_id 有值则设置 x-request-id，没有则省略；其余既有允许的非关联头行为不变。不得顺便转发 W3C 头。

本专项不增加 JWT claim；JWT 其他签发差异由[JWT 专项](../20260926-delegation-jwt-contract/README.md)独立处理。

## 6. 提交与 Run 的关系回调

RuntimeGatewayService 注入可选 on_correlation，同步、无返回值、默认 None；只接受固定事件名和下列安全关系值。HTTP 工厂捕获请求安全上下文，分别写结构化日志、合并 request.state.audit_metadata。复用既有 HTTP 审计写入时机、失败保护和事务，不新增派发审计行，不伪造 202。

回调数据只含 submission_id/thread_id/run_id/parent_run_id/target_run_id/interrupt_key、operation、outcome、reused_submission；HTTP 层补 request_id/platform_trace_id、已授权 project_id、correlation_version=1。未知字段省略，拒绝任意业务正文和异常原文。attempt 没有结果时省略 outcome；operation 沿用实际业务动作的现有委托 operation，不新造 JWT operation。

| 落点 | 固定事件 | 事实及结果 |
|---|---|---|
| launch_runtime_run 成功 reserve 后、上游调用前 | runtime.submission.attempt | submission、thread、是否复用、已知父 Run/interrupt |
| 已保存 Run 的幂等复用分支 | runtime.submission.result | outcome=deduplicated，使用保存的实际 Run |
| 新提交获上游确认 | runtime.submission.result | outcome=accepted，实际 Run |
| 明确拒绝 | runtime.submission.result | outcome=rejected，已有安全错误分类，不记异常原文 |
| 超时、响应丢失、结果无法确认 | runtime.submission.result | outcome=unknown，不等于未执行 |
| cancel_thread_run 返回/异常 | runtime.cancel.result | target_run_id，accepted/rejected/unknown；accepted 只表示取消请求获接受 |

实施细节：

1. reserve 事务返回记录及是否复用这一事实；IntegrityError 重试仍沿现有算法，只补观察字段。reserve 成功前的鉴权失败、参数错误、幂等冲突不能伪造 submission_id 或派发事件。
2. attempt 覆盖后续校验、委托构造、复用和上游调用分支；正常返回或可捕获失败应有一个 result。进程崩溃/强制终止不保证 result，不引入后台补偿。
3. 已保存 run_id 即是复用事实；后续读取 Run 详情失败也不能抹掉已知关系或暗示会再创建 Run。上游已确认 run_id 后本地 mark 失败，同样保留已确认接受事实；不借观测改变原异常传播。
4. 分类依据已知阶段及现有安全错误分类；未发上游的确定性拒绝是 rejected，发出后无法判断是 unknown。取消不吞掉 CancelledError；无法确定执行结果时只尽力记录 unknown。
5. 日志失败与 metadata 合并失败独立保护：一项失败不阻止另一项，不改变业务结果、不重发用户动作，不新增观测重试队列。不得用捕获 BaseException 的方式吞掉取消。
6. 审批使用实际返回 Run 与既有 parent_run_id/interrupt 标识，不改恢复算法。repository.mark(request_id, ...) 的内部参数实际上是 submission ID，本期不重命名；输出字段必须叫 submission_id。
7. A 请求结果未知、B 请求重试成功时，两者 request_id 不同而 submission_id 相同。下游保存的 metadata 才是实际执行编号来源，可能来自 A 或 B；查询所有尝试，不能强称首请求即来源。
8. 多次回调对当前 HTTP 审计行增量合并，result 更新 outcome，缺省字段不清空已知关系。不追加独立审计行。流关闭时若 HTTP 审计已经写出，不补写/回写；完整连接生命周期以结构化日志为准。

## 7. SSE 连接事实与专项接口

固定事件 runtime.stream.opened、runtime.stream.closed。公共字段为 request_id/platform_trace_id/project_id/thread_id/stream_kind，已知时 run_id；关闭加 duration_ms、close_reason。stream_kind 固定区分 thread、run；线程流不永久绑定单个 Run。

复用 RuntimeStreamingResponse 的实际 ASGI 发送和现有关闭路径；成功发送 http.response.start 后才记 opened，不等待业务首帧。握手失败或 start 发送失败不记 opened；对已 opened 的连接最多一条 closed。duration_ms 从成功 start 计至统一关闭；没有 opened 时不伪造一对生命周期。

| close_reason | 判定 |
|---|---|
| eof | 正常迭代结束 |
| client_disconnect | 已确认客户端断连 |
| upstream_error | 上游读取/传输异常 |
| frame_rejected | SSE 专项现有解析器明确拒绝帧 |
| closed | 明确主动释放连接 |
| unknown | 取消或异常无法可靠区分来源 |

由[SSE 专项](../20260926-sse-event-contract/plan.md)解析器提供可选结束原因回调，将 frame_rejected 传给同一连接状态；追踪侧不重复解析流、不增加正文解析器。具体原因一经确定，finally 的通用 closed/unknown 不得覆盖；幂等关闭标记确保仅一次日志。

创建并订阅 Run 的入口通过提交回调取得实际 Run ID。握手阶段错误走正常错误编号出口；已发 200 后仅记录传输结果，不能改记 500。保持既有 shielded 清理，不在别的任务 reset ContextVar token。

不记录事件正文、模型输出、工具参数、任意 namespace。连接结束不等于 Run 结束，释放连接不触发取消。线程持续保活、订阅恢复和显示由 SSE 专项负责，本专项不引入默认折叠或改变交互。

## 8. 审计写入、读取与精确查询

写入 _resolve_metadata 与读取 list_events 两处白名单同时扩充：

platform_trace_id、submission_id、thread_id、run_id、parent_run_id、target_run_id、interrupt_key、operation、outcome、stream_kind、close_reason、reused_submission、correlation_version。

correlation_version 固定整数 1，reused_submission 为布尔值；其余为已确认安全标量。request_id 沿已有列，project_id 沿已有授权项目列。所有关系由平台上下文或服务端事实产生，不允许正文覆盖；已有 metadata 允许项保留。

扩展现有 GET /api/audit，保留 project_id、分页、排序及其他查询语义：

| 参数 | 校验及匹配 |
|---|---|
| request_id | 1—64 字符、无控制字符，精确匹配已有列，兼容历史非 32 位编号 |
| submission_id | UUID，规范化为现有 run_requests.id 字符串，精确匹配 metadata |
| thread_id | 1—128 字符、无控制字符，精确匹配 metadata |
| run_id | 1—128 字符、无控制字符，匹配 metadata 的 run_id/target_run_id/parent_run_id 任一 |

- 不同参数 AND；run_id 内部三个字段 OR，并整体括号化后与授权 project_id 等过滤 AND；列表和 total 使用同一过滤集。
- submission/thread/run 任一存在时，created_from/created_to 必填，起点不晚于终点，窗口不超过 7 天；边界均含。恰好 7 天允许，超过拒绝。request_id 单独查不强制窗口。
- 沿现有时间字段；比较前统一时区，历史无时区输入按既有 UTC 存储约定解释，避免 naive/aware 混比。控制字符按 Unicode Cc 拒绝，不对 ID 静默截断。
- router 将字段传给 ListAuditEventsQuery，在请求边界校验；模型跨字段校验失败必须转换为公开 422 验证响应，不能让路由内构造模型的 ValueError 漏成 500。
- 保留现有平台审计权限及带 project_id 的项目审计授权；只有编号、没有权限不得查询。不能把关联过滤当作授权条件。
- 通过 SQLAlchemy JSON 标量比较实现，验证 SQLite 与 PostgreSQL 实际执行；不使用数据库专属 JSON 文本拼接或任意路径查询。
- 历史缺字段视为不匹配相关 metadata 条件，不报错；request_id 仍可查。不迁移、不回填旧数据，不新增表或索引。
- 无模糊扫描、任意 JSON 查询或凭编号越权。无索引性能不达标则另行评审，不能擅自执行 DDL。

## 9. 实施顺序、集成与兼容回退

顺序：T1 → T2/T3 → T4 → T5/T6 → T7 → T8，详见 tasks.md。错误响应专项公共安全 500 和错误编号契约是 T1 集成前置；SSE 结束原因回调是 T6 协作接口。同文件按最新工作树整合，不覆盖对方实现或用户改动。

后续仅发布包含变更的 API 产物，Runtime/Web 无本专项版本升级要求。实施前按当前锁定 Runtime 契约验证两个现有可选 claim；API 新旧实例混合期间旧实例可能沿旧编号行为，不能宣称全量内部编号保证。历史审计读取兼容；新增查询参数不保证在回退后的旧 API 上仍可用，调用者应恢复旧查询方式。

回退只恢复前一 API 产物；新增 metadata 对旧读取白名单无害，无表、索引、迁移或数据库回滚。不取消、重发或重签已有 Run；观测 metadata 保持当时事实。回退后不再承诺新关联字段齐全，真实在途 Run/SSE 必须按 verification.md 验证。

本轮只落文档、不执行部署或回退。任务完成与验收状态分开，缺环境按未验证记录。
