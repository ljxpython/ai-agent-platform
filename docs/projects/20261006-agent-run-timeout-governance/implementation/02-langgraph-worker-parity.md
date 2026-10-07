# LangGraph Worker 语义修订

日期：2026-10-07；对应 T13 与独立 GraphHarbor G05-G07。用户明确要求按 LangGraph Server 实现，取代前一阶段跨 attempt 总 deadline。进度只看 tasks.md；未修改前端、正式锁文件或现役服务，未提交/发布。

## 实际改动

GraphHarbor 路径均相对独立仓库根：

- `libs/langgraph-runtime-pg/src/langgraph_runtime_pg/run_store.py:RunRepository.claim_next`：每次 claim 更新私有 attempt UTC/H；删除旧 deadline 对 fail/reaper 的提前终态判断，退避/停机不累计到下一 attempt。
- 同文件 `attempt_count/can_retry/requeue_for_shutdown`：复用已有 retry_counters，正常 checkpoint drain 归还 attempt；runs.retry_count 始终作为单调 generation，避免旧 saver 写入。支持 BG_JOB_MAX_RETRIES，不增加 migration。
- `production_worker.py:_run_timeout_seconds/_drain_grace_seconds/_is_infrastructure_error/run_once`：兼容官方 H=86400、最大 attempt=3、grace=180/最大3600 与旧变量优先别名；用户/provider 超时不重跑整图，明确 DB 瞬时故障才重试。查询最新 checkpoint metadata 确属当前 Run 后移除原 checkpoint_id、以 None input 继续，已完成节点不重新开始。工厂/执行/drain仍共享本 attempt 剩余 H。
- `run_state.py:transition`：代次只校验非负，次数上限交由独立 attempt 计数执行。
- `tests/test_run_budget.py`：当前 attempt 更新、旧 deadline 后接管、用户错误单执行、重复 drain/故障上限、官方配置、真实 PG checkpoint 恢复、DB 异常边界。
- `tests/test_production_contract.py`：原 DB 故障夹具改为驱动 OperationalError；手工次数夹具同步独立 counter；正常 drain 即时可接管。
- `scripts/verify_official_worker_timeout.py`：实际执行锁定官方 worker，隔离图/状态 sink；仅验证 Worker 分支，无生产连接。

平台路径相对本仓库根：

- `apps/runtime-service/src/runtime_service/runtime/run_budget.py`：说明改为 Worker attempt 预算，schema 和解析接口不变；软收尾仍由应用 middleware 实现，未迁入 GraphHarbor。
- `scripts/verify_run_timeout_budget.py`：模型 scope 超时仅运行一次 Worker；真实 SIGTERM 后等旧 deadline 过去，新 PID 用 H=20/G=5 接管相同 Run，并断言新 attempt 预算与 checkpoint 继续。高负载下先 schema 构图、普通验收 H=30/G=10；测试模型的等待大于当前 H，生产配置不变。
- 方案、任务、验证、前端交接与服务规范统一现行口径；原 01 实施记录标历史，正式包、前端和 Final 门禁保持。

## 验证

官方分支探针、真实 PG/Redis 回归、修订双包冷安装及平台 HTTP 的实际结果统一记录于 [verification.md](../verification.md) T13；未执行的发布/浏览器/完整回退不写成通过。
