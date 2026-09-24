# interaction-data-service 退役 - 验证计划和记录

## 验证计划

### 前置与数据安全

- [x] 本机旧容器已停止、8081 无监听；用户确认本次仅覆盖本机，未来 Docker 部署自行管理。
- [x] 本机 Docker 旧库、角色、两表/索引及独占卷名称与归属已核对；共享卷不在清理范围。
- [x] 本机 Docker 旧库已备份并在隔离临时库恢复、读取一条旧文档；专属附件卷为空。
- [x] 本服务没有 Alembic 迁移目录/版本表；Platform API 和 Runtime 的迁移表未修改。

### 配置与静态检查

- [x] 两份 `docker compose ... config --quiet` 能解析；服务列表不含 `interaction-data-service`，Runtime 环境不含旧连接变量。
- [x] Postgres 初始化脚本 `sh -n` 通过；全新临时 Docker 卷实际启动后只创建 Runtime 与 Platform API 库/角色，未创建旧库/角色。
- [x] `apps/interaction-data-service/` 全目录消失，包括建表/补列代码和本机私有文件；当前文档、架构图、根 README、AGENTS、部署示例与 `docs/FEATURES.md` 不再把旧服务写为现行能力。
- [x] `git diff --check` 通过；历史项目/发布记录保留。

### 单元与集成

- [x] 三应用源码无旧服务调用；Platform API 退役路由与网关契约、成果双服务 HTTP、前端成果页与路由单测、typecheck/build、Runtime 工作区/成果定向测试通过；Runtime 另有 1 项跳过。
- [x] 本机四进程栈运行，Runtime `/ready`、Platform API `/_system/health` 与 Web 200 通过；浏览器聊天用例已完成真实模型运行。
- [x] 全新临时 Postgres 实例只初始化现行两库；两份 Compose 解析后的服务列表没有旧容器构建入口。两种 Compose 未完整构建/启动，留给未来部署时检查。

### 端到端与回退

- [x] 经 Web 创建/进入项目、发起聊天，真实模型回复且刷新后历史可见；桌面浏览器用例还覆盖审批恢复与分支编辑。
- [x] Dear Agent 真实生成并发布 Markdown，经 Web 成果页预览与下载，核对 `platform-web -> platform-api -> runtime-service` 全链路。
- [x] 本机 8081 无监听、宿主 PG 与 Docker 旧库/角色均不存在、Platform API 库无旧业务表。
- [x] 退役前版本/镜像、原配置和本机 Docker 已验证备份可定位。

## Phase 验证记录

### Task 2.1 验证（2026-09-24）

- `docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack.example config --quiet` 与 Nginx 版本同命令均通过；`config --services` 分别仅有 `postgres`、`redis`、`runtime-service`、`platform-api`、`platform-web`（Nginx 版另有 `nginx`）。
- `sh -n deploy/postgres/init/01-init-shared-databases.sh` 通过；旧服务目录已消失。
- 在全新临时 Docker 卷启动 `pgvector/pgvector:pg16` 并运行当前初始化脚本，实际库为 `postgres`、`platform_api`、`runtime_service`，角色仅有后两者；临时容器与卷已清理。未构建整套 Compose 镜像。

### Task 2.2 验证（2026-09-24）

- 对非历史现行文档、部署脚本及三应用源码搜索 `interaction-data-service`、`INTERACTION_DATA_SERVICE`、8081 和旧表名，无现行引用。状态记录/ADR 保留退役对象名称。
- 补充审计发现部署配置仍有四项无人读取的 `TEST_CASE_V2_KNOWLEDGE_*`，现已从 Compose、环境示例及现行说明清除；前端/Platform API 的退役路由测试保留。
- `git diff --check` 通过；`scripts/check_docs.py` 失败：`docs/projects/20260920-dear-agent-memory/04-frontend-handoff.md` 1 处、`06-user-and-dev-guide.md` 2 处既有 macOS 绝对路径；与本次退役文件无关。

### Task 1.2 验证（2026-09-24）

- 本机 Docker 旧库 custom-format 备份大小 5224 字节，SHA-256 为 `cafa5969dc879449984f608cf417fe7fa137ed434dcbfd89b1be92ef2e7dcf37`，`pg_restore --list` 可读。
- 临时库 `interaction_retirement_restore_20260924` 恢复成功：`test_case_documents` 1 行、`test_cases` 0 行，读取 1 条文档 `id` 成功；临时库已清除。备份路径见 [环境清理记录](implementation/02-local-docker-cleanup.md)。

### Task 3.1 验证（2026-09-24）

- 删除前 `pg_shdepend` 仅显示旧角色拥有旧库及两张旧表；删除旧库后依赖清零，`DROP ROLE` 成功。
- 旧库/角色、旧容器及专属空卷均不存在；共享卷保留。`platform_api`、`runtime_service` 两库仍存在，`alembic_version` 各 1 行；旧 PostgreSQL 容器恢复为停止状态。
- 清理后本地四进程仍运行：Runtime `http://127.0.0.1:8123/ready` 五项检查均为 true，Platform API `http://127.0.0.1:2142/_system/health` 返回 `database_ready=true`，Web `http://127.0.0.1:3000/` 返回 200。

### 其他已执行验证（2026-09-24）

- Platform API：`test_retired_business_routes.py` 1 通过，`test_runtime_gateway_runtime_contract.py` 17 通过。
- Runtime：`test_workspace_http.py` 与 `test_artifact_platform.py` 合计 3 通过、1 跳过；5 条第三方 DeprecationWarning。
- 前端：路由与工作区服务 16 个单测通过，`pnpm typecheck`、`pnpm build` 通过；构建提示 Browserslist 数据较旧及大 chunk 警告。
- 本机 `scripts/local-stack.sh status` 显示四进程运行、Runtime/Platform API ready；Runtime `/ready` 的五项检查为 true，Platform API `/_system/health` 的 `database_ready=true`，前端首页 HTTP 200。
- Playwright 只读浏览器检查：登录后工作区总览可见，项目列表 HTTP 200（7 项），携带项目上下文的 `/api/runtime/graphs` 经 Web 同源入口返回 HTTP 200。
- 初次运行 `e2e/agent-refactor.spec.ts` 时共享夹具调用已退役的工具策略路由返回 404；该夹具已修正，后续结果见下方补充回归。
- 本机宿主 PostgreSQL 无旧库/角色；旧服务 `.env` 的 `DATABASE_URL` 为空、`storage/` 为空、8081 无监听。本机 Docker 资源已按上方 Task 1.2/3.1 清理，其他部署环境未操作。
- 修正共享 Playwright 夹具中的旧工具策略路由调用后，`chat-refactor.spec.ts` 的桌面用例通过（真实模型回复、刷新历史、审批与分支编辑），`control-plane-refactor.spec.ts` 的主路由用例通过（无旧业务请求）；前端成果页与路由 8 个单测通过。
- Platform API `test_dear_artifacts_two_service_http` 通过：真实 Runtime HTTP 成果列表、预览/下载及重启后读取。`agent-refactor.spec.ts` 已通过夹具准备，但测试仍按旧 UI 标签“名称”定位，90 秒超时；当前标签为“智能体名称”，未改该测试。
- 新增 `retired-result-service.spec.ts`：最终运行 1 通过（48.1 秒）。真实 Dear Agent 通过 `write_file`、`present_artifacts` 发布 Markdown，Web 成果页读取 SHA 命名文件并显示预览内容，浏览器下载文件名正确。先前两次失败分别源于测试使用旧下拉审批控件、按源文件名匹配成果，以及抽屉遮挡下载按钮；已按现行契约修正。临时测试项目由夹具清理。

**当前判定：** `done`（本机范围）。仓库及本机 Docker 退役、备份恢复、浏览器聊天与成果生成/预览/下载已验证；未来 Docker 部署不在本次范围。

## Final 验证记录

### 2026-09-24 Final 验证

- **状态一致性：** `README.md`、`tasks.md`、本文件及 `docs/CONTEXT.md` 均标记本机范围完成。
- **静态与配置：** 三应用业务源码/迁移无旧结果服务调用、表或旧环境变量；两份 Compose `config --quiet` 通过且不含旧服务；建库脚本 `sh -n` 及全新临时 Postgres 初始化通过，仅创建 Platform API/Runtime 库和角色。
- **单元与集成：** Platform API 退役路由 1、网关契约 17、成果双服务 HTTP 1 通过；前端原有相关 16 项、成果页及路由补充 8 项、typecheck/build 通过；Runtime 工作区/成果 3 通过、1 跳过。
- **浏览器 E2E：** 真实聊天桌面用例通过（流式回复、刷新历史、审批恢复与分支编辑）；控制面主路由用例通过（没有旧业务请求）；Dear Agent 成果用例通过（写入、发布、预览、下载）。
- **数据与回退：** 本机旧库/角色/容器/专属卷已删除；共享卷和两主服务数据库及迁移表保留。旧库 custom 备份已在临时库恢复、读取 1 条文档，SHA-256 与路径见[环境清理记录](implementation/02-local-docker-cleanup.md)。
- **未纳入本次门禁：** 两份 Compose 未整栈构建启动；用户确认未来 Docker 部署自行管理。旧 `agent-refactor.spec.ts` 仍有与当前 UI 不符的“名称”标签断言，属于独立测试维护问题。Dear Agent Memory 文档中 3 处本机绝对路径已改为相对链接/仓库无关说明，`scripts/check_docs.py` 复验通过。

**Final 结论：** `done`（仅本机退役范围）。
