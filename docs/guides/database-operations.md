# 数据库部署、迁移与本地开发规范

文档类型：当前生效的运维规范。适用于控制面 PostgreSQL；Runtime 使用自己的迁移工具，不能让控制面 Alembic 接管其表。实施证据和剩余验收项见[迁移专项](../projects/20260920-platform-api-postgresql-migration/README.md)。

首次非 Docker 新机部署从[完整手册](../quickstart/deployment-guide.md)开始；本页重点是数据库职责和运维。

## 1. 存储边界

| 服务 | 推荐数据库 / 角色 | 建表与升级 |
|---|---|---|
| platform-api | `platform_api` / `platform_api` | SQLAlchemy 模型 + Alembic；关闭自动建表 |
| runtime-service | 通用模板 `runtime_service` / `runtime_service`；个人交接可另指定独立库/角色 | GraphHarbor / Runtime 自己的迁移 |

可以共享 PG 实例，必须分库和使用独立非超级用户角色。控制面角色不授予其他库业务表访问权限。开发、测试、生产也必须隔离；测试不能指向业务库。库名以各环境配置为准，脚本不凭库名前缀推断“可以删除”。

两个独立数据库的 dump 不是跨库原子快照。需要一致备份时冻结关联写入、等待在途请求结束并停止 Worker；数据库备份不包含 Redis 队列、工作区或外部工具副作用。

## 2. 新服务器首次部署：先创建库，再创建表

### 2.1 已有脚本及职责

| 入口（相对仓库根目录） | 做什么 | 不做什么 |
|---|---|---|
| `deploy/postgres/init/01-init-shared-databases.sh` | 创建缺失的 Runtime 和 Platform API 数据库及角色；`--platform-only` 仅建控制面库 | 不升级表、不迁数据、不重置已有角色密码或已有库 owner |
| `apps/platform-api/scripts/database.py preflight` | 校验有效 PG 配置、实际连接、已知 revision；允许新空库/待升级版本 | 不写库 |
| `apps/platform-api/scripts/database.py upgrade` | preflight 后执行 Alembic 到 head，再核验版本 | 不创建 database、不自动导入旧数据、不 stamp 未登记的库 |
| `apps/platform-api/scripts/database.py check` | 要求实际目标已在 Alembic head | 不迁移 |
| `apps/platform-api/scripts/migrate_sqlite_to_postgres.py` | 当前 20 表 SQLite 基线到空 PG 业务表的受控一次性复制 | 不兼容任意旧 schema，不双写，不清洗历史 |

脚本不会替你安装 PostgreSQL。先安装项目支持的 PG 版本并配置监听、网络访问和认证；管理凭据仅用于建库，应用只配置专用业务角色。所有命令须在已核对的环境执行。

### 2.2 全栈 Docker Compose 新数据卷

1. 从 `deploy/.env.stack.example` 创建受保护的部署配置；修改超级用户、各服务数据库密码、JWT/委托/模型 master key 和管理员设置，禁止把示例密码用于服务器。
2. 在仓库根目录启动基础设施（示例使用无 Nginx 版本；Nginx 版换对应文件）：

   ```bash
   docker compose --env-file "deploy/.env.stack" -f "deploy/docker-compose.stack.yml" up -d postgres redis
   ```

3. **只有空 PG 数据目录首次初始化时**，官方 PG 镜像会自动执行挂载的 `01-init-shared-databases.sh`，创建两个库与角色。PG healthy 不代表控制面表已经存在。
4. 构建/启动平台服务时，Compose 命令先执行 `python scripts/database.py upgrade`，成功才启动 uvicorn；`PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false`。升级错误会阻止 API 启动。新库部署与旧库迁移使用不同流程，旧库必须先走第 3 节。
   Runtime 容器同样先运行 `graphharbor migrate upgrade`、`python -m runtime_service.messaging` 再启动服务，连接变量为 `DATABASE_URI`；健康探针访问 `/ok`。模型密文的 `PLATFORM_API_MODEL_CONFIG_MASTER_KEY` 必须跨重启/恢复保持一致。
5. 用容器内 `python scripts/database.py check` 核验 head；再验证登录、项目、Agent、运行和审计。检查 ready JSON 中 `status=ready` 且 `database_ready=true`，HTTP 200 不是唯一依据。

同一数据库首次迁移或版本更新只允许一个迁移执行者。多副本部署在扩容前单独执行 migration job，避免多个容器同时 upgrade。首次管理员初始化使用受控引导窗口；正式生产模式要求关闭 bootstrap，不能为绕过检查长期使用 local 模式。

### 2.3 已有数据卷或宿主机 PostgreSQL

已有 PG 数据卷不会重跑 `docker-entrypoint-initdb.d`。新增控制面库时，可以在确认部署配置已注入 postgres 容器后执行：

```bash
docker compose --env-file "deploy/.env.stack" -f "deploy/docker-compose.stack.yml" exec postgres sh /docker-entrypoint-initdb.d/01-init-shared-databases.sh --platform-only
```

宿主机部署也复用该脚本。在安全的会话中配置 `PGHOST`、`PGPORT`、`PGUSER`（管理员）、`PGPASSFILE`，以及 `PLATFORM_API_POSTGRES_DB`、`PLATFORM_API_POSTGRES_USER`、`PLATFORM_API_POSTGRES_PASSWORD` 后，在仓库根目录执行：

```bash
sh "deploy/postgres/init/01-init-shared-databases.sh" --platform-only
```

容器脚本优先使用 `POSTGRES_USER`，宿主机未设置时使用 `PGUSER`；避免残留 `POSTGRES_USER` 指向错误管理员。密码通过受保护配置注入，含特殊字符的连接 URL 要按 URI 编码。重复执行仅补缺失角色/库，不更新已有密码；已有库 owner、编码、权限不符时先人工核查，不自动修补。

建库之后，在 `apps/platform-api/.env` 配置：

```dotenv
PLATFORM_API_PLATFORM_DB_ENABLED=true
PLATFORM_API_PLATFORM_DB_AUTO_CREATE=false
PLATFORM_API_DATABASE_URL=postgresql+psycopg://platform_api:<URI编码后的密码>@127.0.0.1:5432/platform_api
```

将示例中的地址/密码替换为真实值；容器内 PG 主机通常为 `postgres`，不是容器自身的 `127.0.0.1`。在 `apps/platform-api` 执行：

```bash
uv sync --frozen
uv run --frozen python scripts/database.py upgrade
uv run --frozen python scripts/database.py check
```

系统环境变量优先于 app 的 `.env`。脚本与应用都通过 `load_settings()` 读取配置。操作前检查生效目标，不能只看文件内容。

## 3. 未来数据迁移规范

### 3.1 schema 变更

1. 修改模型后新增 Alembic revision；已投入使用的基线/历史 revision 不重写。
2. 评审约束、索引、默认值、已有数据回填、锁表时间、应用版本兼容和恢复办法；涉及删除/权限/生产须人工批准。
3. 隔离库先验证从当前版本升级、重复升级及 metadata 一致性；有数据的升级用代表性快照测试，空库通过不能替代。
4. 停写/备份后，由单一迁移执行者执行 upgrade，再启动批准的应用版本并验收；迁移失败不能跳过继续发布。
5. 不使用 `create_all` 修补业务库，不以 `alembic stamp` 冒充迁移。没有证明可逆时，不在真实库直接 downgrade。

### 3.2 SQLite → PostgreSQL（本专项）

当前工具只支持当前 20 张业务表及字段集；额外表、缺失字段、无效布尔或不兼容值均应拒绝并复核。目标必须是 Alembic 初始化的空业务库，且尚未运行 bootstrap。保留全部业务数据、主键、密文和 token 摘要，目标 `alembic_version` 不从 SQLite 复制。当前主键为 UUID，无需重置自增序列；未来新增自增列须同步扩展迁移与测试。

操作顺序：

1. 明确源文件、目标库、执行人、停写窗口及备份保留期。确认旧 SQLite 的无时区时间值确实表示 UTC，否则先制定时间映射，不能直接使用下面的 UTC 参数。
2. 停止平台写入口、其他写入方与 Runtime Worker，等待在途任务结束。保存对应密钥、关联库快照、队列状态和必要工作区。
3. 按第 2 节创建目标空 PG 并 upgrade；使用进程级目标配置进行迁移，暂不覆盖现有服务 `.env`。备份目录需事先创建并限制访问。
4. 在 `apps/platform-api` 执行以下命令；`PLATFORM_API_DATABASE_URL` 应从安全环境注入，指向新库，数据库开关开启且自动建表关闭：

   ```bash
   uv run --frozen python scripts/migrate_sqlite_to_postgres.py \
     --source ".data/platform-api.db" \
     --backup ".data/backups/pre-postgresql-20260920.db" \
     --confirm-database platform_api --writers-stopped --assume-naive-utc
   ```

   日期/库名按实际填写。`--writers-stopped` 是操作者对停写事实的确认，工具不会替你停止远端写入方。SQLite backup API 覆盖 WAL，备份以 0600 独占创建，已有备份绝不覆盖。工具从备份读取；PG 导入及数据比对位于同一事务，失败回滚，源库和备份保留。
5. 核对工具报告中所有表的行数、归一 SHA-256、约束和历史关联。缺失审计/请求数据不可静默忽略；明确要求清洗时需另行批准并实施数据策略，当前工具不提供自动清洗参数。
6. 修改本地实际配置，先进行受控验收，再开放真实写入，分别记录时刻。不要删除旧源库/备份。

### 3.3 PostgreSQL 换服务器 / 数据恢复

在确认停写窗口，用与服务端兼容的客户端分别执行 `pg_dump --format=custom`，并保存 revision、行数/摘要、密钥及关联服务快照。恢复到**新空库**，使用 `pg_restore --exit-on-error --no-owner --no-acl` 并核对目标 owner/权限，不能覆盖当前运行库。

恢复后先比对数据、检查 head 与历史读取；核实 Redis 队列、lease、待执行任务和外部副作用，再开放 Worker 和写入口。迁移前无真实新写入时，可按批准方案恢复旧配置和一致快照；**PG 已接收新写入后不得直接切回旧 SQLite**。应停写、保全新 PG，优先修复/恢复 PG；反向同步须单独评审。

跨服务数据库、密钥、工作区及队列需要共同制定恢复点与恢复时间目标。不同 PG 主版本迁移先验证扩展、排序规则、编码和 SQL 行为，不能只改连接 URL。

## 4. 本地开发明确使用本地 PG

- 正式本地开发与联调连接本机 `127.0.0.1:5432` 的独立控制面库 `platform_api`；不能借用 Runtime 的 `graphharbor_acceptance`，不能连共享生产库。
- 本机安装 PG 或启动只绑定回环地址的 PG 容器均可；本地与服务器都应实际使用 SCRAM 密码认证，不能仅在 URL 中填密码而保留 trust。当前本机已完成 socket/IPv4/IPv6 收紧和正确/缺失/错误密码测试，见[认证记录](../projects/20260920-local-postgres-password/README.md)。当前用户 `.pgpass` 权限 600，仅用于客户端提供凭据；新客户端仍需配置。用第 2.3 节创建控制面库，再设置 app 自己的 `.env`。根目录 `.env` 不作为统一开发配置源。
- `.env.example` 默认 PG、关闭自动建表。已有 SQLite 开发数据先走第 3.2 节；复制新示例覆盖旧 `.env` 不是数据迁移。
- 在仓库根目录只通过本地栈入口启停：

  ```bash
  bash "scripts/local-stack.sh" doctor
  bash "scripts/local-stack.sh" start
  bash "scripts/local-stack.sh" status
  ```

  `doctor` 对控制面执行 preflight；`start` 在 API 前执行 Alembic，失败则阻断启动；`restart-one platform-api` 同样先迁移。preflight 允许空库/已知旧版本，最终 head 校验用 `database.py check`。
- SQLite 仅保留作隔离单元测试和迁移源；真实 PG 集成测试必须指定空的专用库，不能把 SQLite 单测通过称作 PG 验收。

## 5. 清理、备份和审计

`scripts/cleanup_env.sh` 默认仅清理日志/缓存；SQLite 源库、所有备份、Runtime 库和测试数据库不自动删除。若确需清理本地控制面流水，先预览：

```bash
bash "scripts/cleanup_env.sh" --platform-ledgers --dry-run
```

停写且确认目标后才执行：

```bash
bash "scripts/cleanup_env.sh" --platform-ledgers --writers-stopped --confirm-database platform_api
```

流水清理仅支持 local/dev，限制为 `run_requests` 和 `audit_logs`，使用 RESTRICT 而非 CASCADE，失败立即返回错误。参数确认不能代替真实停写；清除请求记录会丢失幂等历史。生产审计保留/销毁另行审批，不使用此开发脚本。

备份保留期、责任人和恢复演练记录随发布单确定；未验证恢复、尚在回退窗口或无明确保留期的备份不得删除。验收报告记录命令、版本、脱敏目标、计数及摘要，不提交数据库副本、连接密码、token 或 master key。

### 本地项目清理

先按本规范备份控制面数据库，再从项目接口取得需要保留的活动项目 UUID。以下为独立模式，不清文件或流水，不允许与其他清理模式组合：

```bash
bash "scripts/cleanup_env.sh" --keep-project "$PROJECT_ID" --dry-run
bash "scripts/cleanup_env.sh" --keep-project "$PROJECT_ID" --confirm-database platform_api --yes
```

仅支持 local/dev；按 UUID 而非名称保留项目，不存在或非活动项目会拒绝执行。单事务软删除其他未删除项目，设置删除时间，重复执行无新增影响。写入时锁定项目表，5 秒锁超时；清理后新建的项目仍会正常显示。操作者应先结束目标项目的运行任务：本命令不会取消 Runtime 任务。

软删除让项目不再出现在列表中，并由现有鉴权拒绝访问；不会释放历史数据占用。项目 Agent、成员、策略、Runtime 会话/检查点、请求及审计保留。操作计数由命令输出，需自行保存到私有运维记录；直接数据库维护不会逐条产生项目 API 删除审计。物理清理需另定跨库关联范围、保留期及恢复方案，不能直接 CASCADE 或清空整个 Runtime 库。

默认文件清理保留 Git 跟踪的测试报告，只删除报告目录中的未跟踪文件。`--include-runtime` 仅指旧 `apps/runtime-service/.runtime/workspaces` 和 `showcase` 目录，执行要求 `--writers-stopped`；它不解析或清理 `GRAPHHARBOR_WORKSPACE_ROOT` 指定的外部工作区。

### Graph 和 Agent 的范围

Graph 是全局 Runtime 目录，项目头用于权限上下文，不会复制 Graph。Agent 是按项目保存的配置实例，`(project_id, graph_id)` 唯一。查询 Agent 列表时，会为本项目已启用的 Graph 自动补齐默认 Agent；未配置项目 Graph 策略时默认启用。因此不同项目可能同名同描述，但 Agent UUID 和配置独立。要改变默认自动生成/默认启用行为，需另行调整产品及授权契约。

### 历史数据清理

`--history` 必须是脚本首参数，是独立模式，不顺带删文件。默认只预览；支持以下选择，可组合：

| 参数 | 范围 |
| --- | --- |
| `--platform` | 仅过期/已撤销 refresh token；全部 run_requests、audit_logs |
| `--runtime` | 全部会话、运行（包括 interrupted）、检查点、事件、消息收件箱、外部任务历史、会话技能绑定 |
| `--drop-test-database NAME` | 指定完整迁移测试库名，可重复；不接受通配符，不会按前缀扫描删除 |

```bash
bash "scripts/cleanup_env.sh" --history --platform --runtime --dry-run
bash "scripts/local-stack.sh" stop
bash "scripts/cleanup_env.sh" --history --platform --runtime \
  --execute --writers-stopped \
  --confirm-database platform_api --confirm-database graphharbor_acceptance \
  --pg-bin "$PG_BIN"
bash "scripts/local-stack.sh" start
```

`PG_BIN` 指向与目标服务端兼容的 PostgreSQL 客户端目录；未指定时使用 PATH 中 pg_dump 所在目录。所有目标先完成 `pg_dump -Fc` 和 archive 目录检查后才修改数据。私有备份在 `apps/platform-api/.data/backups/*-history-cleanup/`，manifest 记录每个数据库的完成状态。备份失败不清理；各数据库各自事务，跨库不保证原子性，部分失败时按 manifest 定位，不盲目重复或覆盖备份。

删除测试库还需通过环境变量 `CLEANUP_ADMIN_DATABASE_URL` 提供本地 `postgres` 维护库连接。每个目标都要同时传入 `--drop-test-database NAME` 和 `--confirm-database NAME`。仅接受完整的 `platform_migration_test_...` 名称，保护当前两个业务库及系统库；目标不存在时报告 already_absent，不强制断开连接，不用 DROP FORCE。不要将带密码的连接字符串写到命令或文档里。

本入口只允许 local/dev 和本机连接；执行需停写声明，另检查数据库活动连接、运行中任务及启用的 cron。`--runtime` 会删除中断任务的恢复点，不能继续恢复旧会话；外部任务 unknown 的历史亦被清除，不会撤销已发出的外部请求。全局目录、项目/Agent 配置、有效令牌、长期记忆和技能定义/版本、迁移版本表均保留。

数据库历史入口不清 Redis、磁盘工作区或其他测试命名空间。需要同时清理流缓存时，应停写、按当前 Runtime 的明确命名空间导出，再删除已备份的历史键；禁止 FLUSHDB。2026-09-20 本次维护另外完成了当前 Runtime 流缓存导出及清理，见专项记录。
