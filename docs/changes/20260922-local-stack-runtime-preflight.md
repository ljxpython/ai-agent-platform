# 本机 Runtime audience 恢复与单服务重启预检

2026-09-22，用户明确批准恢复配置、补预检、重启并验收。

9 月 21 日提交 `b5f1ca8` 在调整超时示例时删除 `GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE`，保留 issuer。当前本机配置同样缺 audience，创建 Run 时现有 GraphHarbor 因签发方/接收方不成对报 500。完整 start 有预检，restart-one 原来没有。

- 恢复 `apps/runtime-service/.env.example` 及本机未跟踪 `.env` 的 `GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE=graphharbor-worker`；没有修改 Runtime/GraphHarbor 业务代码。
- `scripts/local-stack.sh:restart_one()` 对 Runtime API/Worker 复用 `validate_runtime()`，在停止原进程前拒绝无效配置。
- `scripts/test_local_stack_backend.py` 增加失败预检不会停止/启动进程的回归断言，两个 Runtime 入口均覆盖。
- shell 语法检查及新增定向测试通过。现有脚本测试组 5 项中 4 项通过、清理 dry-run 夹具因临时目录缺 `.git` 失败；本次未改清理脚本，不将整组写为通过。
- 已重启 API/Worker，真实平台→Runtime→Worker→模型链路完成 `interrupted → approve → success`，1 passed（48.922 秒），`/tmp/governance-real-model-approval-3.log`；专用测试 Thread 已删除。

权限项目统一验收见 [07](../projects/20260920-platform-access-governance/07-implementation-and-verification.md)。不重新执行历史数据清理或数据库迁移。
