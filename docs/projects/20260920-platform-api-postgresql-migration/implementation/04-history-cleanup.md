# 历史数据清理

2026-09-20，用户明确授权清理失效令牌、6 个迁移测试库、历史会话和审计数据。

## 实现

- `scripts/cleanup_env.sh` 增加独立 `--history` 入口；不顺带清文件，默认预览。
- `apps/platform-api/scripts/cleanup_history.py` 增加显式 `--platform` / `--runtime` / `--drop-test-database NAME` 范围。执行要求本地开发环境、逐库确认、停写声明和活动连接检查。
- 每个目标先 pg_dump，再验证 archive 目录可读；全部备份完成后才执行。控制面与 Runtime 各自事务、锁超时、TRUNCATE RESTRICT；不使用 CASCADE 或 DROP FORCE。
- 迁移测试库逐个指定完整名称，拒绝通配符、业务库和系统库，不存在时报告已不存在。管理员连接通过环境变量传入，不打印凭据。
- `apps/platform-api/tests/test_history_cleanup.py` 覆盖名称保护、远端拒绝、真实 PG 临时表中的有效令牌保留、活动运行阻断、历史清理及回滚。
- 文档：`docs/guides/database-operations.md` 补充参数、备份和跨库部分成功时的处理规则。

## 实际清理

通过 local-stack 停止四进程，备份保存至 `apps/platform-api/.data/backups/20260920T022351647053Z-history-cleanup/`。目录权限 0700、数据库 dump 权限 0600。manifest 逐目标记录成功状态。

| 范围 | 本次清理数量 |
| --- | ---: |
| 过期或已撤销 refresh token | 127 |
| run_requests | 23 |
| audit_logs | 1033 |
| threads / runs | 10 / 23（含 8 个 interrupted） |
| checkpoints / checkpoint_blobs / checkpoint_writes | 170 / 100 / 289 |
| runtime_events | 980 |
| dear_external_tasks / dear_skill_bindings | 2 / 33 |
| 迁移测试库 | 6 |

删除的测试库完整名称为 `platform_migration_test_` 加以下后缀：`quiet_20260920`、`load_20260920`、`forbidden_20260920`、`unversioned_20260920`、`recovery_platform_20260920`、`recovery_runtime_20260920`。各库均有独立 dump。

项目及 Agent 配置、全局 Graph/模型、有效令牌、技能定义/版本、长期记忆、Runtime assistant 配置、迁移版本表保留。旧项目仍为软删除，不将这次会话清理描述成项目物理清库。

## 验证

- 真实 PG 回归 2 项通过，Ruff、格式、bash -n、diff 检查通过。
- 清理前控制面和 Runtime dump 分别恢复到临时隔离库：119 项目、171 Agent、1033 审计；10 会话、23 运行、170 检查点，计数匹配。临时恢复库验证后删除，未覆盖原库。
- 原服务恢复启动后：项目接口仅返回 test，4 个 Agent 保留，会话 search 返回空数组；运行、检查点、事件计数为 0。6 个迁移测试库均不存在。
- 有效令牌保留 218 条（验收再次登录会增加新令牌）；长期记忆 2 条、技能定义 1 条保留。
- 服务启动/验收产生的新审计属于新数据，不反复清除以追求永久零记录。

## 缓存边界

数据库入口不隐式操作 Redis 或文件工作区。本次另行导出当前 Runtime 的 `graphharbor:runtime:run-stream:*` 历史缓存，再删除备份过且长度/末条 ID 未变的键；不执行 FLUSHDB，不混删其他测试命名空间。Redis 原生 DUMP 在大流导出时超时，尚未删除数据；改用 XRANGE 导出完整消息 ID、字段和 TTL，字段值 base64 保存，导出完成后才删除。最终数量见验证证据。

跨库清理不是分布式事务；每库成功记录在 manifest 中，遇到后续失败可按记录和备份恢复。本次数据库部分全部成功。

最终缓存结果：导出并删除 875 个 Runtime 历史流（151592 条消息），剩余 54 个其他测试命名空间键保留。缓存备份为 redis-runtime-streams.jsonl.gz，消息字段值按 base64 解码后可使用原消息 ID 重建。数据库与 Redis 证据汇总：[history-cleanup.json](../evidence/history-cleanup.json)。
