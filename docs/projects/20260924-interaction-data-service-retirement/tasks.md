# interaction-data-service 退役 - 任务拆分

## Phase 1：目标盘点与可恢复备份

### Task 1.1：确认依赖与真实清理对象
- **改动内容：** 核对前端、Platform API、Runtime 的代码及配置引用；盘点目标环境的旧容器、外部调用、实际数据库/角色、表/行数、卷及本机附件目录。
- **代码位置：** `apps/platform-web/src/`、`apps/platform-api/src/`、`apps/runtime-service/src/`、`apps/interaction-data-service/app/db/`、`deploy/`；目标环境只读检查。
- **预期结果：** 仓库内依赖清单与旧服务独占资源清单完整；共享资源不列入删除对象。
- **验证项：** 记录 8081 调用、两个业务表及索引、数据库角色、Compose 实际卷名；发现有效外部调用时先解决依赖。
- **状态：** [x] 已完成 2026-09-24：仓库内引用、本机 8081/PG/附件及 Docker 旧容器、数据库和卷已核对；用户确认仅本机属于本次范围，未来 Docker 部署自行管理。见[环境清理记录](implementation/02-local-docker-cleanup.md)。
- **合规检查：** [x] 盘点完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

### Task 1.2：备份并验证可恢复
- **改动内容：** 备份实际旧库与附件，在隔离环境恢复并读取至少一条旧结果；记录备份位置、校验信息及清理对象，补齐架构决策。
- **代码位置：** 本项目 `verification.md`、`README.md`、`docs/decisions/`；目标环境数据库与存储。
- **预期结果：** 清理旧库与附件后有可验证的回退路径。
- **验证项：** 备份/恢复证据齐全；旧库角色和存储卷确认独占，Platform API/Runtime 库不在清理名单。
- **状态：** [x] 已完成 2026-09-24：本机 Docker 旧库已备份并在临时库恢复、读取 1 条文档；专属附件卷为空。其他环境若存在旧资源，仍须各自备份和验证。见 [环境清理记录](implementation/02-local-docker-cleanup.md)。
- **合规检查：** [x] 备份与恢复完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

## Phase 2：仓库内退役

### Task 2.1：删除旧服务并收口容器配置
- **改动内容：** 删除 `apps/interaction-data-service/` 全目录（包括盘点/备份后的本机私有文件与附件）；移除两份 Compose 的服务定义、Runtime 旧变量、专属卷声明，以及环境示例和新实例建库入口。
- **代码位置：** `apps/interaction-data-service/`、`deploy/docker-compose.stack.yml`、`deploy/docker-compose.stack.nginx.yml`、`deploy/.env.stack.example`、`deploy/postgres/init/01-init-shared-databases.sh`。
- **预期结果：** 旧服务实现、自动建表/补列逻辑及构建入口消失；整仓容器配置只启动仍在用的服务。
- **验证项：** 两份 `docker compose config --quiet` 与服务列表 ✅；`sh -n deploy/postgres/init/01-init-shared-databases.sh` ✅；新空库只创建 Platform API/Runtime 库 ✅；源码与旧变量静态搜索 ✅。
- **状态：** [x] 已完成 2026-09-24 → 见 [实施记录](implementation/01-repository-retirement.md)与[补充核查](implementation/03-residual-audit-and-regression.md)。
- **合规检查：** [x] 代码实现完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

### Task 2.2：更新当前事实源
- **改动内容：** 修正部署契约、快速开始、运维手册、根 README 中英双语、AGENTS、FEATURES、CONTEXT 及 Runtime 部署示例；删除已过时的架构图源文件及 SVG，保留历史项目/发布记录。
- **代码位置：** `docs/local-deployment-contract.yaml`、`docs/quickstart/`、`docs/runbooks/`、`docs/guides/`、`docs/knowledge/ai-harness-practice.md`、`docs/diagrams/`、`docs/assets/`、`deploy/README.md`、`apps/runtime-service/deploy/`、`README.md`、`README.en.md`、`AGENTS.md`、`docs/FEATURES.md`、`docs/CONTEXT.md`。
- **预期结果：** 所有当前操作指引均只描述实际存在的服务与调用链路。
- **验证项：** 对非历史现行文档、脚本、三应用源码搜索旧服务名、8081、旧环境变量 ✅；剩余引用仅在本项目/ADR 状态记录。
- **状态：** [x] 已完成 2026-09-24 → 见 [实施记录](implementation/01-repository-retirement.md)与[补充核查](implementation/03-residual-audit-and-regression.md)。
- **合规检查：** [x] 代码实现完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

## Phase 3：目标环境清理与验证

### Task 3.1：清理旧服务独占数据库和存储
- **改动内容：** 停止确认的旧实例；删除旧服务独占数据库（包含 `test_case_documents`、`test_cases` 及索引）、独占角色、专属 Docker 卷/本机附件；不清理共享 Postgres 卷。
- **代码位置：** 目标环境 Postgres、Docker 卷和 `apps/interaction-data-service/storage/`；操作和对象记录到 `implementation/`。
- **预期结果：** 旧服务进程、专属库/表与附件存储均不存在，其他服务数据仍在。
- **验证项：** 使用真实对象名称逐一核验；确认 Platform API/Runtime 库及迁移版本表仍完整。
- **状态：** [x] 已完成 2026-09-24：本机 Docker 旧库、独占角色、停止的旧容器和空专属卷已定向删除；共享卷与另外两库及迁移表保留。其他部署环境不在本次已验证范围。见 [环境清理记录](implementation/02-local-docker-cleanup.md)。
- **合规检查：** [x] 资源清理完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

### Task 3.2：Final 回归与交接
- **改动内容：** 验证两种 Compose、主服务测试、浏览器主链路及清理后的数据边界；记录结果与备份/恢复证据。
- **代码位置：** `verification.md`、`implementation/`。
- **预期结果：** 前端、Platform API、Runtime 当前功能可用，旧服务所有权资源已清除。
- **验证项：** 见 `verification.md`；Phase 记录与 Final 结论分别填写，未执行项明确标注。
- **状态：** [x] 已完成 2026-09-24：静态、单测、构建、四进程健康、真实浏览器聊天、控制面及成果生成/预览/下载通过；Compose 配置与新空库初始化通过。未整栈构建两种 Compose，作为部署时验证项。见[补充核查](implementation/03-residual-audit-and-regression.md)。
- **合规检查：** [x] 本机回归完成；[x] 验证项已执行；[x] tasks.md 已更新；[x] CONTEXT.md 已更新。

## 进度追踪

- [x] Phase 1 本机 Docker 盘点和可恢复备份完成
- [x] Phase 2 仓库内退役完成
- [x] Phase 3 本机目标环境清理和主链路 E2E 完成
