# 后端与 Runtime 实施

日期：2026-10-09。范围：P1.3、P2.1-P2.4、P2.7、P3.1-P3.3；进度以 tasks.md 为准。

## 持久来源与接线

- `apps/platform-api/src/platform_api/modules/runtime_gateway/infra/sqlalchemy/models.py`、迁移 `20261009_0007_run_completion.py`：新增 origin/event/receipt，RunRequest 可选来源；不读引擎数据库。
- `application/service.py` 的 `_promote_protocol_run_start` 与 `repository.py::RunRequestsRepository.mark`：dispatch 前同事务持久来源，callback 与响应绑定共用 Origin→RunRequest 锁序，先回调/响应丢失不会清掉已接受事实。
- `core/security/tokens.py::create_runtime_delegation_token`、Runtime `runtime/auth.py`、`auth/platform.py`：可选签名 `callback_context.origin_ref`，严格 UUID，旧 token 兼容；拒绝公开输入伪造。
- `scheduled_tasks/service.py`：create/update 前来源与重新签名，任务 owner 决定 recipient；服务账号没有用户 feed；旧版本来源保留用于晚到回调。

## 收件与公开查询

- `domain/completion.py`：v1 严格正文/公开 DTO，`execution_stopped` 必须为布尔 true；安全码共用 `domain/error_codes.py`。
- `application/completion.py`、`completion_repository.py`：原始 bytes HMAC、30s 时钟窗口、双 key 轮换、event/run 唯一、当前 ACL、30/90d 保留；来源未知与数据库失败 503，提交后 ACK。
- `presentation/completion_http.py`：内部回调及历史/feed/read 三公网接口；成功、验证错误、已知错误统一 `private, no-store`。游标绑定 actor/project/unread 模式；ACL 空页有界扫描不漏晚到旧 Run。
- Run/Thread 删除与 callback 共用 PostgreSQL advisory thread 锁、删除审计事实，禁止晚到回调复活删除目标。
- 容量验证发现 outer join 未读过滤导致 10k 事件排序，改为索引选候选→limit→当前 ACL/receipt 关联；缺失 ACL 仍推进 cursor。回调 p95 27.692ms、feed 27.057ms（100k、20/s+10/s），证据见 verification。

## Runtime 与运维

- `run_completion/projector.py::project_terminal_outcome` 为纯函数；仅映射既有预算、Workspace、模型稳定码，未知兜底。不依赖每个 Agent 装 tool、Thread 旧错误或 Langfuse。
- 最终模型异常只携带安全分类，在 except 块外抛出，避免 provider 原文异常链。API `adapters/langgraph/sdk_client.py` 保留白名单模型码与原有 SSE 形状，过滤新增私有 callback 字段。
- `scripts/backfill_run_completion_origins.py`：按 owner/project/tenant 重新授权，dry-run/apply/revert，0600 原子清单，响应丢失续跑复用 origin；拒绝覆盖变化配置。迁移窗口内暂停任务编辑，因为原生 cron PATCH 无 CAS。
- `scripts/maintain_run_completions.py`：预览/应用详情与 receipt 清理，90d 去重墓碑；来源不自动清理。
- `scripts/export_run_completion_contract.py`：从实现导出 OpenAPI，并校验真实链路样例。

## 验证与限制

已执行 PostgreSQL 并发/retention、签名/DTO/权限、SSE/diagnostics 回归和隔离 Worker 链路，逐次结果写入 verification 的 Phase。未执行现役数据库迁移或生产启用；前端由同事实施。旧基线 RunRequest fixture 的非 UUID project 与 Runtime ACL mock 签名问题已有独立复现，不能为修测试放宽安全边界。

## 正式包验收夹具修正

`tests/integration/test_model_resilience_worker.py::verify_scenarios` 的 `slow/budget` 会修改共享 Agent 策略，原先只在 `cancel` 后恢复，导致后续用例继承短超时。现在三类临时策略结束后都恢复；completion 模式普通调用使用 15s/60s，慢流仍在 3s 单次期限内超时，100s Retry-After 仍受 20s 总预算限制。只调整验收夹具，不改变生产超时、重试、通知或执行策略。早期正式包失败及修正后的真实结果分别保留。

完整矩阵还暴露一次性任务创建的时序风险：原夹具只预留 3 秒，授权/请求耗时可能让 `run_at` 在校验前过期。夹具改为创建未来一小时的任务，在隔离数据库明确设置 `next_run_date` 到期；备用模型撤权场景先撤权再触发。仍走真实 Cron scheduler/Worker，不放宽生产校验或扩大轮询上限。

正式native尾段已执行8定时场景与旧cron回填，队列blocker的10s等待超时，未执行重启断言；没有改生产代码或继续重复完整矩阵。v6的once创建400未保留正文，不能把run_at过期推断写成已证实错误。真实JUnit统计/哈希和部分步骤单独固化到evidence，两仓tasks/README/CONTEXT同步资源blocked，前端契约包重新按实现导出并逐项核验一致。正式post44同时包含既有metadata CAS/migration011，发布事实更新不代替其他专项的使用方验收。
