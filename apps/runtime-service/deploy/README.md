# Runtime-Service Container Deployment

文档类型：`Planned Delivery Guide`

本文描述的是 `apps/runtime-service` 的单应用镜像交付面。API、Worker、PostgreSQL 和 Redis
作为四个独立部署单元运行；对应文件资产和 R6 Durable Core 已有验证证据，生产切流仍需按
R6 hard gate 单独验收。

## 1. 目标

让用户在不理解整仓控制面细节的情况下，单独把 `runtime-service` 跑起来。

目标拓扑：

- `runtime-service-api`
- `runtime-service-worker`
- `redis`
- `postgres`

补充说明：

- 单应用 `runtime-service` compose 中的 Postgres 默认只在容器网络内可达
- 默认不绑定宿主机 `5432`
- 这样可以避免和本机已有 PostgreSQL 冲突

## 2. 镜像构建原则

规划已收敛为：

- 使用仓库内受管 Dockerfile
- 路径：`apps/runtime-service/deploy/Dockerfile`
- Python 基线：`3.13`
- 当前 GraphHarbor 基座镜像：固定 digest 的 `python:3.13-slim`，GraphHarbor wheel 在镜像内非 editable 安装。
- 用户应可直接使用 `docker compose build` / `docker compose up -d`
- 不要求用户先安装 LangGraph CLI；镜像使用 `graphharbor serve/worker/migrate`。
- 当前验证结论：
- GraphHarbor API、独立 Worker 和 migration job 使用同一 Runtime 镜像。
- Workspace 通过 `RUNTIME_WORKSPACE_MAX_FILE_BYTES`、`RUNTIME_WORKSPACE_MAX_FILES` 和
  `RUNTIME_WORKSPACE_MAX_TOTAL_BYTES` 限制单文件、Thread 文件数量和 Thread 总字节数；过期清理使用
  `scripts/r6_workspace_cleanup.py`，默认 dry-run，只有部署任务
  从 Thread 持久化事实源提供活跃 `tenant/project/thread` 列表并显式传入 `--apply` 时才会删除。
  - `langgraph dev` 仅是 local_dev/in-memory 对照，不能替代本 compose 的 PostgreSQL/Redis Durable Run 验证。

说明：

- Dockerfile 可以最初参考 `langgraph dockerfile` 的生成结果
- 但最终交付物应作为仓库内一等文件维护

## 3. 配置归属

### 3.1 模型配置

容器部署的真实配置唯一归：

- `apps/runtime-service/deploy/.env.runtime-service`

宿主机 `apps/runtime-service/.env` 供原生开发栈及本地 Python 测试读取，`.dockerignore` 会排除它，不能作为
容器部署来源。`runtime_service/conf/settings.local.yaml` 当前也不参与 Runtime 配置加载。
模型凭据必须通过部署 env file 或 secret store 注入，不能写入镜像。

### 3.2 当前 R6 配置

R6 Compose 负责 API、独立 Worker、PostgreSQL 和 Redis 的隔离启动；Runtime 模型凭据从
部署环境注入，Durable 测试地址和 Assistant ID 由测试命令显式提供。生产环境还必须配置
`GRAPHHARBOR_RUNTIME_CONTEXT_SECRET`、`GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER` 和
`GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE`，用于 API 到 Worker 的内部签名 envelope；它们不
等同于 Platform 外部 delegation JWT 配置。R6 Durable Core 已通过真实 Agent Server Durable
验证；生产发布、回滚和外部依赖仍需单独通过对应 hard gate，不能把本文件当作无条件生产发布声明。

### 3.3 运行时 config 文件

默认容器化 config 源：

- `langgraph.json`

GraphHarbor 直接读取该文件中的 `auth`、`http.app` 和 `graphs` 配置。

### 3.4 配置检查

在 `apps/runtime-service` 目录执行：

```bash
uv run python scripts/validate_runtime_config.py \
  --env-file deploy/.env.runtime-service
```

该检查只输出 `present/empty` 和错误字段名，不输出密钥内容。API、Worker 和测试客户端必须使用
同一组 delegation/context secret；缺少 `deploy/.env.runtime-service`、任一必需 secret 或模型凭据时
应立即失败，不允许依赖 Compose 默认空值启动。

## 4. Graph 范围

当前规划默认：

- 跟随根级 `langgraph.json` 注册的 graph 集

当前已知风险：

- 至少部分 graph 存在 blocking-IO 敏感性，后续实现时必须通过真实容器 smoke 验证

## 5. 未来交付物

计划中的文件：

- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/.env.runtime-service.example`

当前已补齐到：

- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/.env.runtime-service.example`
- `apps/runtime-service/.dockerignore`

当前验证状态：

- GraphHarbor `0.13.0.post20` 已从 PyPI 安装，Runtime lock 和 Docker 镜像使用同一正式版本
- PostgreSQL / Redis：已通过健康检查和 migration
- API / Worker：使用同一 Runtime 镜像、不同启动角色，已连接独立 PostgreSQL/Redis；`/ready`
  的 graphs、postgres、schema、redis、queue 检查通过
- Durable Core：真实 Thread/Run/Checkpoint、Worker replacement、SSE replay、failure/timeout
  和 Workspace 基础链路已有验收证据；生产发布回滚和外部依赖仍未闭合

当前验证发现：

- `langgraph dev` 在无 license 条件下仍能正常提供：
  - `/info`
  - `/internal/capabilities/models`
  - `/internal/capabilities/tools`
- 该结果只覆盖本地开发和 in-memory 持久化，不覆盖 Durable Run；Durable Run 以 GraphHarbor
  API + Worker + PostgreSQL + Redis 验收为准

更新结论：

- 当前交付使用 GraphHarbor 原生 `migrate`、`serve` 和独立 `worker` 路线。
- 不需要 `LANGGRAPH_CLOUD_LICENSE_KEY`；生产仍必须注入 Platform Delegation JWT 所需的受管密钥。
- GraphHarbor 使用 PyPI 上锁定的正式版本；Compose build 不依赖开发机源码路径或本地 wheel。

## 6. 更新与重建

更新 runbook 不在本页展开，统一收敛到：

- [`docs/runbooks/container-update-runbook.md`](../../../docs/runbooks/container-update-runbook.md)

核心原则已经确定：

- 代码 / Dockerfile 变更：
  - rebuild + recreate
- 仅 env/config 变更：
  - recreate

## 8. 使用宿主 PostgreSQL/Redis

本地账号可以用于 Runtime，但必须使用专用数据库、专用用户和独立 Redis DB/namespace，并在
启动前完成真实连接、权限和 migration 预检。最快的方式是 API、Worker 和 migration 都在宿主
进程中运行，显式设置同一组 `DATABASE_URI`、`REDIS_URI`，不构建 Docker。

当前 Compose 文件不是宿主基础设施模式：它声明并启动自己的 `postgres`、`redis`，API、Worker
和 `migrate` 通过 `depends_on` 依赖这两个服务，并在 `environment` 中合成容器网络 URI。因此：

- 不能只把 `RUNTIME_POSTGRES_HOST` 或 `RUNTIME_REDIS_HOST` 改成宿主地址后继续使用当前文件；
- 容器访问 Docker Desktop 宿主资源时使用 `host.docker.internal`，不能使用容器内的 `localhost`；
- 当前 compose 的 Postgres URI 使用固定容器端口 `5432`，`RUNTIME_POSTGRES_PORT` 不能单独证明
  已完成宿主端口切换；
- Docker API/Worker + 宿主 PG/Redis 需要另行增加 host-infra Compose 文件或 profile，移除本地
  PG/Redis 服务和对应依赖后才能作为正式模式记录。

宿主资源的准入条件：PostgreSQL 版本、extension 和 migration 兼容；测试账号具有所需建表/迁移
权限；Redis DB 或 prefix 不与其他验收批次重叠；数据目标不是业务或生产库。验收清理不能执行
无范围 `DROP`、volume 删除或宿主服务终止。

### 8.1 host-infra 容器模式

容器 API/Worker + 宿主 PostgreSQL/Redis 使用独立编排文件：

- [`docker-compose.runtime-service.host-infra.yml`](./docker-compose.runtime-service.host-infra.yml)
- [`.env.runtime-service.host-infra.example`](./.env.runtime-service.host-infra.example)

该文件只声明 `migrate`、`runtime-service` 和 `worker`，不声明 PostgreSQL、Redis、对应 volume
服务依赖；API/Worker 通过 `depends_on` 等待迁移成功。先完成 migration，再启动 API/Worker；三者从同一份 host-infra env file 接收同一
组 `DATABASE_URI` / `REDIS_URI`：

```bash
cp deploy/.env.runtime-service.host-infra.example deploy/.env.runtime-service.host-infra
uv run python scripts/validate_runtime_config.py \
  --env-file deploy/.env.runtime-service.host-infra
docker compose --env-file deploy/.env.runtime-service.host-infra \
  -f deploy/docker-compose.runtime-service.host-infra.yml run --rm migrate
docker compose --env-file deploy/.env.runtime-service.host-infra \
  -f deploy/docker-compose.runtime-service.host-infra.yml up -d runtime-service worker
```

Docker Desktop 宿主资源使用 `host.docker.internal`；Linux 或远程基础设施使用可路由的实际地址。
不要把 `localhost` 写进容器内的 URI，也不要把本地 Compose 文件的 `postgres` / `redis` 服务与
host-infra 文件混用。实际 env 文件已加入 Git 忽略，模板中的密码只是占位符。

## 9. GraphHarbor 发布与 Runtime 回滚

GraphHarbor 的 `graphharbor` 和 `graphharbor-runtime` 必须锁步使用同一版本。发布可以使用
`~/.my_best/.env` 中的 `UV_PUBLISH_TOKEN`，但只允许安全加载到发布终端并通过 `uv publish`
使用，日志和文档不记录 token；`UV_TEST_PUBLISH_TOKEN` 仅用于测试 index。

GraphHarbor 仓库的 Trusted Publishing/OIDC workflow 与本地 token 是两条互斥路径。发布前要通过
版本脚本、`uv.lock --check`、lint、完整测试、build、wheel import 和目标 index 可见性检查；
先发布 `graphharbor-runtime`，再发布 `graphharbor`，两个包均可隔离安装后才能更新 Runtime
lockfile 和镜像。PyPI 版本不可覆盖，单包成功时另一包失败必须递增版本，不能重传同版本。

Runtime 回滚使用已验证的旧 API/Worker 镜像或虚拟环境，不重新发布旧 wheel；保留 PostgreSQL、
Redis 和 Workspace 数据，确认旧版本 lockfile 与 migration 兼容后再切换。回滚后重新检查
`/ready`、最小 Run、Checkpoint 和 SSE replay。GraphHarbor 不负责 Platform 灰度、route ownership
或 legacy upstream 回滚。

环境问题和一次性验收门禁统一见：

- [非 Docker 部署与排障](../../../docs/quickstart/deployment-guide.md)
- [`docs/runbooks/container-update-runbook.md`](../../../docs/runbooks/container-update-runbook.md)


## Runtime 应用表迁移（2026-09-19）

服务内两个 Compose 的 `migrate` job 依次执行 `graphharbor migrate upgrade` 和
`python -m runtime_service.db upgrade`；任一失败，API/Worker 不应启动。
应用迁移位于 `src/runtime_service/db/migrations/`，版本表为 `runtime_app_alembic_version`，
不修改 GraphHarbor 迁移链。Alembic 是直接依赖，业务查询继续使用 psycopg。

宿主部署在已配置 `DATABASE_URI` 的 Runtime 环境执行：

```bash
uv run graphharbor migrate upgrade
uv run python -m runtime_service.db upgrade
```

应用表包括 `dear_memory`、`dear_external_tasks`、`runtime_message_inbox`、`dear_skills`。
已有保留表在基线迁移时检查列类型、主键和必要唯一约束；不符则回滚并失败，不自动修补未知结构。
迁移使用事务和 advisory lock；重复执行不会重复建表，也不修改业务数据。
旧 `dear_skill_versions`、`dear_skill_bindings` 不导入、不双写、不自动删除；需要的技能重新上传。
旧散落 SQL 已退出代码，三个历史初始化入口统一委托应用迁移，不在 HTTP/Agent 请求中建表。

切换前排空旧程序运行，执行迁移后启动两端新后端。旧前端的技能治理请求不再受支持，
前端按 [交接文档](../../../docs/projects/20260919-skills-page-improvement/07-frontend-handoff.md) 一同切换。
保留 Workspace 卷及其快照目录；恢复缺失或损坏快照时明确失败，不读取当前技能代替。
不支持破坏性 downgrade 或旧技能模型无损回切。生产发布尚未执行。
根目录 `scripts/local-stack.sh` 通过 `python -m runtime_service.messaging` 调用同一应用 `upgrade()`；根级 Compose 中相同命令也会执行应用迁移。独立手工启动仍须先执行上述迁移。

对话工具仍遵守项目工具策略；若配置了显式工具白名单，部署后刷新工具目录并按原审批方式授权 `upload_skill/update_skill/set_skill_enabled/delete_skill`。不自动扩大用户权限。
