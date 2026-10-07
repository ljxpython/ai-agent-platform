# 03 安全诊断查询

## 目标

让有当前Thread读权限的人从平台查询某个真实Run的安全观测摘要，供现有轨迹Inspector排障。Run事实仍从GraphHarbor读取，观测仍由Langfuse保存；不新增Run表、事件库或观测数据库。

**状态：** 后端已完成（done），Q01-Q05及后端Final于2026-10-07完成；2026-10-06用户已批准DTO/operation/错误出口。前端F01-F04和QV09/QV10的浏览器部分待同事实施，整项目partial。

## 方案设计

### 查询链路

```text
Web现有轨迹Inspector
  -> Platform API GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
    -> 当前项目权限 + Thread ACL + 原生Run存在/归属校验
    -> 签发 diagnostics-read（绑定当前租户/项目/graph/Thread）
      -> Runtime GET /internal/threads/{thread_id}/runs/{run_id}/diagnostics
        -> 校验签名和限定scope
        -> Langfuse有界查询，核对trace的可信scope/run元数据
        -> Runtime安全摘要
    -> Platform重新白名单投影 + 加上本次查询request_id/原生run_status
```

Runtime查询不能直接沿用任意Thread最后模型错误。历史Run即使在当前Thread内，也只读取该run_id的trace；权限失效、资源删除或读不到原生Run时先拒绝，不从trace后端找旁路数据。

### 没有新存储的理由和限制

现有Langfuse已经保存graph/model/tool观察，本期复用。按session_id=thread_id和已存在的run_id/scope metadata筛选；02的新trace优先用SDK可复算的确定性trace ID，老trace走有界候选查找。不能假设已有旧trace已采用新ID。

- 最多50条trace候选，最多100条相关observation；总预算2秒，禁止无界“拉完所有Thread历史”。超出上限返回partial/truncated，不静默认定该Run不存在。
- 使用已安装的 `langfuse.api.client.AsyncLangfuseAPI`，`trace.list/get` 和 `observations.get_many` 的异步方法及 `request_options` 已核对。复用应用级 `httpx.AsyncClient`，由lifespan关闭，不每请求新建；不用同步SDK或线程池。整个查询以 monotonic deadline 限2秒，每次HTTP使用剩余预算且关闭SDK额外重试，取消必须传到底层请求，避免超时后仍积累后台工作。
- 所有候选必须同时核对tenant_id/project_id/thread_id/run_id以及固定graph_id的受信元数据；缺失或冲突者不公开。404可能是尚未导出，不代表Run未执行。
- 不要求SDK同步flush来满足用户查询，不在模型异常路径发额外HTTP回写。
- exporter关闭/失败、历史未带可信scope、保留期到期、进程崩溃时可能无法返回分类；页面呈现不可用，不构造伪成功记录。

查询只选必要的 core/metadata/time 字段，按目标 Langfuse 服务端支持的字段筛选接口验证；不主动拉取 prompt/input/output。01 的 `runtime.model_call.failed`、`runtime.graph.completed` 和02 的 startup事件是新增DTO字段的来源，必须逐条校验schema/event/可信scope，不从provider原文重新分类。SDK generation仅提供既有轨迹关联，不与安全event重复计算模型失败。

如果业务要求关闭观测也必须在刷新后查完整原因，或要求exactly-once错误审计，本方案不够。届时单独评审Runtime自有诊断存储和保留/清理策略，不在此次偷偷增加迁移和状态副本。

### 新增Delegation operation

建议新增 `diagnostics-read`，仅允许上述Runtime内部GET。复用短时Delegation v2/HS256；scope仍是当前五个键，不新增run_id claim，run_id为该授权Thread内的只读目标。

- 必须绑定tenant/project/assistant_id/thread_id；任何scope与路径或观测数据不一致均拒绝。
- 不访问原生GraphHarbor资源、模型连接、工具、workspace、Thread update；`run-create/read/suggestions-generate`等token不能访问新的diagnostics内部路由。
- Platform仍需要 `project.runtime.read` + 该Thread `read`，不能用超级管理员前端判断或Langfuse凭据替代ACL。
- 服务账号同样校验当前credential/project授权；不记录token，不把用户凭据发给Langfuse。
- 双端枚举、Runtime原生资源禁止清单、Delegation contract测试一起更新。按名称集合断言，不增加固定数量/下标切片依赖。

不选择放宽`run-create`来更新metadata；也不把“普通read委托能读原生Run”隐式解释为能读取全部观测payload。新增operation的审核和生产发布属于本治理项目。

### 公共契约

唯一新增的浏览器接口：

```text
GET /api/langgraph/threads/{thread_id}/runs/{run_id}/diagnostics
Authorization: 平台现有登录认证
x-project-id: 当前项目UUID
响应 Cache-Control: no-store
```

thread_id/run_id接受合法UUID，不支持浏览器传tenant/provider/trace URL/供应商凭据/自选观测host。不改变已有Run GET/List结构；诊断返回单独DTO。

```json
{
  "version": 1,
  "thread_id": "11111111-1111-4111-8111-111111111111",
  "run_id": "22222222-2222-4222-8222-222222222222",
  "run_status": "error",
  "request_id": "0123456789abcdef0123456789abcdef",
  "availability": "available",
  "unavailable_reason": null,
  "correlation": {
    "execution_request_id": "abcdef0123456789abcdef0123456789",
    "platform_trace_id": "abcdef0123456789abcdef0123456789"
  },
  "trace": {
    "provider": "langfuse",
    "trace_id": "11223344556677889900aabbccddeeff00",
    "url": null
  },
  "graph_executions": [
    {
      "observation_id": "execution-1",
      "outcome": "failed",
      "error_code": null,
      "duration_ms": 340.2
    }
  ],
  "model_errors": [
    {
      "observation_id": "model-call-1",
      "scope": "primary",
      "namespace": [],
      "code": "provider_rate_limited",
      "error_type": "RateLimitError",
      "provider_status": 429,
      "duration_ms": 120.5
    }
  ],
  "startup": {
    "duration_ms": 48.1,
    "phases": [
      {
        "name": "factory.model_connection",
        "ordinal": 0,
        "outcome": "completed",
        "started_at": "2026-10-06T00:00:00.000Z",
        "ended_at": "2026-10-06T00:00:00.020Z",
        "duration_ms": 20.0,
        "error_code": null
      }
    ]
  },
  "truncated": false
}
```

样例为已实现v1的说明数据，实测样例另行保留。`run_status`来自同一请求授权读取的原生Run；`graph_executions[].outcome`是实际观察到的图执行，不覆盖Run状态，也不按最后模型失败推断最终原因。首期graph/phase的error_code固定null，不能把一次429写成Run的最终failure_reason。

字段约束：model_errors最多20条、graph_executions最多10条、startup.phases最多16条；namespace最多8段且每段128字符；error_type为string|null，observation_id等字符串上限128；duration为非负有限number或null，拒绝NaN/Infinity；request_id为非空查询编号，执行关联缺值为null；只有固定机器码允许公开。provider正文、message、stack、prompt、input/output、tool payload全部没有公开字段。

`graph_executions.outcome`仅允许 `success/failed/timeout/cancelled/interrupted`；`error_code`为01固定码或null，无法证明确切来源时用null。startup为null或该Run最后一次**可明确归属的构图**记录，阶段outcome为 `completed/failed/cancelled/incomplete`，起止时间为合法UTC时间或null。多次构图无法确定对应关系时startup=null并返回partial，不拼成一组总耗时；按实际采集到的总计event取duration，不能把重叠phase相加。`run_status`沿用原生SDK字符串，未知值只显示未知，不据此改变聊天状态。

`trace`没有已验证关联时为null；即使存在，`url`首期固定null。外链可能让用户进入整个共享Langfuse项目，平台ACL不保护离开的页面；不以“仅返回URL不返回密钥”就判定安全。02的新Run可以多个execution共用trace；老Run有多个trace且不能选定时返回partial、trace=null，不挑第一个冒认唯一来源。

### 不可用与失败语义

| 结果 | HTTP/字段 | 前端和平台行为 |
|---|---|---|
| 观测可读且有本期字段 | 200 available | 展示安全摘要，仍以原生Run/SDK判断执行状态 |
| 旧数据/部分字段/有界截断 | 200 partial | 有什么展示什么；缺duration写未知，保留truncated提示 |
| Langfuse未开启 | 200 disabled，reason=not_configured | 仍返回已核验Run ID/status；没有分类不等于没有错误 |
| 尚未导出/保留期到期/缺可信scope | 200 unavailable，reason=not_recorded | 用户主动刷新可重试；不创建Run、不循环刷历史 |
| Langfuse网络故障或限流/预算超时 | 200 unavailable，reason=backend_unavailable | 返回安全降级；不得把provider原始HTTP响应作为平台响应 |
| 当前项目/Thread权限拒绝 | 原有403/404安全Envelope | 停止该scope查询，复用现有权限处理，不返回诊断 |
| Run不存在或不属于Thread | 原有404安全Envelope | 不查观测后端 |
| 平台签发失败/Runtime委托拒绝 | 503/502既有安全Envelope | 安全故障不得吞成disabled；不登出、不重试模型 |
| Runtime整体不可达 | 502/504既有安全Envelope | 仅诊断面板报错，可重试查询，不影响对话/Run |
| DTO/版本无效 | 安全502或unknown展示降级 | 不透传任意对象，不把格式错误当授权撤销 |

`request_id`是本次GET请求ID；`correlation.execution_request_id`是trace中原执行请求ID，必须分开。字段缺失就为null，不拿当前查询ID冒充执行ID。

### 公共JSON/SSE错误投影

R05已批准：沿既有 `redact_runtime_private_fields/_redact_event_value` 增加明确执行错误槽位投影，保留正常messages/tool正文。

- 原生lifecycle.error、Thread.error、state.tasks的执行错误，仅保留允许type、稳定code和固定安全message；未知message固定为“运行异常”，不公开str(exc)/stack/body。
- Protocol/v3的lifecycle params.data、debug task_result.payload.error及checkpoints tasks[].error，与普通error/lifecycle各按锁定形状处理；流已经200不拼HTTP Envelope，不丢终态或改event/sequence/id。
- 已有HTTP握手前Envelope保持原行为；新机器码只在用途明确时加入error catalog，分类码不会自动成为HTTP状态映射。
- 审批/取消/工具的正常结构不改。回归真实SDK消费者，尤其nested error不能误覆盖SDK解析。
- 根callback模型分类只是观测来源，不能把错误消息投影与Langfuse查询绑定，避免外部追踪故障拖住每个SSE事件。

GraphHarbor自身记录的原始异常日志不在本仓库修改面；若R05要求全栈采集端不保留原文，须先明确上游/采集端负责人和验收，不把本仓库出口修复当该问题已解决。

### 实际代码落点

下表 Runtime 路径前缀为 `apps/runtime-service/src/runtime_service/`，API 路径前缀为 `apps/platform-api/src/platform_api/`；新符号均明确标注。

| 服务/文件 | 既有或拟新增符号 | 要补的代码 |
|---|---|---|
| Runtime `observability/query.py`，新增 | `query_run_diagnostics` | 有界Langfuse候选/observation查询，可信scope复核，DTO投影；不读GraphHarbor业务表 |
| Runtime `http/diagnostics.py`，新增 | `run_diagnostics_endpoint` | UUID/operation/scope验证；调用查询；固定response model |
| Runtime `webapp.py:lifespan/include_router` | query client生命周期 | 注册内部route；独立关闭查询client，导出初始化仍保留明确错误处理 |
| Runtime `runtime/auth.py:_parse_scope`、`auth/platform.py:deny_image_scope_on_server_resources` | operation集合/原生资源边界 | 允许新内部operation，原生资源继续拒绝 |
| API `core/security/tokens.py:create_runtime_delegation_token` | 现有签发函数 | 增加operation合法枚举；不新增claim或新算法 |
| API `modules/runtime_gateway/application/ports.py` | 新upstream方法 `get_run_diagnostics` | 沿既有Protocol添加一个真实消费方法，不建新通用port层 |
| API `adapters/langgraph/runtime_gateway_upstream.py` | 新 `get_run_diagnostics` | URL转义、既有require_json、超时/安全上游错误映射 |
| API `modules/runtime_gateway/application/service.py` | 新 `get_thread_run_diagnostics` | `_load_thread`授权、Run归属、`_thread_upstream(...,operation="diagnostics-read")`，拼安全response |
| API `modules/runtime_gateway/presentation/http.py` | 新GET endpoint/response model；错误投影 | 薄路由、no-store、安全JSON/SSE出口，不全仓重构service |
| API `adapters/langgraph/sdk_client.py:redact_runtime_private_fields` | JSON私有/错误出口 | 按固定错误槽位移除原文，保持其他正常字段 |
| Web | 只在 `frontend-handoff.md` 规划 | 当前开发者不写页面代码 |

新接口参数/模型放既有HTTP/查询文件即可；只有实现超过粒度规范且职责确实独立时再拆contracts.py，不先造额外SDK和异常基类。

## 任务拆分

### Q01 权限与契约冻结，预计0.5人天

- [x] **改动内容：** 人工批准DTO/operation和错误出口范围；双端签发/校验/原生拒绝。
- **代码位置：** Runtime `runtime/auth.py`、`auth/platform.py`；API `core/security/tokens.py`；现有delegation测试。
- **预期结果：** 只有Thread绑定的diagnostics-read能访问新内部GET，不能反向访问模型/工具/原生资源。
- **验证项：** 多operation名称集合矩阵，错tenant/project/thread/graph、服务账号撤权、过期/伪造token。
- **状态：** done；用户2026-10-06批准。

### Q02 Runtime查询与生命周期，预计0.5人天

- [x] **改动内容：** 复用公共SDK查询，限候选/时间、可信metadata交叉校验、统一安全摘要。
- **代码位置：** 拟新增 `observability/query.py:query_run_diagnostics`、`http/diagnostics.py:run_diagnostics_endpoint`；`webapp.py`。
- **预期结果：** 老trace可partial；新trace精确关联；观测不可用不改变Run；client不泄漏。
- **验证项：** 相关/不相关/伪造trace、错误body、超时/限流/分页上限、关闭和并发隔离。
- **状态：** done。

### Q03 Platform授权聚合，预计0.5人天

- [x] **改动内容：** 新GET复用Thread授权和Run读取，再签发新operation；不在事务中等待HTTP。
- **代码位置：** 上表API port/upstream/service/router。
- **预期结果：** 输出可直接给同事接入；当前请求ID与原执行ID分开；拒绝先于Langfuse查询。
- **验证项：** `tests/test_run_diagnostics.py`，许可、403/404、Run归属、代理失败、no-store、DTO上限。
- **状态：** done。

### Q04 公共错误原文治理，预计0.5人天

- [x] **改动内容：** 明确JSON/Protocol/普通SSE错误槽位投影，保留帧顺序与终态。
- **代码位置：** `sdk_client.py:redact_runtime_private_fields`、网关HTTP `_redact_event_value/_redact_sse_frame`及相关lifecycle归一化入口。
- **预期结果：** provider正文/traceback不在浏览器错误出口；正常messages/tool响应不被误删。
- **验证项：** canary测试覆盖Thread/Run/state/history、Protocol/普通SSE、错误嵌套SDK、合法工具message；真实SDK链路。
- **状态：** done；v3 debug执行错误槽位遗漏已补充回归。

### Q05 交接、文档与专题Final，预计0.5人天

- [x] **改动内容：** 实现后回写交接真实字段；更新网关/Delegation/error/SSE/trace标准的必要条目；完成授权查询与故障链路。
- **代码位置：** `frontend-handoff.md`；`apps/platform-api/docs/standards/runtime-gateway-interface-standard.md`；相关 `docs/standards/`、显式HTTP route矩阵和error catalog。
- **预期结果：** 单独完成03后API与Runtime真实契约可验，未接前端仍不标整项目done。
- **验证项：** 下表QV01-QV12的后端部分、回退门禁、前端mock所需真实契约样例；前端mock实现归F01，浏览器验证归F04。
- **状态：** done，2026-10-07；后端Final与真实交接样例已完成，前端mock/浏览器部分仍归F01/F04。

## 验证要求与记录

| ID | 层次 | 场景与预期 |
|---|---|---|
| QV01 | 单元 | DTO白名单/数组与字符串上限；未知版本/码、NaN/无限值不公开 |
| QV02 | 单元 | identity/run ID来源；查询request ID与execution request ID不同且缺值不伪造 |
| QV03 | 契约 | diagnostics-read仅限内部GET；其他token拒绝；不得访问原生/模型/文件/工具 |
| QV04 | 授权 | 两租户、两项目、同项目其他用户、共享Thread读权限、被撤权服务账号；按当前ACL拒绝 |
| QV05 | 集成 | Platform先查Thread/Run，错Run/404/403时从未调用Langfuse |
| QV06 | 集成 | 老trace/new确定性trace、多个execution、分页上限；只返回同scope同Run记录，必要时partial |
| QV07 | 故障 | 禁用、未导出、过期、Langfuse429/503/timeout、Runtime拒绝；降级与安全故障分开 |
| QV08 | 安全 | query/JSON/SSE错误槽位无canary正文/stack/body/secret；正常工具含error字样仍完整 |
| QV09 | E2E | Web→API→Runtime→本地provider stub429→原生Run error→Langfuse→安全摘要；真实错误关联ID吻合 |
| QV10 | E2E | primary失败/fallback成功、模型恢复后工具失败、并行子任务、用户取消/HITL、断线刷新；不误标终态 |
| QV11 | 性能 | 并发50次查询，2秒上游预算、候选上限、pool释放；记录p50/p95/内存，确认无执行影响 |
| QV12 | 回退 | 关闭查询入口/恢复前版采集；普通Run/SSE/审批/取消继续；新旧缺字段均安全，不需要DB回滚 |

E2E同时包括本地受控失败链路和目标实际配置的provider正常/失败smoke。新的provider协议错误不能靠通用Exception替身验收；故障注入在隔离provider stub/独立服务完成，不发生产敏感数据。

计划命令，新增文件实施后才存在：

```bash
# Runtime服务目录
uv run pytest "tests/observability/test_run_diagnostics.py" "tests/runtime/test_platform_auth.py" -q
uv run ruff check "src/runtime_service/http/diagnostics.py" "src/runtime_service/observability"
# Platform API服务目录
uv run pytest "tests/test_run_diagnostics.py" "tests/test_runtime_gateway_http_matrix.py" \
  "tests/test_error_response_contract.py" "tests/test_runtime_upstream_errors.py" -q
uv run ruff check "src/platform_api/modules/runtime_gateway" "src/platform_api/adapters/langgraph" "src/platform_api/core/security/tokens.py"
```

最终需运行三服务完整相关回归并保留真实Run与查询样例。原SSE容量/JWT消息回查遗留不在本次自动完成，也不为这些遗留把标准草案误升级为active。

### Phase记录

| 任务 | 日期 | 实际Phase证据 |
|---|---|---|
| Q01 | 2026-10-06 | 用户批准；API跨环境JWT契约5 passed/50 subtests，Runtimeoperation/内部GET/Thread与credential测试通过；生产TTL仍60秒。 |
| Q02 | 2026-10-06 | Runtime query/http测试涵盖官方异步SDK参数、旧trace fallback、分页/预算、scope核验、故障与安全投影，纳入240项定向回归。 |
| Q03 | 2026-10-06 | API组合63 passed/4 skipped/524 subtests；Thread/Run授权先于查询、Run归属、DTO白名单、no-store/关联ID验证。 |
| Q04 | 2026-10-07 | debug task_result实际错误槽位补齐后，API diagnostics/http matrix/error/SDK回归37 passed/1 skipped/311 subtests；Protocol/v3/普通帧ID与正常工具内容保留。 |

补充SDK/gateway组合：38 passed/10 subtests。skip保持未执行。合规检查：沿当前ACL与只读委托；无新增表、Thread回写或观测直连浏览器；错误出口投影与查询独立，调用Langfuse不占DB事务。Q05的后端Final、性能和真实交接材料于2026-10-07完成。

### Final记录

2026-10-07：**本专题后端Final done；浏览器部分未执行**。实际命令、版本、失败测量和边界见 [后端验收](implementation/02-backend-verification.md)，响应/安全HTTP/Run ID见 [最终JSON](implementation/backend-runtime-evidence.json)。

- QV01-QV08：DTO/operation/当前ACL/安全槽位测试见Phase；独立原生链路验证错Run404、跨项目403、非owner拒绝→共享read允许→真实撤权拒绝。ordinary debug task_result的实际错误槽位经修正后无canary，普通message/tool内容保留。
- QV09/QV10：API→Runtime API/Worker→本地provider429→Langfuse→安全GET已验；fallback恢复、后续工具失败、并行子任务、同Thread多Run和HITL/取消均有实际Run材料。Web→Inspector段和浏览器断线/刷新由F04/FV07-FV09接续，不据此标整链路done。
- QV11：最终50并发全部HTTP200，但50条均为Langfuse429引起的unavailable；整体p50/p95=6819.31/7535.70ms，Langfuse段268.83/651.07ms，峰值RSS约544MiB。只证实有界安全降级及原生Run不变，未证明50并发完整诊断容量；初次全部ReadTimeout及独立查询复测证据一并保留。
- QV12：关闭采集后正常原生Run成功、查询disabled；另按固定基线源码恢复采集/reference/workflow工厂和Runtime应用、撤下平台诊断入口，六个隔离回退场景passed（普通Run/SSE、审批恢复、拒绝恢复、取消及入口/采集核验），见 [回退证据](implementation/rollback-evidence.json)。无记录和连接故障200 unavailable，安全HTTP502/503/504仍是Envelope，不吞成disabled；旧trace、缺字段、取消/预算和pool关闭由单元/lifespan测试覆盖，无诊断数据库回滚。未执行现役服务部署回滚。

无后端实现阻塞。现有供应商限额是已批准的降级边界；需要更高完整诊断容量须调整观测服务限额并在独立环境按SLO重验。前端mock与实际浏览器Final仍待同事完成。
