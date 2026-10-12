# Runtime 数据查询与聚合

## 目标

利用 Runtime 已持久化的模型调用事实，提供跨 Thread 的有界聚合及运行候选明细。保持原始台账、采集失败软降级、Run额度保护和既有两GET行为，减少新增存储与执行链改动。

## 方案设计

### 决策记录：职责与数据访问路线

- **决策日期：** 2026-10-11。
- **状态：** 已由用户确认，适用于本项目V1。
- **确认依据：** 用户在澄清Runtime继续负责调用事实及额度恢复后，明确表示“我同意你这个方案,把刚才的决策写入到文档中”。
- **确认范围：** 首轮确认职责与接口查询路线；同日用户明确“方案评审通过，可以开始实施”，批准05全部 G0 和非前端范围。原确认并非自动批准所有事项，追加批准记录见05。

| 模块 | 职责 |
|---|---|
| Runtime执行与采集 | 提取供应商usage、Token归一化、可信调用归属、去重持久化、单Run额度检查与恢复；既有采集、历史成本快照和执行语义继续复用 |
| Runtime用量查询 | 在受保护的tenant/project及时间范围内查询自有台账，完成有界汇总、分桶、分组和候选运行分页，返回安全事实投影 |
| Platform API用量分析 | 定义看板产品指标及公开契约，检查用户权限与查询范围，解析目录名称，执行运行明细ACL、审计和安全DTO校验 |
| Platform Web | 筛选、卡片、趋势、排行、质量提示和按当前权限钻取运行；只访问Platform API |
| GraphHarbor | 持有原生Thread/Run/Checkpoint/Interrupt执行事实；看板不直接读取或修改其内部表 |

Runtime新增查询属于自有用量数据访问能力；平台产品和治理规则由Platform API承担。月度预算、告警、导出、经营分析，以及未来折扣、汇率和结算不随聚合查询下沉Runtime；本期复用现有受信价格快照与估算逻辑，不重建采集或迁移额度恢复。

**选择依据：** 已有单Run/Thread用量查询可延续；台账结构、去重、迟到补齐与质量语义集中在Runtime维护。受控接口让平台依赖稳定查询契约，无需新增Runtime数据库凭据、第二套数据库连接或读取视图的发布协调。源码依据为 `apps/runtime-service/src/runtime_service/observability/usage.py` 的 `RuntimeUsageCallback._load_budget()` 与 `apps/runtime-service/src/runtime_service/db/repositories/usage.py` 的 `read_budget()`；现有额度恢复直接依赖持久化调用事实。

**备选路线的定位：** 数据库只读视图可以成为正式数据契约，平台直查并非天然错误；它与使用通用Runtime账号读取私有底表是不同方案。V1选择受控接口基于当前边界与已有能力，不把这一选择推广为所有系统都禁止数据库读接口。未来已有统一分析数据库、明确共享读取契约或实测证明当前查询无法满足负载时，可以重新评审只读视图/派生读模型，不能未经评审静默改为直查。

**接受的代价与保护：** 增加一次内部HTTP调用及Runtime查询模块；HTTP隔离访问方式，不隔离同库CPU/I/O/连接资源。时间/项目/页数/分组枚举上限、SQL与总请求超时、读并发预算及05的采集写入影响测试必须落实。是否需要独立查询连接池或进一步隔离，由实测决定；不能让报表重压拖垮Agent执行。

### 路线选择

| 路线 | 代价与问题 | 本项目建议 |
|---|---|---|
| Web列出Thread再逐条请求usage | 请求数量随历史增长；分页导致总量漏算；难以一致分桶 | 不采用 |
| Platform API使用通用Runtime账号直接读私有底表 | 扩大数据库权限，依赖内部表结构及迁移，绕过明确的数据读取契约 | 不采用 |
| Platform API查询正式用量只读视图 | 可将SQL聚合放平台，但需专用受限账号、版本化视图、第二套连接及跨服务迁移协调；同库负载仍存在 | 合理备选，当前V1不采用 |
| Runtime SQL聚合，API授权后调用 | 复用现有台账及查询边界，平台依赖稳定接口；增加内部调用与Runtime查询职责 | **V1已由用户确认** |
| Platform复制ledger/每日读模型 | 多出同步、游标、迟到修正和删除策略，未经测量难以证明必要 | 超过05负载门槛后单独评审 |
| 分析数据库/独立统计服务 | 新运维与同步链路，当前没有容量证据 | 不引入 |

### 表与字段复用

| 表 | 本期用途 | 本期变化 |
|---|---|---|
| `runtime_usage_calls` | 每次调用的Token、已知成本、model_id、purpose/scope、started_at、quality/outcome | 时间索引和同事务脏标记trigger；不改变唯一调用事实和pricing_snapshot |
| `runtime_usage_runs` | native归属、graph_id、采集manifest、degraded与额度停止原因 | 时间索引、内部usage_slot与has_calls；不新增执行终态镜像 |
| Runtime投影状态/脏版本/维度桶 | 可重建查询加速，按generation切换 | B01实测后获批新增；不成为调用事实或额度恢复来源 |
| Platform项目/Agent/模型目录 | 由API侧解析显示名 | Runtime不查询平台库 |
| GraphHarbor Run/Checkpoint | 已有RunUsage单条详情继续读取原生状态 | 看板聚合不扫描checkpoint、不改引擎表或引擎包 |

原方案先验证台账直读；B01实测后获批新增Runtime内部派生表和manifest查询字段，最终实现见下方约束。用户排行、来源、无Run辅助操作需要01的后续事实，不能凭Thread owner/当前模型/最新Thread状态推导。

### 时间数据集与聚合

令 `C` 为严格满足签名tenant、授权project集合、调用时间 `[from,to)` 和模型/graph/purpose/scope过滤的调用集。所有汇总、趋势与维度分解基于同一个 `C`；SQL先限定scope再聚合，不能先读全租户结果再在Python筛选。

1. **summary：** 对 `C` 计算各Token字段SUM及非null字段COUNT、observed/reported/missing/invalid/incomplete/priced次数、已知成本和distinct native Run数。仅对匹配Run的manifest计算degraded/open数量，零调用manifest单独计数，不编造model归属。
2. **timeseries：** 按 `c.started_at` 在所选 `UTC/Asia/Shanghai` 时区分桶，再返回带UTC offset的真实桶边界。`hour`窗口最多7天，`day`最多90天，至多200桶；分桶前后沿半开区间一致过滤。
3. **breakdown：** group_by只允许project/model/agent/purpose/scope。agent键为 `(project_id,graph_id)`，不同项目同Graph不混为同一Agent。model_id为空进入未映射组。
4. **previous_window：** 同一SQL读快照下查询紧邻前窗；窗口等长，筛选不变。只对可比较的完整数据生成变化率；首期不做去年同期或自定义对照窗。
5. **runs候选页：** 按选中调用汇总native Run的“窗口内消耗”，使用 `(last_matching_call_at,run_id)` 降序keyset，表示最近匹配调用时间。候选Run分页量最多200、公开默认50；API负责当前Thread ACL过滤。分页冻结首请求的查询截止时刻，晚到记录/用量补齐可在刷新后改变结果；不承诺跨请求永久快照，不保持数据库长事务。

零调用manifest单独限定tenant/project/graph及 `collection_started_at` 时间窗，查询该Run在台账中确实没有调用；不计入按call时间计算的recorded_run_count。应用model/purpose/scope筛选时无法归属零调用Run，`zero_call_manifest_count` 返回null。这个辅助计数的manifest时间口径在DTO/提示中明确标示，不能混入调用趋势。

Top N默认10、最多50，排序字段只有known_total_tokens/known_cost_usd/observed_call_count。缺失按“已知小计排行”展示，不把unknown费用当真实0参与免费排名。“其他”用其所属调用重新计算SUM/COUNT DISTINCT；不能将各组运行数相加冒充总运行数。运行数、缓存比、覆盖率均不是可加指标；Token与金额在互斥维度分组内可以核对总和。

空桶处理：在数据库查询成功的已观测数据集内，返回该桶已记录调用数0及已记录小计0。没有历史采集依据且当前采集开启时返回unavailable/not_recorded；没有历史且采集关闭时返回disabled。旧台账可读时availability继续按记录完整度返回available/partial，采集关闭仅通过 `collection.enabled_now=false` 提示。不能把补齐图形的0点当作“这段时间没有任何供应商消费”的证据；graph未接线/停采集期间没有完整覆盖承诺。

### 完整度与刷新

复用现有 `project_summary()` 的字段计数、`known_tokens`、Decimal成本与availability思路，将可共享的小计算函数放在现有query模块；不能给单Thread接口偷偷换时间口径。新增查询仅使用v1调用事实和自身输出DTO。

- 模型结果补齐前：started调用的token为空，已知小计保留，对应桶为partial。
- 缺usage/非法数字/采集degraded：完整字段为null；已知字段和缺失数量继续返回。
- Token完整但缺费率：Token仍可available，cost独立partial/unknown。
- 迟到回调补齐历史桶；只按已有唯一调用键更新，不用 `tokens +=` 形成重复消费。
- manifest结束不等于GraphHarbor success，API状态和Run详情继续沿原生读取。
- 一个报表内部summary/series/breakdown/previous使用同一个只读REPEATABLE READ事务，返回snapshot时间 `as_of`。运行列表独立请求带自己的 `as_of`，不伪称和旧报表同一个数据库快照。
- 不加公开响应缓存或HTTP长事务；B01获批的Runtime后台投影每0.5秒调度，当前快照检查dirty并有界补查，积压超限明确不可用。不能跨身份/项目复用公开结果。

### 索引与查询边界

当前 `ix_runtime_usage_calls_page` 先以run_id索引，`ix_runtime_usage_calls_thread` 先以thread_id索引，不适合没有Thread条件的时间看板。建议前向迁移增加：

```sql
CREATE INDEX ix_runtime_usage_calls_project_time
ON runtime_usage_calls
    (tenant_id, project_id, started_at, run_id, model_call_id);
```

先用真实数据做 `EXPLAIN (ANALYZE, BUFFERS)`；不得为每个筛选组合建索引。若manifest时间/零调用查询确实退化，再增加 `(tenant_id,project_id,collection_started_at,run_id)` 索引。成本、Token和JSON快照不放进宽覆盖索引，避免采集写放大。

索引迁移使用合法Alembic revision，不复用已发布编号。本地空/既有库升级和重复upgrade已验，最终应用head为0005。生产大表构建锁时长需先测；需要 `CREATE INDEX CONCURRENTLY` 时另用Alembic autocommit并验证invalid索引恢复，不在普通事务中直接执行。生产迁移与发布仍需另行授权。

边界建议：

- 显式project_id集合最多200、拒绝空集合/重复或通配符；超出则要求先缩小范围，不能截断成“全平台总量”。tenant始终单一。
- 每次查询最多90天，每页最多200、每次最多200时间桶；项目/模型/Agent选项也有上限和truncated标识，不用选项截断影响统计总量。
- 首期服务端固定查询保护，建议单statement≤1秒、整次报表≤5秒，连接/lock timeout继续有界；05负载测试校准。不全局放宽既有usage查询750ms设置。
- SQL参数化；group_by/sort/granularity只能由枚举映射固定SQL表达式，拒绝任意JSON path、列名或函数。
- PG SUM使用自身宽精度；public Token/Count继续遵守现有 `0..2**53-1` 契约。溢出返回明确 `usage_aggregate_range_exceeded`，要求缩小范围，不截断、转float或伪装0。金额溢出单独标cost unknown并保留Token。
- 只读事务在同一个线程创建/使用/关闭；最终 executor 1线程、专属读池/SQL槽各1、最多16个在途请求，提交起4.5秒deadline、异步最多4.8秒。Platform看板整个流程共享2个admission槽，排队计入5秒总预算；超时返回503。采集原独立连接保留，取消由有界SQL退出后回收配额。

### 内部接口与落点

两个新只读POST仅用于结构化查询，不产生模型调用/业务写入：

- `POST /internal/usage/aggregate`：返回summary、previous、series、一个group_by的排行。
- `POST /internal/usage/runs/query`：返回限定scope的运行候选页，不返回会话标题/正文/native终态。

认证/签名详见03；旧 `usage-read` JWT、其他operation或裸网络请求均不能访问新入口。API根据当前权限生成project集合，Runtime验证signature/body并再次强制SQL作用域，绝不接收浏览器直连。

| 路径（相对仓库根） | 修改职责 |
|---|---|
| `apps/runtime-service/src/runtime_service/db/repositories/usage_analytics.py` | 新增 `aggregate_usage()`、`list_usage_runs()`；原 `usage.py` 采集和两旧查询保持口径 |
| `apps/runtime-service/src/runtime_service/observability/usage_query.py` | 复用已有数字投影helper，避免复制归一化/计价逻辑 |
| `apps/runtime-service/src/runtime_service/observability/usage_analytics.py`（拟新增） | 有界query解析、summary/series/group投影与安全聚合DTO；不存provider正文 |
| `apps/runtime-service/src/runtime_service/http/usage_analytics.py`（拟新增） | 两只读查询入口及用途受限HMAC校验 |
| `apps/runtime-service/src/runtime_service/webapp.py` | 注册router，遵守现有自定义路由认证边界 |
| `apps/runtime-service/src/runtime_service/auth/platform.py` | SDK 最外层仅向两个精确 POST 分发 HMAC 请求，真正验签由 router 完成；无 native scope/permissions |
| `apps/runtime-service/src/runtime_service/runtime/auth.py` | 修复已有 `credential_id` 契约在 VerifiedDelegation 中丢失导致的普通认证500；不新增 JWT operation |
| `apps/runtime-service/src/runtime_service/db/migrations/versions/` | 下一条index-only前向迁移；不修改历史revision |
| `apps/runtime-service/tests/observability/test_usage_analytics.py`（拟新增） | 时间/数字/缺失/分组投影，复用既有usage fixture |
| `apps/runtime-service/tests/http/test_usage_analytics.py`（拟新增） | 签名、body上限和各operation互拒 |
| `apps/runtime-service/tests/durable/test_usage_analytics.py`（拟新增） | 真实PG查询、并发补齐、索引/迁移/故障和规模测量 |

采集callback、模型装配、各Agent组合根不是V1默认改造项。G0盘点若发现某个声称支持的图未接线，按最小公共helper接线并列成明确追加任务，不顺手重构整个Harness。

## 任务拆分

| Task | 改动与结果 | 最小验收 | 预计/状态 |
|---|---|---|---|
| R01 查询契约与投影 | analytics 文件、时间/枚举/部分数据/数字边界冻结 | 小计、空桶、前窗、已知比例与旧 v1 回归 | [x] done |
| R02 SQL及时间索引/投影 | repository、0004索引+0005可重建派生桶 | 正确性/迁移与公开百万容量原SLO通过 | [x] done，B01已解除 |
| R03 内部入口与认证 | 两 POST、用途 HMAC、SDK ingress/router 注册 | 实际部署验签和双端向量/互拒通过 | [x] done |
| R04 耐久/故障与回归 | 补齐、锁/断库/重启/重建、旧Usage/预算验证 | 恢复/回退、两轮公开写入增幅≤20%通过 | [x] done，控制链证据见05 |

### Task R01：有界查询与安全投影

- **改动内容：** 冻结 strict 查询、窗口、指标及降级 DTO，复用原 `_integer/_cost`。
- **代码位置：** `apps/runtime-service/src/runtime_service/observability/usage_analytics.py` → `AnalyticsQuery/project_metrics/dashboard/query_aggregate`。
- **预期结果：** 完整/小计/真实零/未知分别返回，缓存推理不重复，费用 Decimal 字符串。
- **验证项：** analytics单元、旧usage/usage_query与双端schema通过；最新相关Runtime回归171项通过，新增取消后SQL异常回收先失败后通过，旧更广集合174项与向量3项证据另保留。
- **状态：** `[x] done` 2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 本专题状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task R02：SQL、快照、索引与投影

- **改动内容：** 在原有同一 READ ONLY REPEATABLE READ 聚合/前窗/Top+other/候选 keyset 上，增加 Runtime 可重建投影、Run 位集合、脏版本补齐和两槽平台 admission；前向迁移链保留原事实、价格与额度。
- **代码位置：** `apps/runtime-service/src/runtime_service/db/repositories/usage_analytics.py`、`usage_projection.py`、`usage_connections.py`；迁移 `0004_usage_analytics.py`、`0005_usage_projection.py`。
- **预期结果：** 作用域、可加总量和 distinct Run 正确，并满足 05 容量/采集影响门槛。
- **验证项：** 真实 PG/既有含价格台账升级、重复 upgrade、全字段保留、投影/边界/重建和公开容量两轮均通过；读 p95 1220.89/1171.99ms，写入 p95 增幅 16.01%/11.62%，200 项目/90 天可用。
- **状态：** `[x] done` 2026-10-12；B01 已解除，详细证据见 05。
- **合规检查：** [x] 实现；[x] 执行验证并保留失败；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task R03：用途隔离的内部读入口

- **改动内容：** raw bytes HMAC、body64KiB/30秒窗口、重复键/头拒绝；精确 ingress 无 native scope。
- **代码位置：** `apps/runtime-service/src/runtime_service/http/usage_analytics.py` → `_verified_body/_query`；`apps/runtime-service/src/runtime_service/auth/platform.py` → `authenticate_ingress`；`webapp.py`。
- **预期结果：** 平台可签名查数字，旧 JWT 和其他资源互拒，不产生模型调用。
- **验证项：** 双端冻结向量、PrincipalMiddleware部署边界、真实HTTP错签/path/native互拒；查询前后call数量不变 → 通过。
- **状态：** `[x] done` 2026-10-11。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

### Task R04：耐久、故障与回归

- **改动内容：** 补齐双 upsert、SIGKILL started 留痕、PG故障/锁/重启、取消工作配额及旧预算恢复回归。
- **代码位置：** `apps/runtime-service/tests/durable/test_usage_analytics.py`、`test_usage_ledger.py`、`test_token_budget_ledger.py`；`apps/runtime-service/tests/observability/test_usage_analytics.py`。
- **预期结果：** 故障不伪造数据、不重复调用，恢复后原事实、价格与额度保留，采集 p95 增幅≤20%。
- **验证项：** 最终 Runtime 171 项、Platform API 96 项/18 subtests、独立原生 PG durable 13 项通过；覆盖投影崩溃、晚提交、重建、PG 停止/重启、旧应用保留 `0005` head 和真实模型重启核账。公开容量两轮全部可用，写 p95 增幅 16.01%/11.62%。
- **状态：** `[x] done` 2026-10-12；B01 已解除，未包含前端浏览器验收。
- **合规检查：** [x] 实现；[x] 验证；[x] 状态；[x] CONTEXT；[x] FEATURES；[x] CHANGELOG。

## 验证要求与记录

### 验证要求

- [x] index-only迁移空库/既有台账、重复upgrade、既有调用数量和历史价格不变。
- [x] 同时覆盖前窗和本窗、同Run跨午夜/跨窗口、结束后补齐原桶；总量不使用run开始时间过滤。
- [x] `(project,graph)`维度与不同catalog UUID正确；未知模型/删除名称不丢调用。
- [x] Top N加“其他”Token/金额等于summary；同Run多模型的distinct运行数不被相加。
- [x] 同快照SQL、重复双upsert、新调用和迟到coverage；独立原生PG重启后可读。
- [x] 无价格、null/cache/invalid、真0、无记录、关闭新采集但旧数据仍查、查询故障均有明确状态。
- [x] DB故障/查询不触发模型重试/构图/额外LLM；采集fail-soft，投影维护和公开读压下两轮写入增幅≤20%。
- [x] 十万/百万调用负载与采集写入同时运行；05 的 SLO、投影规模、公开接口报告和失败复诊均留证。

### 规划记录

2026-10-11规划阶段：已核对两表schema、现有repository及投影；当时尚未执行SQL/迁移/负载测试，新符号及路由为拟议契约。

2026-10-11决策落笔阶段：用户确认本节职责与数据访问路线；当时仅记录采用理由、只读视图备选和同库负载风险。随后全部G0获批，实施证据见下方。

### Phase 实施记录

R01–R04 已完成。2026-10-12 最终 Runtime 171 项、Platform API 96 项/18 subtests、独立原生 PG durable 13 项通过；公开百万容量两轮 30/30 可用，读 p95 1220.89/1171.99ms，写入增幅 16.01%/11.62%，B01 解除。失败复诊、投影实现、回退和边界仍见 [05](05-delivery-and-verification.md)。

## 状态

### B01 优化实现约束（2026-10-11，用户已批准）

原始SQL只读Spike确认：百万行可加数字单SUM约0.66秒，但日分桶2.30秒、Run集合6.05秒、零调用4.43秒；10并发和采集门槛不能仅靠增加timeout解除。采用Runtime内可重建读模型：

- 原manifest增加按tenant/project唯一的内部紧凑Run编号与调用存在标记；原台账/价格/预算字段保留，旧应用仍可读取。存在标记在事实事务维护，零调用统计不再逐Run探测百万表。
- 新增小时、UTC日、上海日和内部8小时维度桶，存精确Run位集合及各字段known count/价格版本。日查询优先完整日，跨UTC边缘优先8小时/小时，非整小时读有界原始调用；相邻窗口独立切段，先在同项目合并位集合，再跨项目合计基数，不能按桶Run数相加。
- 同事务trigger按tenant/project/UTC日标脏，涵盖新增、真正更新、迟到修正及删除；原始upsert去重不受影响。脏版本append-only，后台独占advisory lock、在RR快照重算替换桶，仅清除本快照可见且不高于任务水位的脏版本；序号分配不代表提交先后，晚提交低版本也必须留下再处理。
- 查询仍只读Repeatable Read：读active generation、manifest及脏标记；最多8个脏项目日与5000条边界/脏事实在本快照有界补查，先排除受影响派生桶、合并重叠补查范围。超限明确不可用，不返回假完整。manifest开放/退化状态按本快照的原始状态计算；派生读模型不参与Run额度恢复。
- 重建使用新generation、同事务双代标脏，处理完新代脏队列再原子切换，旧派生代保留；应用回退保留新迁移链。投影任务也计入读写联合容量验收。
- 三成功DTO/HMAC/权限/ACL保留，原deadline不扩大；Runtime查询收敛为1线程/1SQL连接、最多16在途，Platform整链路2admission槽；新增503安全错误fixture。不新增依赖或外部消息系统，高基数/稀疏单独核账，压缩率不外推任意数据集。

具体任务和验收仍见05的B01.0–B01.5；实现细节记录在implementation/02-b01-optimization.md。

`done`（Runtime 非前端范围）：R01–R04 和 B01 优化已完成，原容量/采集影响门槛通过。Web W01–W04沿用04同事完成记录，本轮未复验；整项目仍等待最终后端/503联合复验及全栈人工验收。同库投影降低查询工作量但不等价于物理数据库负载隔离。
