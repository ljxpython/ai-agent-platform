# Runtime 与 Platform 实施记录

## 日期与范围

2026-10-07。用户已批准方案；实施 02/03 以及 05 的非前端验证，前端代码由同事接续。未部署现役服务。

## 已落地代码

- `apps/platform-api/src/platform_api/modules/runtime_catalog/domain/models.py`：`PricingInput/PricingSnapshot`，固定 USD/百万 Token，六费率十进制字符串，客户端不能伪造版本；原 CRUD 增加可空 pricing。
- `apps/platform-api/src/platform_api/modules/runtime_catalog/application/service.py`：`_price_snapshot()` 服务端 UUID、同价幂等、PATCH 不传保留/null 清空；`resolve_model_connection()` 返回完整快照。
- `apps/platform-api/migrations/versions/20261007_0006_model_pricing.py`：nullable JSON；不回填、不删除价格历史。
- `apps/runtime-service/src/runtime_service/observability/usage.py`：官方 callback 生命周期、优先标准 usage metadata、缓存 TTL 互斥分桶、Decimal 成本、可信 Run 归属及隐藏调用辅助配置。
- `apps/runtime-service/src/runtime_service/db/repositories/usage.py` 与 `db/migrations/versions/0002_usage.py`：作用域唯一键、幂等 upsert、两表、SQL 汇总、repeatable-read 明细分页；连接/statement/lock 超时有界。
- `observability/langfuse.py::with_langfuse_tracing()`：采集与外部观测开关独立；所有现有组合根复用。`runtime/modeling.py::build_model()` 通过模型 metadata 携带安全身份，保留 BaseChatModel/bind_tools。
- `services/dearflow_agent/middleware/memory.py` 与 `tools/images.py`：隐藏调用保留 usage callback；不引入正文导出或后台任务。
- 两端 `usage-read`、两个 GET 和 Platform Pydantic 白名单：原生 Run 状态仍由 GraphHarbor 提供。

关键行为从“扫描当前消息累计 total”变为“模型 start/end 事实按 ID 补齐”。数据库更新不做 `tokens +=`；相同调用重复事件不重复收费，新模型调用保留新 ID。

## 初次 Phase 验证证据

- Runtime 归一化/成本/真实 create_agent callback + 模型构造：23 passed。
- Platform 价格/既有目录与引用：30 passed。
- Platform 用量投影 + 双端 Delegation：17 passed，52 subtests passed。
- Runtime 用量/内部路由：12 passed。
- 隔离 PostgreSQL 两进程并发、唯一键、占位补齐、分页、汇总、lock timeout、开关：1 passed。

## 实测修正

- 使用官方 `langgraph.config.get_config` 读取隐藏调用上下文。
- LangGraph 图配置合并会拼接 callbacks；重复装配时过滤已有实例。
- Pydantic PATCH 的 `exclude_unset` 递归作用于嵌套价格；价格对象必须完整归一化后比较版本。
- PostgreSQL 本地时区会生成 `+08:00` cursor；ledger 连接统一 UTC，避免服务生成的 cursor 被自身拒绝。

## 后续 Phase 与实测修正

- Runtime usage/lifecycle/http 最新 26 passed，vision 身份未知即便携价仍 unknown 的最后回归 1 passed；真实 PG 追加 SIGKILL/连接恢复/索引后 2 passed。
- Platform usage/pricing/inventory 最新 32 passed、305 subtests；audit/migration/model 用量定向 38 passed、6 subtests。各集合重叠，不累加。
- `_details` 拒绝非对象细节，provider normalization 使用实际 model.protocol；complete tokens 受 reported-call coverage 限制，known_tokens 是独立已知字段小计。
- 真实 HITL resume 不允许覆盖 context；入队必须等 native running，因此 controlled provider 用事件同步后提交两条 HumanMessage；fork/checkpoint replay 用真实 native UUID。
- 删除原生 Run 的 API 产品没有 DELETE，因此测试以作用域受控 native run-delete 进行删除，再通过公共 GET 验证404和 Thread 历史保留。
- `scripts/verify_agent_usage.py` 采用真实 API/Runtime/ProductionWorker/PG/Redis，仅 provider 是无外部请求的确定性 HTTP fixture；价格改版、清空/模型删除、开关、权限和故障均实测。
- PG restart 后关闭采集仍可读旧金额；`scripts/verify_agent_usage_rollback.py` 从导出的旧源码启动两服务，保留新迁移库，不跑旧 migration/downgrade；聊天/SSE/HITL与账本保留通过。
- 性能首文本仅接受 live SSE messages，排除旧 checkpoint 文本；SQL_ASCII admin 库返回bytes数据库名，连接采样需解码，不能把0峰值当事实。
- 回退 fixture 增加标准 SSE，避免旧 streaming 模型把 JSON 响应判为无消息；这只修验证脚本。
- Thread删除后平台现有ACL先拒绝403，测试按授权顺序断言，不改生产权限实现。

前端报告与 actual Pydantic schema/安全样本已冻结在 04/fixtures。非前端 Final 的静态/全量门禁已按 05 执行，最终结论只写 05，不以实施记录判断进度。

## Final 回归修正

- `runtime/modeling.py::fetch_model_connection()` 只在安全快照非空时增加 `pricing`，缺字段/显式 null 保留旧结果结构；追加参数化验证。完整价格快照继续随连接传递。
- `tests/services/test_message_inbox_postgres.py::test_limits_sender_isolation_metrics_and_additive_recovery()` 在自己的临时 schema 内移除新 usage 表后再删除版本表，构造真实迁移前旧库。原 fixture 只删版本表却保留新表，造成 DuplicateTable；生产迁移不添加忽略冲突或自动修复逻辑。
- 指定既有 `PLATFORM_API_TEST_PYTHON` 后跨服务澄清契约通过；修复后 usage/modeling/legacy/durable 相关集合 `44 passed`。
- Runtime 三个既有测试失败与 Platform 四个既有错误脱敏失败均以 `bf47991b` 对照复现；没有放宽正式图契约、修改 MCP 或更改旧错误投影来让测试变绿。详见 05 Final。

## 验证脚本与证据资产

- `scripts/verify_agent_usage.py` 创建唯一隔离 Runtime/Platform 数据库，启动受控 HTTP provider、Runtime、Platform API 和 ProductionWorker；覆盖 16 个后端场景，输出 `e2e-evidence.json` 与 `usage-v1.json`。
- `scripts/verify_agent_usage_rollback.py` 使用 `git archive HEAD` 导出的旧应用源码连接已经迁移的数据库；不执行旧 Alembic，验证旧聊天/SSE/HITL 能力与 ledger 保留，输出 `rollback-evidence.json`。
- `restart-evidence.json` 记录 PG `pg_ctl restart` 后的历史读取和关闭采集语义；临时库只用于本轮验证，现役 5432/服务没有触碰。
- 真实隔离证据包含 provider/write/query 数字和连接峰值，但这是小样本基线，不是批准的业务 SLO；受控 provider 不能证明供应商隐藏重试或账单完整性。
