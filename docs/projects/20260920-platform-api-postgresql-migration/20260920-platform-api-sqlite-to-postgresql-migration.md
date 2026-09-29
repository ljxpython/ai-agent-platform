# ADR: 平台控制面 (platform-api) 数据库从 SQLite 迁移至 PostgreSQL 架构决策与实施方案

- **状态**：ACCEPTED（2026-09-20 用户批准专项方案；实施与验收进行中）
- **日期**：2026-09-20
- **影响范围**：`apps/platform-api`, `scripts/local-stack.sh`, `scripts/cleanup_env.sh`, `docs/local-deployment-contract.yaml`
- **关联文档**：`apps/platform-api/docs/handbook/database.md`, `docs/quickstart/local-dev.md`
- **实施专项**：[控制面 PostgreSQL 迁移](../projects/20260920-platform-api-postgresql-migration/README.md)
- **正式规范**：[数据库部署、迁移与本地开发](../guides/database-operations.md)

> 以下为立项时的原始方案记录。已批准专项修正了原文的清洗默认值、CASCADE 清理、跨库备份和“秒级切回”假设：默认全量保留业务数据，禁止自动删除备份，开放新写入后不能直接回指旧 SQLite。执行步骤以实施专项及正式规范为准，不直接执行下方历史示例。


---

## 1. 背景与现状排查 (Context & Current Reality)

在对当前工程的数据库会话、日志与临时文件进行排查与清理过程中，发现平台控制面存在**事实与认知偏离**的架构现状：

### 1.1 现状与排查现象
1. **实际运行现状**：
   - 开发者普遍认为“后端数据都放在了 PostgreSQL 中”。
   - 但经进程文件句柄（`lsof`）与配置现场排查证实：
     - **执行运行时 (`runtime-service`)**：确实连向了本地 PostgreSQL，使用的数据库名为 `graphharbor_acceptance`，里面存放了 LangGraph 执行引擎的会话线程、Checkpoints 和运行事件（`threads`, `runs`, `checkpoints`, `runtime_events`）。
     - **控制面 (`platform-api`)**：实际运行进程仍挂载并锁定了本地 SQLite 数据库文件：`apps/platform-api/.data/platform-api.db`。
2. **产生的问题与风险**：
   - **双重存储裂隙**：平台控制面业务数据（租户 `tenants`、用户 `users`、权限、Agent 注册元数据 `agents`、审计日志 `audit_logs`、运行请求 `run_requests`）保存在本地单文件 SQLite 中，而底层执行引擎数据在 PostgreSQL 中。数据备份、恢复与快照无法实现事务原子性。
   - **磁盘膨胀与历史冗余**：SQLite 缺乏企业级自动化维护机制。之前在迁移历史中留下了多个 400MB+ 的备份文件（如 `original-main.db`、`platform-api.pre-agent-alias-retirement-*.db`），累计吞噬了 **1.6 GB+** 磁盘空间。
   - **高并发与水平扩展受限**：SQLite 采用文件级锁（Database-level write lock）。一旦 `platform-api` 启动多 worker 进程或容器化横向扩展，高频写入（如 `audit_logs` 和 `run_requests`）极易引发 `sqlite3.OperationalError: database is locked`。

---

## 2. 目标架构与设计决策 (Target Architecture & Decision)

### 2.1 架构决策
1. **控制面全面切入 PostgreSQL**：
   - 将 `platform-api` 的元数据与控制面持久化迁移至 PostgreSQL 独立数据库（建议库名：`platform_api` 或 `platform`），彻底废除本地 `apps/platform-api/.data/platform-api.db`。
2. **库级逻辑隔离**：
   - 维持平台控制面与运行时执行层的**物理/逻辑解耦边界**：
     - 控制面数据库：`platform_api`（通过 SQLAlchemy + Alembic 维护 20 张平台业务表）
     - 执行层数据库：`runtime_service` / `graphharbor_acceptance`（由 GraphHarbor / LangGraph 独立管理）
   - 两者共享同一个 PostgreSQL 实例或集群，但独立使用不同的 Database 和连接凭据。
3. **环境与合约统一**：
   - 更新本地启动合约 [`docs/local-deployment-contract.yaml`](../local-deployment-contract.yaml)，使本地开发环境、`scripts/local-stack.sh`、Docker 全栈环境与生产环境保持完全一致的 PostgreSQL 配置标准。

---

## 3. 完整迁移方案 (Step-by-Step Migration Plan)

本迁移方案分为五个阶段：前置准备、数据库初始化、数据离线迁移（可选）、配置切换、以及验证与基线收敛。

### Phase 1: PostgreSQL 专用库准备
在本地或共享 PostgreSQL 中为控制面创建专用数据库与角色：

```bash
# 使用具备创建权限的管理员角色（例如 postgres 或当前本地用户）
psql -U postgres -h localhost -c "CREATE DATABASE platform_api WITH ENCODING 'UTF8';"
```

### Phase 2: 执行 Alembic 结构迁移
`platform-api` 源码内已包含完备的 Alembic 基线迁移脚本（[`20260910_0001_platform_baseline.py`](../../apps/platform-api/migrations/versions/20260910_0001_platform_baseline.py)），直接指向新库即可完成建表：

```bash
cd apps/platform-api
# 临时指定新数据库连接执行迁移
PLATFORM_API_DATABASE_URL="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/platform_api" \
PLATFORM_API_PLATFORM_DB_ENABLED=true \
PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false \
uv run --frozen alembic upgrade head
```

### Phase 3: 数据同步迁移（Data Migration）
若需要保留当前 SQLite 中的基础业务数据（如初始管理员、项目、租户、Agent 配置）：

1. **迁移工具选型**：使用 Python 脚本利用 SQLAlchemy 针对同构模型进行批量复制，或使用轻量开源工具（如 `pgloader`）：
   ```bash
   # 示例：使用 pgloader 单行完成跨库同步
   pgloader apps/platform-api/.data/platform-api.db postgresql://postgres:postgres@127.0.0.1:5432/platform_api
   ```
2. **清洗式迁移（推荐）**：
   - 历史垃圾无需迁移：`audit_logs`（审计流水）和 `run_requests`（执行请求流水）不导入新库，只迁移关键维度主数据：
     - `tenants`
     - `users` / `refresh_tokens`
     - `projects` / `project_members`
     - `agents`
     - `runtime_catalog_*`
     - `project_*_policies`
   - 若不保留历史开发数据，可直接依赖 `platform-api` 启动时的 `bootstrap_admin` 自动初始化全新环境。

### Phase 4: 配置与启动入口切换
修改本地与平台相关配置文件：

1. **`apps/platform-api/.env`**：
   ```dotenv
   PLATFORM_API_PLATFORM_DB_ENABLED=true
   PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false
   PLATFORM_API_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/platform_api
   ```
2. **`scripts/local-stack.sh`**：
   - 检查 `platform-api` 进程启动注入项，确保环境变量直接对齐 PostgreSQL。
3. **`docs/local-deployment-contract.yaml`**：
   - 将 `platform-api` 的 `minimum_required_env` 从 `sqlite+pysqlite:///./.data/platform-api.db` 更新为 PostgreSQL 连接串标准。

### Phase 5: 验证与验收
1. 启动 `local-stack` 服务集群：
   ```bash
   bash scripts/local-stack.sh restart
   ```
2. 检查 `platform-api` 进程连接情况：
   ```bash
   # 验证平台进程打开的网络句柄连接到了 5432
   lsof -p <platform-api-pid> -i :5432
   ```
3. 浏览器登录并进行端到端测试，验证项目、Agent 管理及对话功能均能正常持久化至 PostgreSQL。

---

## 4. 清理脚本 (`scripts/cleanup_env.sh`) 改造设计

当控制面迁移至 PostgreSQL 后，现有的环境清理脚本 [`scripts/cleanup_env.sh`](../../scripts/cleanup_env.sh) 必须同步进行升级适配：

### 4.1 现有脚本行为
- 目前脚本将 `apps/platform-api/.data/platform-api.db` 作为清理目标，通过 `sqlite3` 执行 `DELETE FROM run_requests; DELETE FROM audit_logs; VACUUM;`。
- 同时删除了 `.data/` 下的历史备份文件。

### 4.2 迁移后需要的脚本改动
1. **增加控制面 PostgreSQL 库的清理逻辑**：
   - 在 `clean_postgres()` 函数中，不仅清理 `graphharbor_acceptance`（运行时数据），同时支持清理 `platform_api` 中的流水表：
     ```bash
     # 清空控制面的会话请求和高频审计流水，但保留租户/用户/项目/配置主数据
     psql -U "$PG_USER" -h "$PG_HOST" -p "$PG_PORT" -d platform_api -c \
         "TRUNCATE TABLE run_requests, audit_logs CASCADE;"
     ```
2. **SQLite 逻辑降级为历史兼容 / 弃用标记**：
   - 检查 `apps/platform-api/.data/platform-api.db`，如果存在则提示已弃用，或作为可选清理项直接删除整个废弃的 `.data/` 目录。
3. **统一数据库连接参数**：
   - 脚本顶部支持从 `apps/platform-api/.env` 动态读取 `PLATFORM_API_DATABASE_URL`，自动解析目标数据库名并执行对应库表的精准清理，避免硬编码库名。

---

## 5. 风险与回滚方案 (Risks & Rollback)

| 潜在风险 | 影响程度 | 应对与回滚策略 |
| :--- | :--- | :--- |
| **本地开发环境缺少 PostgreSQL 实例** | 中 | 本地启动脚本提供 preflight 校验；若 PG 未运行，明确报错提示，或支持一键 docker-compose 拉起基础设施。 |
| **迁移后数据丢失或主键冲突** | 低 | 迁移前完整备份 SQLite 文件（`cp platform-api.db platform-api.db.bak`）。出现问题时切回 SQLite 配置即可秒级恢复。 |
| **测试隔离库堆积** | 低 | 保持并优化 `cleanup_env.sh` 中的孤立测试库自动 DROP 机制，防止临时数据库占满磁盘。 |

---

## 6. 评审结论与后续行动
- [ ] 架构方案评审确认
- [ ] 在本地创建 `platform_api` 测试库并跑通 Alembic 迁移
- [ ] 更新 `scripts/cleanup_env.sh` 适配 PostgreSQL 控制面清理
- [ ] 更新部署合约与开发文档，全线切换
