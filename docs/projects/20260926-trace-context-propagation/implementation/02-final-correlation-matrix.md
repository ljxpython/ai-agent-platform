# 关联闭环矩阵与最终实测

2026-09-27；对应 T1—T8。沿现有 API、Runtime、Web 组合验证，没有修改 Runtime/GraphHarbor 的代码、配置或数据库结构。

## 实现

- `apps/platform-api/src/platform_api/modules/runtime_gateway/presentation/http.py:58`：`RuntimeStreamingResponse` 用 Starlette 现有断连监听记录已确认的客户端断连；发送侧 `OSError` 记 `client_disconnect`，其他取消记 `unknown`，继续传播取消并执行 shielded 清理。原因回调优先级仍由现有帧解析器决定。
- `apps/platform-api/src/platform_api/modules/audit/contracts.py:4`：`ListAuditEventsQuery.validate_correlation()` 用 Unicode `Cc` 分类拒绝所有控制字符，补齐原实现仅检查 ASCII 控制字符的缺口。
- `apps/platform-api/tests/test_request_correlation.py`、`test_runtime_gateway_event_redaction.py`、`test_audit_correlation.py`、`test_audit_stream_status.py`、`test_run_requests.py`：补并发/取消、SSE 关闭分类、两种数据库的授权过滤、审计写失败、审批/取消关系与输入边界。`test_error_response_contract.py` 复用现有真实链路，增加 submission 窗口、权限拒绝和线程流跨 Run 重连断言。

## 验证要点

- 本机 PostgreSQL 17.11、既有 `audit_logs` schema：测试数据在事务内插入并回滚；四项真实 JSON 过滤行在两个项目中分别命中 3/1，分页 2、总数 3。SQLite 同一断言通过。
- 现役平台真实重试请求 `0b9c86fa5de14900a68e577d9f62eb27`、`6d392f8c39964201a710de02cc225ecc` 共用 submission `8c52c864-0860-43fc-bdcd-0cbad4950895`、Run `c786612f-f9b0-4810-863b-6251992bd823`；Langfuse trace `77cf961ec70884670c0c38e9c2712422` 的可信 metadata 同时匹配 Run 与提交编号。Runtime `runs` 记录为 `success` 且有 heartbeat；本地栈 worker launcher PID 38768、子 Python PID 38784 在验证时存活。
- 同一隔离 Thread 的第二个 Run `45aeec01-77cc-46d6-87a1-e24325c97738` 执行期间，线程流断开并立即重连返回200；Run 后续成功。两次流请求编号 `2b2fb0bf212c41b5aaa0cb22d2836a25`、`b5e3877dc74a45df835210ba75692e19`，各一条 opened/closed，`close_reason=client_disconnect`，均无固定 `run_id`。此前一次502与 WatchFiles 测试文件编辑触发 API 热重载同窗；无编辑干扰的复测通过，不记为业务限制。
- 现役旧隔离审批/取消样本通过授权 API 精确反查：取消目标 Run 命中 `target_run_id`、`operation=run-cancel`、`outcome=accepted`；审批恢复 Run 命中真实 `parent_run_id`、`interrupt_key`、`operation=approve`。ACK 只代表接受，未当作终态。
- PG 既有 112135 行：request_id 查询 30 次中位 0.577 ms / p95 1.105 ms，走 request_id 索引；7 天、项目过滤的 run 关联查询中位 1.276 ms / p95 1.834 ms，走 project_id 索引后 JSON 过滤。SQLite 3.50.4 内存 10000 行：同类关联查询中位 2.442 ms / p95 7.911 ms，走 project_id 索引。用户确认本期只记录实测数据，没有批准的查询 SLO，不作阈值达标宣称。

## 边界

真实 worker 身份以本机单 worker 进程、Runtime 持久 Run heartbeat/终态和 Langfuse 同 Run trace 共同核对；持久表在终态清除 `lease_owner`，不能伪称有一条永久保存的 worker ID 关联。没有改写已接受 Run，也没有迁移、部署、提交或分支操作。
