# 平台接口、权限与服务间契约

## 目标

提供独立于聊天传输的用量分析API，统一项目范围、显示名称、数据校验、错误和审计。新聚合能力只暴露获批数字统计；Run明细继续复核既有会话访问规则。

## 方案设计

平台经Runtime受控接口读取用量、双方职责分工已由用户于2026-10-11确认，依据见[02决策记录](02-runtime-aggregation.md)。完整方案及必要B01优化获批，权限、数字披露、HMAC和整链路admission已实现；不新增Runtime数据库连接。2026-10-12公开容量两轮通过、B01解除，证据见05。

### 公开接口

| API（已实现） | 用途 | 授权 |
|---|---|---|
| `GET /api/usage/dashboard` | 当前tenant的跨项目summary/趋势/排行；省略project_ids表示授权范围内全部非删除项目 | `platform.usage.read` |
| `GET /api/projects/{project_id}/usage/dashboard` | 单项目相同报表 | `project.usage.read`，带明确project_id |
| `GET /api/projects/{project_id}/usage/runs` | 期间内运行候选明细，过滤当前Thread ACL后分页返回 | `project.usage.read`并按现有Thread read规则逐批校验；治理接管访问仍按现有审计 |
| 现有 `GET /api/langgraph/threads/{thread}/runs/{run}/usage` | 完整一次Run明细及当前native状态 | 原授权链、Thread绑定usage-read；本项目不改变该接口 |

平台视图选择项目后，可用项目路线钻取；只有platform聚合权限而无法通过现有Thread读规则时，只能查看已获批的数字统计。不能将 `platform.usage.read` 当作 `project.runtime.read` 或Thread接管授权。

没有新价格CRUD；已存在的模型价格编辑页继续按 `platform.model.write` / `project.runtime.write` 等原权限判断，看到缺价不自动获得改价权限。

### Query规则

| 字段 | 规则 |
|---|---|
| `from/to` | 同时必填，带UTC时区的ISO8601，`0 < to-from <= 90天`；服务端不依赖浏览器本地时区 |
| `timezone` | `Asia/Shanghai`或`UTC`，默认前者；只影响桶和显示，不改变时间过滤 |
| `granularity` | `day`默认；`hour`仅≤7天，最多200桶 |
| `project_ids` | 仅平台接口，采用重复query参数，最多200；服务端解析UUID且全量授权；项目路由拒绝此参数并以path项目为准 |
| `model_id` | 可选catalog UUID；未映射组用明确枚举 `model_mapping=unmapped`，与model_id互斥 |
| `agent_id` | 单项目或平台仅选择一个项目时可选平台UUID，API解析为该项目graph_id；多项目查询拒绝agent_id，排行点击具体Agent先限定其项目 |
| `purpose/scope` | purpose=agent/summarization/memory_extraction/vision/other；scope=primary/subagent/auxiliary；未提供表示全部已采集调用 |
| `group_by` | project/model/agent/purpose/scope；项目视图不显示无意义的单项目排行 |
| `rank_by/top_n` | known_total_tokens/known_cost_usd/observed_call_count；默认Token和10条，最多50条 |
| `limit/cursor` | runs专用，默认50、最多200；公开cursor认证加密，绑定actor/credential/tenant/project、筛选摘要、排序和首请求截止时刻，跨身份或变筛选后旧cursor拒绝 |

接口拒绝未知query键、非法UUID、反向窗口、超范围和冲突筛选。过滤model_id不改变其当前费用授权；只允许所选scope内安全统计。source/user/status筛选未采集到可信事实，V1不开放。

三个GET分别冻结参数白名单：dashboard接收时间/时区/粒度、业务筛选和排行字段；runs仅接收from/to、model_id/model_mapping/agent_id/purpose/scope、limit/cursor，不接受group_by/rank_by/top_n/granularity/project_ids。时间均返回UTC值，时区展示由报表window确定；内部两个POST也按用途各自strict解析，避免一个胖query类型放过无效参数。

### 报表DTO（独立于既有RunUsageV1）

新类型命名 `UsageDashboardV1`，不往Chat v1塞入平台字段。实现时冻结JSON schema及完整/部分/空/关闭/不可用/缺价等fixtures。

```text
UsageDashboardV1
  version: 1
  scope: { kind: platform|project, project_ids, covered_project_count }
  window: { from, to, timezone, granularity, time_basis: model_call_started_at }
  as_of: UTC timestamp
  availability: available|partial|disabled|unavailable
  unavailable_reason: null|not_recorded|backend_unavailable
  coverage_basis: recorded_native_runs
  summary:
    tokens / known_tokens: 复用TokenCounts语义
    cost: 复用UsageCost的USD/Decimal-string/unknown语义
    coverage: observed/reported/missing/incomplete/priced、degraded、字段已知次数
    recorded_run_count / open_collection_run_count
    zero_call_manifest_count|null: 按manifest开始时间单独计数；model/purpose/scope过滤时为null
    cache_read_ratio / ratio_sample_call_count: 可空比值及对应样本数
    average_tokens_per_recorded_run: 完整期间total / 同数据集distinct Run，分母0或不完整时null
  previous_window: { window, summary, total_token_change_ratio|null }
  series: 最多200个 { from, to, tokens, known_tokens, cost, coverage }
  breakdown: { group_by, rank_by, items: 最多50条, other|null }
  facets: 授权project/model/agent选项，分别有truncated标识
  collection: { enabled_now, first_recorded_at, last_recorded_at, excluded_operations }
  request_id: 平台生成
```

各series/group的Token字段和cost保留完整/已知小计语义，不只返回一个裸数字。`other`只表示未进入TopN的该维度调用，不装入无权限项目；时间点补齐不代表供应商全覆盖。名称为安全纯文本，UUID/graph_id回显经过scope验证。

`UsageRunPageV1`包含 `items/next_cursor/as_of/request_id`。每行限project/thread/run/graph安全ID、授权Agent名、窗口内Token/已知成本、调用coverage、first/last_matching_call_at。没有Prompt、会话标题、用户信息、模型连接、JWT、pricing_snapshot或parent callback栈；native状态仅在用户打开既有单Run详情时读取。

运行page排序不提供任意列排序；先按最新消费时间做稳定keyset，消耗排行在报表维度层完成。避免第一版为了“所有运行按金额排序”新增可变快照排名/长事务/缓存系统。

### 权限模型与新增数据边界

| 权限 | 推荐初始角色 | 可读取范围 | 不授予的能力 |
|---|---|---|---|
| `platform.usage.read` | platform super_admin、operator | 当前tenant、明确存在的项目数字聚合、项目/模型/Agent统计标签 | 任意Thread/文件/模型凭据读、跨tenant、价格修改 |
| `project.usage.read` | project admin、editor | 该项目数字聚合，包括项目内私有Thread消费数字 | 其他项目统计、任意私有会话正文、新执行动作 |
| 既有Thread read | 当前IAM + thread_access规则 | 明细候选行及已有RunUsage | 不由聚合权限替代 |

获批并实现的平台 `platform_viewer`、项目 `project_executor` 不新增聚合权限；当前系统没有 `project_viewer`。executor仍可按原规则看自己的RunUsage。服务账号必须通过当前凭据/项目grant获得具体权限；网络位置不能代替授权。

2026-10-11 用户已批准：汇总保留有效项目中已删 Thread 的数字消费，admin/editor 可看项目私有 Thread 的数字统计；运行明细仍按内容 ACL。该授权来自本项目明确评审，已同步服务活规范，不借聚合扩大内容读取。

平台参数先解析tenant，再从服务端项目库求范围，校验每个显式project_id。没有有效项目返回合法空范围页面；超200范围报错要求筛选，不悄悄缩成前200项。登录、项目禁用/删除、成员撤权在每次请求核对；HTTP等待前关闭Session，返回前对身份/权限版本和项目范围作短事务复核，避免撤权期间返回迟到结果。

### Run明细的ACL分页

1. API把已授权单项目查询发给Runtime，取得最多200候选运行及内部keyset位置；候选预算不因公开limit增大而超过200。
2. API批量加载现有 `thread_access` 并使用其当前read判定；不把候选全部Thread ID返回浏览器再隐藏。manager接管读沿现有审计，不能静默省略。
3. 限定一次请求的候选扫描预算，过滤后的页面可以少于limit，甚至空但有next_cursor；不循环扫完全部项目台账来“凑满”一页。
4. 公开cursor封装已扫描位置，next page仍重新授权。使用已安装cryptography的Fernet，沿现有加密用法，通过标准HKDF和固定用途 `usage-dashboard-cursor/v1` 从服务secret派生独立key；建议有效期15分钟、长度≤2048。仅Base64加签会泄漏隐藏RunID，不可直接回传内部cursor；无需新增Redis会话存储。隐藏项数量/会话名不在响应中透露，不提供泄漏隐藏记录的总数。
5. 不可查看/已删除Thread的行不返回；汇总数字范围仍依G0规则，不通过删会话导致历史成本归零。

Run 删除过滤批量查询现有 `run.deleted/runtime.run.item.deleted` 成功审计；Thread 删除通过缺少 `ThreadAccessRecord` 排除。现有公开 router 不提供单 Run DELETE，真实 Thread 删除已验证，单 Run 删除审计使用锁定契约测试。普通 HTTP 审计为 fail-soft、非原子，直接引擎删除或审计丢失无法从现有台账证明 Run 已删；该限制不以新增引擎扫描/台账复制掩盖，详情仍处理 404。若后续新增公开单 Run 删除，须同时落可靠删除标记并补真实链路，不承诺所有来源删除都已过滤。

页面说明明细只显示当前可查看的运行，不能承诺明细行加和一定等于项目治理汇总。详情打开和分页的ACL都要重查；复用 `_load_thread()` / `thread_access` 的实际规则，包括现有manager接管例外，不能发明第二套角色判断。

运行列表按最近匹配调用时间分页；首请求截止时刻不阻止已有调用迟到入库或补齐金额。前端以 `(project_id,run_id)` 去重，刷新重新开始分页；不把多页结果描述成不可变财务快照。

### 内部聚合HMAC契约

既有 `usage-read` JWT严格要求Thread/assistant、受当前模型策略约束，适用于单会话查询。平台跨项目报表不应伪造Thread/assistant、放松operation白名单或签一个租户通配JWT。

本期采用已有内部HMAC请求模式（参考Thread授权和completion签名），为02两个URI增加用途限定验证。沿现有平台/Runtime共享委托secret配置，要求双方一致且长度合规；不复用已有签名正文格式，不新增可访问所有Runtime资源的服务JWT。

```text
headers:
  x-usage-query-timestamp: Unix seconds
  x-usage-query-signature: sha256=<hex>

canonical bytes:
  usage-query/v1 + LF + timestamp + LF + POST + LF + exact_path + LF
  + exact request-body bytes

body:
  version=1, actor_id, credential_id可选, tenant_id,
  project_ids（服务端授权后排序的非空集合）, request_id,
  from/to/timezone/granularity/group_by/filters/pagination
```

签发使用服务端最终bytes发送，Runtime按收到bytes验签后strict解析，固定UTF-8和body≤64KiB。重复签名头、超30秒窗口、错method/path、被改tenant/project/filter、未知字段或错version均拒绝。只读短期重放不增加数据或执行，但同一签名不能兑换模型、Thread、MCP、文件或其他入口。

该签名代表Platform API已经执行当前用户授权；Runtime不信任浏览器权限列表。它仍校验tenant/project集合与时间上限，并在每个SQL中带scope。公开路径不接受以上内部headers；secret/body原文/JWT不得进入日志。Runtime部署必须隐藏内部URI于浏览器入口，但网络隔离不能替代HMAC校验。

这是一条新的服务间契约，须G0人工批准并保留双端fixture及正反例。既有Delegation JWT五字段scope/operation集合、模型策略、Context v6和SSE均保持现状；不更新未批准的 `docs/standards/`。功能获批验收后按实际接口同步服务活规范，本方案本身不代表标准active。

### 错误、降级与审计

- 授权拒绝始终走既有401/403/404安全Envelope，不能包装200 unavailable。
- DB采集/查询不可用由安全availability返回；上游网络失败、超时或坏DTO分别沿现有502/504和安全码，保留request_id。
- 看板完整流程共享2个admission槽，包含授权、上游、撤权复核、目录和DTO；排队计入5秒总预算，耗尽返回503 `usage_query_capacity_exhausted`。前端保留筛选、提供手动重试，不能将503当无权限或记录0；fixture见 `fixtures/error-query-capacity.json`。该预算按单API进程计算，多进程/多副本需在生产联合验证。
- 新参数/范围/游标异常使用明确的 `invalid_usage_analytics_query`；数字溢出使用 `usage_aggregate_range_exceeded`。实施时登记精确HTTP状态和安全提示，不透传SQL或provider异常。
- DTO校验同时核对tenant内部归属、project集合、窗口、time_basis和group_by与请求一致；只schema合法不代表scope匹配。
- 所有公共响应 `Cache-Control: no-store`；首期无跨用户shared cache。未来缓存key必须含身份/凭据、权限版本、scope、完整筛选与DTO版本，撤权复核不能因cache hit跳过。
- 复用HTTP审计：新增 `platform.usage.read`、`project.usage.read`、`usage.runs.read`动作，记录授权范围计数、窗口、分组、result、request_id；不存整份报表、签名或查询原始body。manager接管的既有Thread审计继续存在。
- 使用已有request_id/trace传播；不新造Token看板trace体系，不发Slack/邮件告警。

### 代码落点与影响面

| 路径（相对仓库根） | 本期变化 |
|---|---|
| `apps/platform-api/src/platform_api/modules/usage_analytics/router.py`、`contracts.py`、`service.py`（拟新增） | 独立读模块，三公开GET、当前scope/DTO/name/ACL；无ORM台账复制 |
| `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` | 同复用HTTP client增加两明确内部POST及最终bytes签名，超时/错误沿既有模式 |
| `apps/platform-api/src/platform_api/modules/iam/application/policies.py` | 两新权限码与固定角色映射；同步identity/access返回值和IAM测试 |
| `apps/platform-api/src/platform_api/modules/runtime_gateway/application/thread_access.py` | 使用现有权限函数；批量读取若确有需要只补小仓储函数，不改变Thread policy |
| `apps/platform-api/src/platform_api/modules/audit/http_resolution.py` | 新路由的动作/target/metadata白名单 |
| `apps/platform-api/src/platform_api/entrypoints/http/router.py` | 在现有api_router注册独立router；沿现有依赖/请求上下文 |
| `apps/platform-api/tests/test_usage_analytics.py`（拟新增） | 权限、DTO/scope、候选ACL、数字/时间、签名、网络故障和Session边界 |
| `apps/platform-api/docs/standards/permission-standard.md`、`audit-standard.md` | 实施获批后同步具体权限/动作，不在规划阶段提前改生效行为 |

新模块有独立平台分析职责，采用现有直接文件布局；不为它造DI容器、CRUD基类、repository Protocol或无调用者的export接口。内部HMAC格式与JWT不混用，跨服务测试按operation名称集合断言，避免依赖枚举数量。

## 任务拆分

| Task | 改动与结果 | 最小验收 | 预计/状态 |
|---|---|---|---|
| A01 IAM与scope | 两具体权限、当前身份/项目及返回前复核 | 角色、服务账号/撤权、越界ID、无项目 | [x] done |
| A02 内部adapter | 用途HMAC、两POST、网络总deadline5秒 | 固定向量、正反HTTP、真实慢网络504/断网502 | [x] done |
| A03 Dashboard API | DTO、参数/name/facets、数字/时间可加性校验、整链路admission | 全状态、坏scope/DTO拒绝、no-store与公开容量 | [x] done，B01已解除 |
| A04 Runs ACL | 单候选页批量ACL、Fernet/HKDF cursor | 私有/共享/撤权/删除Thread、接管审计、空页cursor | [x] done，Run删除依上方限制 |
| A05 审计与回归 | 路由/动作、短Session、安全错误及活文档 | 最新定向96项、真实HTTP六场景、审计canary扫描 | [x] done，全仓既有失败另列05 |

### Task A01：独立数字权限与当前范围

- **改动内容：** 两 IAM 权限、tenant slug→平台 UUID 精确项目范围、HTTP前后身份/grant重查。
- **代码位置：** `apps/platform-api/src/platform_api/modules/iam/application/policies.py`；`modules/usage_analytics/service.py` → `_authorize/dashboard/runs`（后者路径前缀同上）。
- **预期结果：** 报表数字与内容授权分离、撤权不返回迟到数据、超200项目拒绝。
- **验证项：** 全角色/跨tenant/服务凭据/范围变化契约、真实editor/operator/executor/viewer/share及撤权 → 通过。
- **状态：** `[x] done` 2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task A02：内部签名与网络截止

- **改动内容：** 最终UTF-8 bytes签名、精确两URI、独立5秒HTTP总deadline、安全错误映射。
- **代码位置：** `apps/platform-api/src/platform_api/adapters/langgraph/runtime_gateway_upstream.py` → `usage_analytics`；`sdk_client.py` → 安全码白名单。
- **预期结果：** 普通JWT不兑换聚合，新签名不扩Runtime资源权限；上游慢连接有界退出。
- **验证项：** 冻结向量双端、实际Runtime正反验签；OS分配端口的真实慢HTTP504/断连502 → 通过。
- **状态：** `[x] done` 2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task A03：公开报表与安全DTO

- **改动内容：** 两级 Dashboard、参数白名单、当前安全名称、字段/范围/时间/可加性检查；300KiB拒绝。
- **代码位置：** `apps/platform-api/src/platform_api/modules/usage_analytics/contracts.py` → `UsageDashboardV1/parse_query`；`service.py` → `_dashboard_projection`；`router.py`。
- **预期结果：** 正确完整/部分/缺价/关闭/故障，坏上游返回502，null/金额及超限不截总量。
- **验证项：** Pydantic fixtures、真实模型ledger→Run→报表→series/groups、admission超时/恢复；百万完整30天公开两轮30/30可用、读p95 1220.89/1171.99ms、写增幅16.01%/11.62% → 通过，B01解除。
- **状态：** `[x] done`（API功能范围）2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task A04：明细授权与不透明分页

- **改动内容：** 批量当前Thread/read/ready ACL、manager接管审计、删除审计过滤、15分钟身份筛选绑定加密cursor。
- **代码位置：** `apps/platform-api/src/platform_api/modules/usage_analytics/service.py` → `_visible_runs/runs`；`cursor.py` → `binding/encode_cursor/decode_cursor`。
- **预期结果：** 隐藏 Run ID 不泄露、短/空页仍能继续、聚合不偷开私有内容。
- **验证项：** 私有/共享/缺记录/manager/删除审计/变身份/过期与空页用例，真实Thread删除消费保留 → 通过。全来源Run删除无法证明，限制如上。
- **状态：** `[x] done` 2026-10-11（已注册平台链路与锁定删除审计契约）。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task A05：审计、迁移与原能力回归

- **改动内容：** 三动作、有界metadata、成功/失败no-store；补旧双head merge、SQLite UUID前向矫正及model匹配。
- **代码位置：** `apps/platform-api/src/platform_api/modules/audit/http_resolution.py`；`entrypoints/http/middleware/request_context.py`；`migrations/versions/20261011_0008_merge_heads.py`（迁移在app根）。
- **预期结果：** 短事务查Platform，等待Runtime时无持有Session；保留历史通知/回执，不新增Platform Token表。
- **验证项：** 最新API定向96 passed/1 skipped/18 subtests；SQLite UUID行保留和不可信数值拒绝；跳过的真实PG分支另验1 passed；71条用量审计无canary/凭据 → 通过。更早不同定向集115 passed证据不与新集合相加。
- **状态：** `[x] done` 2026-10-11；全量测试既有失败清单见05，不声称全仓绿色。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## 验证要求与记录

### 验证要求

- [x] 平台聚合权限不会授予其他tenant、聊天正文、模型连接、价格编辑或Thread接管的新权限。
- [x] 项目editor/admin范围和executor/viewer拒绝、服务账号grant/凭据失效都有明确结果。
- [x] HMAC双方固定body/路径等向量完全一致；普通JWT与裸请求拒绝新内部接口，signed read不能访问其他Runtime资源。
- [x] 当前ACL过滤发生在公共响应之前；返回前撤权拒绝；缺少Thread记录不向外泄漏RunID。
- [x] 金额字符串与数字safe integer/Pydantic校验、time_basis/选中scope一致性、未知字段剥离或拒绝有用例。
- [x] 200 partial、真实HTTP拒绝、502坏DTO、504超时区分，HTTP等待期间Platform数据库事务关闭。
- [x] 新接口响应/71条用量审计无canary/凭据；无private标题。全量既有日志可能有原生执行内容，不宣称日志全部已脱敏。

### 规划记录

2026-10-11规划阶段：已核对IAM、现有usage DTO/方法、Thread授权与HMAC模式；当时签名/API/角色未批准/实施。随后全部G0获批并实施，不能将该历史阶段描述当作当前状态。

### Phase 实施记录

A01–A05均完成，Task完成卡见本篇；原模型/权限证据保留。2026-10-12最终96 passed/1 skipped/18 subtests；公开容量两轮全部门槛通过、B01解除。Runtime API/Worker/Platform API重启后真实DeepSeek471 Token/USD0.000720000000核账、fork不复制、HMAC/native隔离和六类安全场景再次通过。完整命令及证据见[05](05-delivery-and-verification.md)，未正式发布。

## 状态

`done`（A01–A05及非前端公开容量范围）；B01已解除，整项目`partial`，前端与全栈Final由同事接续。服务活规范和前端交接已同步，未生产部署。
