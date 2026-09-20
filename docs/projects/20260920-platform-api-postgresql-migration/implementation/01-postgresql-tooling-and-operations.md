# PostgreSQL 迁移工具、启动入口与运维规范

日期：2026-09-20。状态：partial，实际本地业务库未切换。用户在本会话批准专项并要求补充首次服务器部署、未来迁移及本地 PG 规范。

## 改动与理由

| 文件与入口 | 改动前 → 改动后 | 理由 |
|---|---|---|
| `apps/platform-api/scripts/database.py:1`；`configured_engine()`、`check_database()`、`clean_ledgers()` | 无统一控制面 preflight → check/preflight/upgrade/clean-ledgers | 复用 Settings/Alembic，拒绝 SQLite、自动建表、维护库和未登记的非空 schema；清理目标需确认 |
| `apps/platform-api/scripts/migrate_sqlite_to_postgres.py:1`；`snapshot()`、`copy_data()`、`digest()` | 无数据复制工具 → WAL 一致备份、空目标/字段集检查、外键顺序复制、事务内摘要比对 | 保留所有 20 表、ID、密文、JSON/SQL NULL、Decimal；不导入 alembic_version；失败回滚 |
| `apps/platform-api/migrations/env.py` | 直接设置 URL → 转义 ConfigParser 的百分号 | 支持 URI 编码的特殊字符密码 |
| `scripts/local-stack.sh`；`validate_stack()`、`migrate()`、`restart_one()` | 只迁 Runtime → API 启动前执行控制面检查与 Alembic | 失败阻断启动，避免自动建表掩盖版本差异 |
| `scripts/cleanup_env.sh` | 默认删 Runtime/测试库、SQLite 流水与备份 → 默认日志/缓存；控制面流水显式选择 | 保留迁移源和恢复材料；RESTRICT，禁止级联扩大范围 |
| `deploy/postgres/init/01-init-shared-databases.sh` | SQL 直接插值 → psql 变量与 format 的标识符/字面量转义；新增 --platform-only | 复用既有建库脚本，支持宿主机及含特殊字符密码 |
| `apps/platform-api/.env.example`、`docs/local-deployment-contract.yaml`、三个 Compose、`apps/platform-api/Dockerfile` | 本地默认 SQLite / 容器自动建表 → PG、关闭自动建表、先迁移后 API | 统一正式入口；保留 SQLite 单元测试 |
| `docs/guides/database-operations.md` 与现行 README/手册 | 新增规范并挂接导航 | 覆盖首次建库脚本、已有数据卷、后续迁移、恢复、本地 PG 和清理 |
| 原 ADR 及 7 处其他专项引用 | 本机绝对路径 → 仓库内相对链接 / 外部参考源码相对定位说明 | 全仓文档检查通过；ADR 标明已批准的修正边界 |

当前主键为 UUID，不引入序列同步或通用 ETL 框架；源 schema 不匹配时拒绝导入，需补充映射再评审。无时区时间必须显式确认 UTC，不自动猜测。当前本地实际 `.env` 与 SQLite 数据未改动。

## 可运行检查

- `apps/platform-api/tests/test_sqlite_to_postgres_migration.py`：WAL 备份、禁止覆盖、0600 权限、配置保护、百分号 URL；真实 PG 20 表复制、超长字符串触发整笔回滚、无时区拒绝、非空目标拒绝、连接重建、流水清理保留其他 18 表。
- `scripts/test_local_stack_backend.py`：增加控制面迁移失败不启动服务、预览保留源库/备份；与原两个环境测试共 4 项通过。
- 真实隔离 PG/API 容器完成 Alembic、登录、项目创建/列表、重启后再读、pg_dump/pg_restore 全表摘要核对。
- 新增 Python 和迁移配置 Ruff、compileall 通过；Shell 语法、三份 Compose 配置、文档和 diff 检查通过。

## 已知限制与后续

全量回归 198 项：192 通过、5 跳过、1 错误；单独复跑 `test_model_connection_lifecycle.py` 7 项，6 通过、1 同样错误。失败为 `test_service_account_revoked_token_is_not_reusable` 在首次凭据兑换时得到 `ForbiddenError: Project role missing`；本轮未修改对应测试、鉴权策略或 Runtime Catalog 业务实现，不掩盖为全部通过。

未完成：实际停写切换、真实历史会话/密钥验收、浏览器全链路、完整四服务 Compose、约定的 2 worker / 10 并发 / 5 分钟及 SQLite 对比、跨服务恢复演练。专项维持 partial，不能发布“迁移已完成”的结论。
