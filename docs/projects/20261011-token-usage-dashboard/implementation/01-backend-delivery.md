# 非前端实施记录

## 时间与范围

2026-10-11，G01用户方案评审通过。当前b2b1关联Worktree实施Runtime查询/索引/签名、Platform API权限/接口/DTO/ACL/审计及非前端验证。Web实现由同事接续，生产发布未授权；不创建分支或提交。本文件记录初始后端阶段，容量失败已由[02-B01优化记录](02-b01-optimization.md)及05的解除证据取代。

## 改动与验证

### Runtime

- 新增 `observability/usage_analytics.py`：strict 查询模型、Token/费用安全投影、前窗/分桶/Top-N+other、distinct Run、partial/unknown/disabled/unavailable 状态；`_read()` 在取消后继续持有并发额度，且消费迟到 SQL 异常，避免 `Future exception was never retrieved`。
- 新增 `db/repositories/usage_analytics.py`、`http/usage_analytics.py` 和 `0004_usage_analytics.py`：在 Runtime 自有台账上使用 READ ONLY REPEATABLE READ、时间/锁/连接超时、查询并发上限和 keyset 候选分页；内部聚合仅接受用途绑定 HMAC，拒绝重复头/键、错误 path/method、超时和超过64KiB正文。
- 补充 `scripts/verify_usage_capacity.py`：百万调用容量报告在并发读/边界不可用时仍完整落盘，不因错误返回形状抛出 `KeyError`。

### Platform API

- 新增 `modules/usage_analytics/` 五个文件：三条公开 GET、参数/DTO 校验、名称和目录解析、平台/项目 scope、Fernet+HKDF 绑定 cursor、Thread/Run ACL、删除过滤和审计。
- 新增 `20261011_0008_merge_heads.py`：合并原双 head，并拒绝 SQLite 数值型 UUID；保留旧 completion 字段。
- 更新 Runtime gateway、SDK 错误白名单、IAM policy、HTTP 审计解析、请求上下文和服务文档；修复已有 `VerifiedDelegation.credential_id` 丢失造成的普通 JWT 认证 500。

### Fixtures/交接

- 冻结 `fixtures/` 的四份 schema、11 个成功/状态响应、4 个错误 Envelope 和 HMAC 向量，覆盖完整/部分/零/未记录/关闭/故障/缺价/空 cursor。
- 新增 `frontend-handoff.md`，明确三 GET、权限、null/费用/缓存口径、分页和 W01–W04 接续范围；未修改 `apps/platform-web/`。

### 关键前后对照与定位

| 位置 | 改动前 → 改动后 | 理由 |
|---|---|---|
| `apps/runtime-service/src/runtime_service/observability/usage_analytics.py:32` | 新增`_read()`；裸shield包装 → 保留wrapped Future并在完成回调消费异常 | HTTP取消不释放仍执行的SQL配额，也不留下未处理异常日志；回归先失败后通过。 |
| `apps/runtime-service/src/runtime_service/db/repositories/usage_analytics.py:28` | project/run文本拼接排序 → project UTF-8 bytes加`uuid_send(run_id)`的固定16字节后缀 | 保留跨项目Run唯一性并减少collation开销；初始优化后仍失败，随后0005投影继续完成容量治理。 |
| `apps/platform-api/src/platform_api/modules/usage_analytics/service.py:412` | 仅Thread/Run用量 → 独立`dashboard()`与`runs()`，HTTP前后短事务重授权 | 平台治理数字与会话内容权限各自判定，不复制Runtime台账。 |
| `apps/runtime-service/tests/durable/test_token_budget_ledger.py:119` | 旧读取器直接查保留库 → 旧应用源码保留当前migration目录并运行lifespan后读取 | 对齐真实启动需要认识新head的回退前提，保留0004与原Token额度/停止原因。 |

所有新增路径、调用者、router注册和相关fixture已同步；没有引入新依赖、通用框架或第二套采集。

### 实际验证

- Runtime 定向回归：167 passed；真实 Runtime durable：6 passed、2 skipped；旧应用读取保留台账并在当前 `0004_usage_analytics` migration head 启动：1 passed。
- Platform API 定向回归：95 passed、1 skipped、18 subtests；SQLite轮跳过的PG分支在专属PG库另验1 passed。
- DTO fixture：11 个响应、4 个 schema、4 个错误 Envelope 校验通过；双端 HMAC、真实慢 HTTP 504/断网 502、PG 停机/重启、权限/ACL/审计和真实 `deepseek-v4.1-flash` 核账通过。
- 最新真实模型471 Token、USD 0.000720000000；运行后真实Thread fork未复制ledger调用、未改变项目汇总。证据`.local-stack/usage-chain-fork.json`，并保留前两次470/488 Token报告。
- 改动Python31文件Ruff check/format通过；18份新增/修改Markdown经`check_docs.py`定向检查、24个项目相对链接通过；`git diff --check`及新增项目尾空格/换行、凭据模式扫描通过。
- 初始容量门禁B01未通过：百万数据10并发×3轮0/30 available，读p95 4524.20ms，双写p95 28.62→42.04ms（+46.89%），200项目/90日边界unavailable；报告 `.local-stack/usage-capacity-million-final.json`。B01优化已解除该失败，原报告和10万/早期+174.77%写入影响仍保留。

本记录是初始实现细节，任务完成度以项目`02/03/04/05`为准；后续B01投影已获用户批准并完成，见`implementation/02-b01-optimization.md`。独立查询资源未引入。
