# B01 容量优化实施记录

**时间：** 2026-10-11–12；**工作区：** b2b1关联Worktree（以本目录执行 `git rev-parse --show-toplevel` 为准）；基线 `116cc26f`，环境 `wt_43d02afc6100`。进度与验收只看 [05](../05-delivery-and-verification.md) 的 B01.0–B01.5。

## SQL 试验与选择

本工作区所属百万库只读试验保存在 `.local-stack/usage-sql-spike.json`：零调用 LIMIT 1 探测约 4.43 秒；可加数字单次汇总约 0.66 秒，日分桶约 2.30 秒，Run 集合约 6.05 秒。单条 SQL 调整不足以支撑十并发，因此实施用户已批准的 Runtime 可重建读模型。

## 实施变化

- `apps/runtime-service/src/runtime_service/db/migrations/versions/0005_usage_projection.py`：manifest 增加项目内紧凑 `usage_slot` 及 `has_calls`，减少零调用 Run 对百万事实表的存在性探测；新增分代桶、append-only 脏版本和状态表。事实 INSERT/UPDATE/DELETE 在原事务可靠标脏；原始调用、预算和价格快照保留。
- `apps/runtime-service/src/runtime_service/db/repositories/usage_projection.py::_replace_day/project_pending/begin_rebuild`：小时、UTC 日、上海日及内部8小时桶完整替换，8小时桶减少上海时区跨 UTC 日边界的读取工作量。advisory lock 限制一个维护者；每批最多8个任务、2秒调度预算、单 SQL 2.5秒、锁250ms。清除本快照可见且不高于任务水位的脏版本，晚提交的低版本仍保留，不会被错误清除。失败回滚、5秒后重试；新 generation 按项目续扫，事实事务同时标记两代，追平后原子切换，旧代保留。
- `apps/runtime-service/src/runtime_service/db/repositories/usage_analytics.py::aggregate_usage/_projected_metrics`：只读 Repeatable Read 中用 pipeline 读取代次、manifest 和脏范围；完整桶读取投影，非整小时边界和少量脏范围有界补查事实。最多8个脏项目日、5000条补查事实，超限明确不可用。使用 `bit varying` Run 位集合，按项目和维度合并后求基数；不能将桶/模型的 Run 数相加。数字、known count、比例分子分母、Decimal 金额与价格版本保持原口径。
- `apps/runtime-service/src/runtime_service/db/usage_connections.py::query_pool/close_query_pool`：仅 analytics 使用一个专属查询连接；查询 executor 一个线程、最多16个在途任务，原4.5秒执行预算和单 SQL 1秒限制保留。原采集独立连接路径保留；新连接池复用、DSN切换和 lifespan/atexit 关闭有测试。
- `apps/runtime-service/src/runtime_service/db/repositories/usage.py::_begin`：非 reopen 时先判断 manifest 已存在，避免每次 call upsert 都触发新 Run 槽分配；`ON CONFLICT` 保留并发安全与旧 reopen 语义。
- `apps/runtime-service/src/runtime_service/observability/usage_projection.py`、`webapp.py`：数据库迁移后启动独立单线程维护，每0.5秒调度；关闭采集后仍能维护已有历史，投影不参与额度恢复。
- `apps/platform-api/src/platform_api/modules/usage_analytics/router.py::get_usage_service`、`service.py::dashboard`：所有看板请求共享两个 admission 槽，覆盖授权→Runtime→撤权复核→目录/DTO全流程；排队也计入原5秒总预算。超时返回安全503 `usage_query_capacity_exhausted`，不放宽 HMAC、ACL 或统计范围。新增前端错误 fixture，三成功 DTO 不变。
- `apps/runtime-service/scripts/verify_usage_capacity.py`、`apps/platform-api/scripts/verify_usage_capacity_http.py`：重建真正完整30天的百万调用样本；公开链包含真实 JWT、当前权限、HMAC、DTO、审计和 ACL；两独立 Run 采集在同租户/项目、查询窗外写入 start/end 事实，后台维护同时运行。修复容量样本复用 Thread ID 的问题。
- `apps/platform-api/scripts/verify_usage_security.py`：数据库故障场景锁投影状态表，验证当前查询真正依赖的对象；保持历史消费及私有内容隔离检查。
- 测试覆盖 `tests/durable/test_usage_analytics.py`、`tests/observability/test_usage_connections.py`、`test_usage_projection.py` 和 API `tests/test_usage_analytics.py`：原始聚合对照、两时区/边界、distinct、缺失/价格、并发写入和晚提交水位、投影进程崩溃、失败重试、重建切换、只读连接复用、整链路 admission 和超时恢复。
- 最终检查发现零调用Run统计误复用了跨日dirty扫描的扩大结束时间：`aggregate_usage()` 改用独立 `dirty_start/dirty_end`，manifest严格按原 `[from,to)`。真实PG的结束时间边界用例先复现2个Run/期望1个，修正后通过；失败证据 `usage-b01-window-regression-before.json` 保留。没有改变索引、查询资源预算或容量门槛。

## 当前证据

2026-10-12 Phase：Runtime171项、API96项及18个子测试通过；API1个PG opt-in分支跳过，不计为通过，原专项有独立PG迁移证据。独立原生PG补验13项通过、2项未选（旧外部模型/旧性能矩阵由本专项实际链路替代）；包含保留 `0005` 迁移链的旧 Runtime lifespan 启动、旧额度/停止原因读取。既有含价格和额度的 `0004` 前向升级/重复升级，以及真实 PostgreSQL 停止/重启，调用、费用、额度、投影和 migration head 均保留；见 `.local-stack/usage-b01-durable-and-restart.json`。临时PG已停止，数据保留，不改宿主共享PG服务。最终40个Python文件Ruff check/format、21份Markdown及27个相对链接、四schema/11个响应/五个错误Envelope检查通过。

完整百万容量库 `wt_43d02afc6100_usage_capacity_c5cfb168`：1,000,000调用、50项目、10,000 Run，覆盖完整30天，目标窗口120,000,000 Token。首次投影43,550行、30,834,688字节（约29.41MiB）、构建189.51秒。高基数/稀疏场景另由真实PG测试核账，不能将该压缩率推广到任意维度分布。

| 公开接口验收 | 第一轮 | 同代码复测 | 原门槛 |
|---|---|---|---|
| 30次、10并发全部可用 | 30/30 | 30/30 | 全部可用 |
| 读 p95 / p99 | 1220.89 / 1309.52ms | 1171.99 / 1172.77ms | ≤1500 / ≤3000ms |
| 两条采集写 p95 | 41.15→47.74ms | 41.47→46.29ms | 增幅≤20%，无持久化失败 |
| 写 p95 增幅 | 16.01% | 11.62% | ≤20% |
| 200项目/90天 | 可用，181.03ms | 可用，170.63ms | 可用 |
| Run ACL页 p95 | 525.54ms | 506.85ms | ≤1500ms |

原始报告为 `.local-stack/usage-capacity-phase-platform-budget-two.json` 与 `usage-capacity-b01-final-http-repeat.json`；Runtime原生独立报告 `usage-capacity-b01-final-native.json` 为30/30可用、读p95 430.30ms、写增幅2.10%，不能替代上面的公开接口结论。历次未通过报告保留，包括单admission槽读p95 1753.35ms/写增幅41.77%；没有通过放宽门槛或超时取得本结论。

两轮公开测试均为新启动API/Runtime进程；首次模型分组请求分别316.36/300.24ms，后续热请求约130–145ms。PG/OS缓存未强制清空，不宣称磁盘冷缓存或生产容量保证。两条采集为真实采集 repository 的有界合成 start/end 写入，不等于外部模型端到端时延；真实模型核账、安全及重启后运行链另列05。

注册环境的Runtime API、Worker和Platform API实际重启后，再执行真实DeepSeek471 Token/USD0.000720000000核账、Thread fork/HMAC/native隔离和六类安全场景均通过。证据 `.local-stack/usage-chain-b01-restarted.json`、`usage-security-b01-restarted.json`，服务继续运行供前端联合复验。

最终边界修正后的Runtime API再次重启，公开项目看板200/available、125.85ms，历史471 Token/USD0.000720000000与趋势核对通过；查询前后调用事实均68条，没有新增模型调用，见 `.local-stack/usage-b01-final-public-smoke.json`。

## 本地旧原型修复

本 Worktree 长期 Runtime 库曾安装未发布的早期同名 `0005` 原型，普通 upgrade 因 head 同名不会自动改变原型结构。已仅在所属本地库校正为最终位集合、紧凑 Run 槽、append-only 脏版本、UTC日与8小时桶，并重新建立触发器；66调用、49,617 Token、USD 0.101036100000 前后不变，证据 `usage-prototype-repair.json`。正式部署必须使用合法前向迁移链；本次已用独立干净库和含事实的 `0004` 库验证，手工修复不作为生产迁移方案。

同库读模型降低查询工作量，CPU/I/O仍共享，后台维护纳入联合压测；只有实际同库写入门槛通过后才解除B01。本轮未开发前端，工作区已有同事的 Web 改动不属于本轮交付；三个成功 DTO 保留，无提交、推送或生产部署。
