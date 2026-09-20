# Platform API PostgreSQL 迁移专项 - 整体方案


**执行状态：** 已完成（done）：真实本地切换及本轮验收通过；最新证据见 [verification.md](verification.md)。以下静态现状表保留立项时点事实。
当前状态：done；2026-09-20 用户已批准并完成真实本地切换，工具、配置、规范及本轮验收均完成；验证明细见 `verification.md`。

## 背景与核查结论

依据 [原始 ADR](../../decisions/20260920-platform-api-sqlite-to-postgresql-migration.md) 立项。以下来自 2026-09-20 仓库静态核查；ADR 中进程持有 SQLite、磁盘占用等现场描述本次未重新验证，不作为当前运行环境证据。

| 位置 | 已核实事实 | 本专项处理 |
|---|---|---|
| `apps/platform-api/pyproject.toml`；`src/platform_api/core/db/session.py`（相对该 app） | 已有 SQLAlchemy、Alembic、psycopg；`build_engine()` 已接受 PG URL | 复用，不增加数据库抽象或驱动 |
| `apps/platform-api/migrations/versions/20260910_0001_platform_baseline.py` | 当前基线包含 20 张业务表 | 新 PG 空库执行 Alembic；不能把旧 SQLite 直接 stamp 成新基线 |
| `apps/platform-api/tests/test_iam_migration.py` | `PlatformBaselineTest.test_empty_database_upgrade_matches_models_and_round_trips()` 当前使用 SQLite | 保留快速回归，补真实 PG 验证；旧专项 PG 证据不等于本次迁移通过 |
| `apps/platform-api/.env.example`；`apps/platform-api/deploy/docker-compose.example.yml`；`docs/local-deployment-contract.yaml` | 默认 SQLite / 自动建表 | 统一为 PG，关闭自动建表 |
| `deploy/docker-compose.stack.yml`；`deploy/docker-compose.stack.nginx.yml`；`deploy/postgres/init/01-init-shared-databases.sh` | 全栈部署已有控制面独立 PG 配置与建库入口 | 复用，检查迁移先后顺序及已有数据卷行为，不另建一套基础设施 |
| `scripts/local-stack.sh` | `check_postgres()` 检查 Runtime 地址；`validate_stack()` 未校验控制面库；`migrate()` 仅包含 Runtime 迁移 | 补控制面实际连接、独立库与基线校验和 Alembic 启动顺序 |
| `scripts/cleanup_env.sh`（当前工作区未跟踪文件） | 硬编码 Runtime 库、按名称模式删测试库、删除 SQLite 流水及备份 | 纳入改造范围，隔离测试；规划期间不运行该脚本 |

## 目标与边界

- 保留租户、用户、项目、Agent、目录、策略、服务账号、公告及治理数据的标识和关系，确保历史线程授权与模型密钥解密仍有效。
- 正式启动入口使用 PostgreSQL，运行账户不共享 Runtime 凭据，不依赖超级用户。
- 对外 HTTP、鉴权、委托和结果域契约不变；不迁移 Runtime Checkpoints，不调整结果域 schema。
- 不实现双写、CDC、跨库分布式事务或零停机迁移；不删除 SQLite 测试支持，不自动清除旧备份。

## 方案设计

### 1. 专用库和初始化

目标结构：`platform-web → platform-api → PostgreSQL(platform_api)`；平台仍通过 Runtime 网关调用执行层，Runtime 与结果域各自维护持久化。

数据库名允许随环境配置，连接凭据不进入文档或日志。复用 `apps/platform-api/src/platform_api/config.py` 中 `load_settings()` 的配置优先级。校验有效配置启用数据库、使用 `postgresql+psycopg` 且关闭自动建表；连接后核验数据库/角色及 Alembic revision，不以端口存活代替数据库就绪。

复用 `apps/platform-api/migrations/env.py`，对明确确认的专用空库执行 `alembic upgrade head`。实现前核对 Alembic 配置与环境 URL 的优先级，避免迁移目标和应用目标不一致。不重写已使用的基线；确有 schema 修复才新增 revision。

### 2. 源库盘点和数据保全

先盘点源库 schema、逐表行数、外键孤儿、唯一约束冲突、空值、JSON、布尔和时间值。必须确认与当前 20 表模型匹配；若仍有旧表/旧字段，列出映射和舍弃项交人工复核，禁止自动猜测。源库路径取有效配置，不假设一定是 `.data/platform-api.db`。

推荐采用现有 SQLAlchemy 实现一次性数据复制脚本，拟新增 `apps/platform-api/scripts/migrate_sqlite_to_postgres.py`。限定 SQLite 源、PG 目标和当前基线，不做通用迁移框架；不引入 pgloader 改写 Alembic 建好的结构。

- 先停平台写入、等待在途请求结束并停止 Runtime Worker；其他会写关联数据的入口也需冻结。记录停写时间和在途 Run 状态。
- SQLite 使用一致性备份 API 或确认停写和 WAL 状态后的可靠备份，不能对活跃库只复制主文件。备份校验完整性，保留原库和对应密钥。
- 配套备份 Runtime、适用的结果域及密钥/工作区，记录 Redis 队列和外部副作用恢复边界。同一 PG 实例中的独立数据库仍不提供跨库原子 dump。
- 目标库必须已经 Alembic 初始化且业务表为空，导入前禁止 bootstrap 创建管理员；非空目标直接拒绝，不自动覆盖或清表。
- 使用模型类型处理 JSON、布尔、时区和 NULL，按外键依赖顺序分批读取，在目标事务中导入；保留主键、密文和 token 摘要，必要时校正 sequence。异常回滚本次导入，不改变源库。
- `alembic_version` 由目标 Alembic 管理，不从 SQLite 复制。对业务数据执行逐表行数及按主键排序、类型归一后的分批摘要比对，检查外键/唯一性；报告仅记录汇总，不能输出令牌、密文或密钥。
- 默认包含 `audit_logs`、`run_requests`、`refresh_tokens` 和全部服务账号表。若选择清洗/空库重建，先批准逐表策略及会话失效、幂等历史丢失和 Runtime 关联影响；bootstrap 只创建管理员，不能重建全部业务数据。

### 3. 配置和启动入口收敛

修改 `apps/platform-api/.env.example`、服务 Compose 示例及 `docs/local-deployment-contract.yaml`，统一 `PLATFORM_API_PLATFORM_DB_ENABLED=true`、`PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false` 和 PG URL 模板；实际 `.env` 只在批准切换时本地修改，不提交秘密。

在 `scripts/local-stack.sh` 的 `validate_stack()` 增加控制面 preflight；在 `migrate()` / `start()` 确保 API 启动前运行控制面 Alembic，迁移失败即停止启动。迁移是显式运维动作，不放入业务 `lifespan()`；正常启动不能隐式导入/删除历史数据。首次数据导入先于启动 bootstrap，日常启动只检查/升级批准的 schema。

同步 `apps/platform-api/README.md`、`apps/platform-api/docs/handbook/database.md`、`apps/platform-api/docs/handbook/runbook.md`、`docs/quickstart/local-dev.md`、`docs/quickstart/env-matrix.md` 及受影响的部署说明；全栈 Compose 已有 PG，按检查结果做必要修正。

### 4. 清理脚本适配

调整 `scripts/cleanup_env.sh` 的 `clean_postgres()`、`clean_sqlite()`、`clean_backup_files()`：从有效配置解析控制面目标，正确处理密码转义与查询参数；预览显示脱敏目标库、表和预计影响，再显式确认执行。

控制面清理仅限明确授权的 `run_requests`、`audit_logs`，按实际外键核对依赖，禁止直接套用 `TRUNCATE ... CASCADE` 扩大范围。运行中不能清理幂等记录。数据库操作失败必须返回失败，不能吞错后宣称成功。默认保留 SQLite 源库、迁移备份和恢复用测试库；不能把库名前缀匹配当作“孤立库可删除”的证据。保留其他无关清理功能，数据库及备份删除须独立选择并确认。

## 切换与恢复

| 阶段 | 放行条件 | 失败处理 |
|---|---|---|
| 停写前 | 评审、备份位置、责任人、窗口、目标身份和容量已确认 | 不开始迁移 |
| 导入/校验 | 静止源快照、空目标、20 表策略明确，校验完全一致 | 源库不变，保留失败报告；重试使用确认的空目标 |
| 切配置后的受控验收 | 平台连 PG、历史读取和鉴权正确；业务流量仍未放开，测试写入单独记录 | 若只有可舍弃的验收写入，批准后恢复旧配置与停写快照；核对 Runtime 配套状态 |
| 放开真实写入后 | 完整验收通过，记录开放时刻 | 立即停写并保全 PG 新数据，优先修复 PG；反向同步或恢复须另行评估和批准，不能直接指回旧 SQLite |

备份保留期限和删除责任人在评审中确定，验收通过不自动触发清理。恢复演练在隔离环境完成，不对真实库执行 `alembic downgrade` 作为数据回滚。

## 链路影响、风险与依赖

- 回归 `platform-web → platform-api → runtime-service` 和启用时的结果域链路。身份、项目、Agent、thread/run 的标识不得改变；仅更换控制面持久化与配置契约。
- 源库漂移/数据脏值：盘点失败即停止；不得以自动建表掩盖差异。
- 密钥不匹配：保留 master key 与签名/验证配置，验证真实模型凭据兑换及 token 撤销，不在迁移中隐式轮换密钥。
- PG 权限/连接耗尽：使用专用角色，测实际并发和连接上限；不把消除 SQLite 写锁等同无限并发能力。
- 依赖可用 PG、匹配版本备份工具、隔离 Runtime/Redis、可用测试模型和授权测试账号。缺失项记为阻塞，不能记通过。

## 实施计划

1. P0 人工评审、源库盘点及基线确认。
2. P1 PG 初始化与复制工具，在隔离库验证。
3. P2 默认配置、启动入口及清理保护收敛。
4. P3 全链路、负载和恢复演练；经窗口确认后执行本地切换并留证。
