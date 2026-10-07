# 持久预算与 Runtime 收尾实施

> 历史阶段记录：2026-10-07 用户要求对齐官方 Worker；本文中跨 attempt 总 deadline、模型 Worker 重试与旧接管证据已由 [后续修订](02-langgraph-worker-parity.md)取代，其余 Runtime/API/取消实现保留。当前进度只看 tasks.md。

日期：2026-10-06；对应 T02-T09，含 T10/T12 非前端阶段证据。用户已批准实施，未改前端、未提交、未改现役进程。进度只看 tasks.md。

## GraphHarbor

正式独立 GraphHarbor checkout 已核对，保留原有 cron 改动。以下路径均从该仓库根开始。

- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py:43/171/468/547/863`：`_budget_expired` 和 `RunRepository.claim_next/fail/requeue_for_shutdown/requeue_expired`；首次claim行锁事务在kwargs冻结version=1、started_at、deadline_at、timeout_seconds，重试/接管/停机保留；到期Run走唯一timeout。
- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/production_worker.py:365/648`：`ProductionWorker.run_once/execute`，数据库剩余时间转换本进程monotonic；等待包含factory，drain使用较小剩余量；只给factory私有快照，invoke_graph不携带。
- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/database.py:276:run_to_dict`：公开Run过滤私有预算。
- `libs/langgraph-runtime-pg/tests/test_run_budget.py:72/105/136/170`：真实隔离PostgreSQL/Redis；冻结/requeue/reaper、到期重试不打开图、不同Worker H不续期、慢factory/模型、shutdown不加时、次数/预算先耗尽两种结果。

关键差分：`asyncio.wait(timeout=H)` 改为 `asyncio.wait(timeout=remaining_timeout())`，不新增第二个运行计时器。

## Runtime

- `apps/runtime-service/src/runtime_service/runtime/run_budget.py:39/52:RunBudget/read_run_budget`：不可变值，版本、身份、有限数值、UTC时间范围与收尾窗口校验；正式run-create缺预算明确失败。新增 `tests/runtime/test_run_budget.py`，schema/probe不启动时钟。
- `apps/runtime-service/src/runtime_service/middlewares/timeout_wrapup.py:26:TimeoutWrapupMiddleware.awrap_model_call`：模型请求边界追加通用收尾指令；model_copy + request.override保留原始内容块及附加属性，去重，G=0关闭。新增 `tests/middlewares/test_timeout_wrapup.py`，同时运行真实create_agent捕获prompt。
- `apps/runtime-service/src/runtime_service/middlewares/model_call_timeout.py:28/46:ModelCallTimeoutError/ModelCallTimeoutMiddleware.awrap_model_call`：本scope expired才转换来源；provider TimeoutError与外部取消继续传播；仍继承TimeoutError，保留Worker既有有界重试。
- 四正式组合根 `services/dearflow_agent/agent.py:149`、`services/demo/showcase_demo/agent.py:76`、`services/reference_agent/agent.py:142`、`services/demo/workflow_demo/agent.py:111/143`（均相对Runtime源码包）：主/子共享RunBudget，workflow内部重建沿用同一对象；公开绑定配置移除私有预算。相应服务测试补真实图/主子/schema/重建回归。
- 配置模板与预检：H 沿用原值，G 默认120，根 stack 补环境传递。

实际发现：content_blocks 会标准化图片并生成 ID，直接转换会改动原多模态块；已保留原 content 块追加文本。

## Platform API 与资源取消

- `apps/platform-api/src/platform_api/core/runtime_contract.py:75/181/236/268`：新增 `_reject_run_budget`，在contract/payload/Protocol归一化复用递归拒绝；覆盖input、config、context、metadata和resume，不信任客户端双下划线参数。
- `apps/platform-api/src/platform_api/adapters/langgraph/sdk_client.py:97:redact_runtime_private_fields`：既有递归脱敏键集合加入预算字段，使HTTP/SSE/history共用保护。未改公开路由或lifecycle类型；新 `apps/platform-api/tests/test_run_timeout_contract.py` 回归completed不覆盖timeout。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/workspace/backend.py:103:DearWorkspaceBackend.aexecute`：原 `asyncio.to_thread(LocalShellBackend.execute)` 取消时线程/子进程可继续工作；改用stdlib异步subprocess、干净环境、独立进程组及有界输出。取消或工具超时kill进程组并等待退出，原CancelledError向父传播；新增 `tests/services/dearflow_agent/test_execution.py:test_local_cancellation_kills_shell_and_children`。Docker仍复用既有执行清理。

关键差分：

```python
# 原scope不能区分provider自身超时
async with asyncio.timeout(self.timeout_seconds):
    return await handler(request)

# 新scope只细化本次过期来源
scope = asyncio.timeout(self.timeout_seconds)
try:
    async with scope:
        return await handler(request)
except TimeoutError as exc:
    if scope.expired():
        raise ModelCallTimeoutError("runtime.model_call_timeout") from exc
    raise
```

## 本地双包与HTTP验收

- `scripts/verify_run_timeout_budget.py:52:main`：复用隔离服务辅助函数，建立专用PG/Redis、临时SQLite平台库和工作区，以真实平台认证/项目授权访问Run/状态/history/SSE/cancel；检查幂等、唯一durable终态、租约、checkpoint和私有字段。真实Worker子进程SIGTERM退出后更换PID接管，不把同进程对象重建当作重启。
- `apps/runtime-service/tests/acceptance_app/run_budget_probe.py:29:get_agent`：仅测试图，消费真实Worker预算、写已核实进度和checkpoint、控制慢模型/HITL/提示窗口，不注册为业务Agent。
- `scripts/verify_scheduled_tasks.py:serve`：复用已有启动/退出助手，仅添加可选启动等待上限供预算验收冷环境使用；默认仍15秒，无新服务编排抽象。
- 本地双包产物位于 `/tmp/run-budget-post42-dist`，候选冷环境 `/tmp/run-budget-post42-venv`；API/Worker同为post42。post41冷环境只用于原包能力差异核对，不与增强Worker混跑。

## 阶段验证

- GraphHarbor 定向16 passed；生产/持久化/公开契约100 passed、4 skipped（既有上游夹具缺项，未当作通过）。
- Runtime 定向109 passed、1 skipped；预算/收尾/schema/主子取消/真实Docker相关53 passed、1 skipped。
- 平台新契约必须显式 PYTHONPATH 指向当前 worktree；旧 editable 安装只作为基线，不作为改动验证证据。
- local shell取消与工具回归15 passed；Platform API全量321 passed、23 skipped、606 subtests passed。
- 隔离HTTP脚本退出码0，12组结果全部符合预期，证据 `/tmp/run-budget-http-e2e.log`；具体run/thread/PID和门禁见verification.md。Runtime全量614 passed、5 failed、34 skipped、51 deselected，外围失败未写成全量通过。
- 收尾定向重跑89 passed/1 skipped、API预算契约3项通过；相关Ruff check与format check通过。修正本次新增local shell取消测试的一处换行，无行为改动；双仓diff检查与本次文档定向检查通过。

## 发布与回退限制

post42只完成本地构建/隔离验收，PyPI双包版本均404；未上传，平台锁文件仍post41。正式执行缺预算会失败，因此当前代码需要post42发布和锁定后才能部署。后续回退必须同时核对Runtime代码与依赖组合，不能仅把依赖降回post41。前端、正式发布/锁定/复验及完整回退门禁均未冒充Final完成。
