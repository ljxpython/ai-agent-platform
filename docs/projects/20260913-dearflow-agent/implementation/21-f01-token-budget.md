# F01 Run Token 额度保护：Runtime 与 Platform API

## 改动时间与任务

2026-10-09；用户已批准 15 的方案。T00—T06、T07-B 的 Runtime/API 实现、隔离验证和交接冻结已完成，无 F01 非前端 blocker。任务进度以 [15 的任务拆分](../15-token-budget-governance.md) 为准，本文只记录实现与证据；前端及联合 Final 按 [16](../16-token-budget-frontend-handoff.md) 接续。

## 实际改动

- `apps/runtime-service/src/runtime_service/runtime/token_budget.py`：部署策略冻结、按唯一 call 增量维护的共享额度投影。`runtime/errors.py` 是两种预算异常的唯一定义。
- `apps/runtime-service/src/runtime_service/db/migrations/versions/0003_token_budget.py`：接 `0002_run_control`，只增加 Run 策略和停止原因；保留式回退不删列/调用事实。
- `apps/runtime-service/src/runtime_service/db/repositories/usage.py`：首次策略写入、原调用幂等 upsert、全 scope 恢复和可空历史摘要；不新增账本表。
- `apps/runtime-service/src/runtime_service/observability/usage.py`：唯一 Usage callback 维护投影；附加 `_TokenBudgetDispatchGuard` 只负责物理请求前检查。关闭预算仍为 fail-soft，严格预算下持久化不足拒绝后续新增工作。
- `apps/runtime-service/src/runtime_service/middlewares/token_budget.py` 与四个正式 `services/*/agent.py`：新增模型/工具前检查，复用 system 收尾指令、既有 custom writer。主子图共享根 callback，子图没有独立额度。
- `apps/runtime-service/src/runtime_service/runtime/modeling.py`：仅在预算启用时关闭 SDK 隐式重试；既有显式 retry/fallback 继续按唯一物理调用事实记账。Workflow 内层保留可信 `metadata.run_id`。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/middleware/memory.py`：完成后的可选候选提取耗尽时跳过；不购买额外总结，不把已完成回答变为失败。
- `apps/runtime-service/src/runtime_service/observability/usage_query.py`：仅 Run Usage 增可选 `token_budget`，不扩 Thread DTO 或增加 endpoint。
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/usage.py`、`adapters/langgraph/sdk_client.py`、`core/runtime_contract.py`：可空摘要、精确错误和 Token notice 白名单、拒绝私有字段注入，复用既有 ACL。
- `.env` 示例与 doctor：开关默认关闭，需 Usage 和迁移，两端部署配置一致；不改实际 env。
- 新增 Runtime `tests/{runtime,middlewares,durable}/test_token_budget.py`、`tests/durable/test_token_budget_ledger.py` 和 `tests/fixtures/token_budget_platform.py`；隔离平台复用原 `test_tool_error_platform.py::stack`，仅扩展图列表与测试启动窗口。API 在原预算投影与 Run Usage 测试中增量覆盖。

## 锁定版本的派发边界

真实 compiled graph 验证发现：langchain-core 1.6.0 的 sync `handle_event` 会将异步 callback 的 coroutine 交给 `_run_coros`，其异常被吞掉，不受 `raise_error` 控制。仅把原 AsyncCallbackHandler 设为 `raise_error=True` 无法阻断同步模型调用。

因此维持唯一采集 callback，附加引用同一 `RuntimeUsageCallback` 的同步派发守卫。该守卫没有采集、计价、缓存或账本，仅调用共享额度决策，`raise_error=True`；`run_inline=False` 使异步派发先调度 handlers，避免拒绝时遗留未 await 的 coroutine。同步直接传播异常，异步在进入模型前等待守卫；预算启用时原 Usage callback 才设为 inline，保证开始/完成事实的顺序。`usage_only_config` 同时继承两者，覆盖隐藏模型。

compiled graph 与真实 Worker 均用 provider 请求计数和工具副作用证明阻断；专用错误不被 retry/fallback 当作 provider 故障处理。自然最后回答刚好达到 cap 时 `stop_code=null`，只有确实拒绝新增工作才记录停止原因。不剥离已生成的 tool calls，不追加付费总结。

## 验证与证据

- Runtime 定向回归 **157 passed**（5 个既有 Swig warning）；API 预算/Usage/流安全回归 **61 passed、177 subtests**。涵盖唯一采集、晚到完整用量、unknown、配置边界、四图 enabled schema/probe 零 I/O、隐藏调用与旧能力回归。
- 完整隔离 PG/Redis/API/Worker HTTP 测试 **1 passed、30 场景、344.24 秒**：四图主子共享、自然触限完成、HITL、取消、SIGKILL 同 Run 接管、未知 started、两项目授权/撤权、Protocol 回放及关闭开关。见 [后端证据](token-budget-backend-evidence.json)。
- 真实 PG 迁移重复运行、去重/晚到替换、锁超时和 Usage 中断恢复通过；旧 HEAD 源码在扩展库 begin/finish/Usage 读取 **1 passed、11.24 秒**，冻结策略和停止事实不丢。迁移 `0003_token_budget` 的 `down_revision=0002_run_control`，downgrade 保留扩展列。
- 真实 DeepSeek 摘要与 child 两次物理调用，**43 tokens、coverage=complete**；Run cap4096、单次输出128。见 [真实 provider 证据](token-budget-real-provider-evidence.json)，不将受控 HTTP provider 计为真实供应商账单。
- 性能 **12 组通过**：100/1000 calls × 1/4/8 Run × 开关。1000 calls/1 Run P50 46.988→48.281ms、P95 197.470→214.891ms；关闭无新增恢复事务，开启每 Run 新增一次短恢复事务。见 [性能证据](token-budget-performance-evidence.json)；本机共享负载，不代表生产 SLO。
- [冻结 fixture](../fixtures/token-budget-v1.json) 包含 DTO schemas、7 个 Usage 样本、3 notices、2 errors，来源明确；前五个 Usage 样本来自真实 HTTP，其余为受控契约样本。实际命令、逐 Task Phase 和全量失败归属见 [15 验证记录](../15-token-budget-governance.md)。
- 收尾 Runtime24/API6个改动 Python 文件 Ruff check/format 全通过；配置校验重跑17 passed，diff空白检查通过。冻结fixture再次通过当前DTO/投影校验，13份变更Markdown规范检查及67个相关链接有效；任务/README/CONTEXT/FEATURES/标准健康表已对齐。

两服务全量基线**未全绿**：Runtime 1008 passed、16 failed、81 skipped、58 deselected、1 teardown error；API 414 passed、37 failed、18 skipped、866 subtests passed。旧 HEAD 对照复现了过期测试接口、非法 project UUID、Workspace HTML/CSP 旧断言等失败；外部 PG/MCP 启动属于环境边界。全仓文档检查另有38条绝对路径违规，均来自9份未改文件，逐行对照HEAD一致。没有通过改 skip 或修范围外行为掩盖失败，也不据此宣称全仓可直接上线。

## 接续与限制

前端业务代码与浏览器场景未实施；仅余 16/F-T01—F-T04、15/E02 与 T07-F 联合 Final。16 已是实现版交接，前端无需自建计数器、通知通道或预算状态机。

功能默认关闭；启用前需 Usage、迁移和 API/Worker 一致配置。检查基于已观测 Token，在途请求允许超额，缺失/持久化不足拒绝新增工作，不承诺严格金额上限；同 native Run 接管恢复原策略，新 Run 独立。不做逐 Agent 配额、第二账本或 BoundedDict。未提交、部署、修改实际 env 或依赖锁；本轮隔离服务与临时 PG 已停止。
