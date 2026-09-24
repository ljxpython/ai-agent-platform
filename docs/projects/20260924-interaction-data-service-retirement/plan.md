# interaction-data-service 退役 - 整体方案

## 背景与事实

2026-09-10 的 [平台 Testcase 业务退役记录](../20260910-platform-api-refactor/implementation/01-retire-knowledge-testcase.md)已删除 `platform-api` 的 Testcase/结果域适配器及 `platform-web` 的对应入口，当时明确保留独立结果服务。当前源码中，三个主应用没有 `/api/test-case-service`、`INTERACTION_DATA_SERVICE_*` 或 `interaction-data-service` 的现行调用；`apps/interaction-data-service/app/db/models.py` 仍只定义 Testcase 文档和用例表。当前成果读取通过 `platform-web -> platform-api -> runtime-service` 的 workspace/artifacts 链路。

两份整仓 Compose 仍构建并启动该服务、注入 Runtime 旧环境变量、初始化专属数据库，文档也仍把它写作现行结果链路。本地默认栈则未启动它。代码与部署、文档之间存在漂移。

上述结论是仓库静态核查，不代表已确认外部客户端、运行实例或历史数据情况。

### 对现有三个应用的影响

| 应用 | 当前核查结果 | 实施与验证 |
|---|---|---|
| `platform-web` | `src/` 无旧服务 URL、模块或测试用例结果页调用；当前成果页走平台网关 | 不预设业务代码改动；跑路由测试、构建和成果页 E2E |
| `platform-api` | `src/` 无旧服务 adapter/路由；Testcase 业务此前已退役 | 不改现有数据库迁移；跑退役路由测试、网关测试与 HTTP 健康/运行链路 |
| `runtime-service` | `src/` 无旧持久化调用；两份 Compose 和 Runtime 部署示例仍注入旧服务环境变量 | 清理部署变量，跑 Runtime 测试、真实 run 与成果读取 |

这只是仓库内影响判断；目标环境的外部调用与私有配置仍须按实施门槛核查。当前 Runtime workspace 成果链路不承担旧 Testcase CRUD 的兼容职责。

## 目标与边界

- 删除 `apps/interaction-data-service/` 全目录，使整仓部署不再创建该容器或专属数据库。
- 清除旧服务独占数据库、表/索引、角色及附件存储；清理前确定实际名称、依赖和可恢复备份。
- 移除主应用部署配置里的旧服务变量、建库入口及现行文档/架构图中的旧链路。
- 验证 Platform API、Runtime、Web 的登录、聊天、运行及成果浏览链路可用。
- 历史项目文档和退役原因记录继续保留。过时的现行文档直接修正，不批量改写历史档案。

## 方案设计

### 实施门槛：定位目标与验证备份

核对目标环境是否运行旧容器、8081 是否有仓库外调用者，确认实际数据库/角色、存储卷、本地 `storage/` 及私有 `.env` 的位置。记录对象名称、连接归属、表和行数，完成旧库与附件备份并在隔离环境验证可恢复。若发现有效外部调用或数据库/角色被其他应用使用，先解决依赖或修订范围，再执行停服、删库和删卷；不凭默认名称或仓库搜索结果直接操作实例。

### 仓库改动

1. **服务目录：** 删除 `apps/interaction-data-service/` 全目录，包括受版本管理的服务实现、测试、文档、Dockerfile、依赖锁文件，以及盘点后的本机私有 `.env`、`.venv`、缓存和 `storage/`；删除前按上述门槛备份实际数据。
2. **容器与建库：** 修改 `deploy/docker-compose.stack.yml`、`deploy/docker-compose.stack.nginx.yml`、`deploy/.env.stack.example`、`deploy/postgres/init/01-init-shared-databases.sh`。移除服务定义、专属卷声明、Runtime 旧 URL/Token/Timeout 和专属建库配置；保留共享 Postgres 与其他服务配置。
3. **数据库与附件：** `app/db/models.py` 仅定义 `test_case_documents`、`test_cases`；`app/db/init_db.py` 用 `create_all()` 和 `ALTER TABLE`/索引语句处理结构，没有 Alembic 迁移目录或独立迁移版本表。删除服务目录即删除这些建表/迁移代码。目标环境中先停旧服务并完成备份/恢复验证，再删除确认独占的整库及其表/索引；数据库角色仅在确认独占后删除。单独删除确认归属的 `interaction-data-storage` 卷和本机附件目录。不得触碰 `runtime_service`、`platform_api` 数据库及其 `alembic_version`。
4. **依赖与现行文档：** 对 `apps/platform-web/src/`、`apps/platform-api/src/`、`apps/runtime-service/src/` 再做源码和配置引用核查；仅修复真实依赖。修改 `docs/local-deployment-contract.yaml`、`deploy/README.md`、`docs/quickstart/`、`docs/runbooks/`、`docs/guides/`、`docs/knowledge/ai-harness-practice.md`、`README.md`、`README.en.md`、`AGENTS.md`、`docs/FEATURES.md`、`docs/CONTEXT.md` 及 Runtime 部署示例里的当前服务说明。删除已过时且不再使用的 `docs/diagrams/system-architecture.{zh,en}.drawio`、`docs/diagrams/local-dev-startup-flow.{zh,en}.drawio` 和对应 `docs/assets/*.svg`；历史项目/发布记录保留原貌。
5. **决策留痕：** 在 `docs/decisions/` 记录退役原因、当前成果路径、数据库清理边界和回退方式；本项目文档记录实际对象与验证结果。

### 链路与契约

现行用户链路保持 `platform-web -> platform-api -> runtime-service`。旧 `/api/test-case-service/*` 随服务退役停止提供；仓库内已无消费者，本项目不为其增加转发或替代接口。新 Compose 不再暴露 8081，也不再自动创建旧服务数据库。外部消费者核查未通过时不得将“仓库内无引用”当作停服依据。

## 风险与回退

- **外部调用：** 仓库外客户端可能仍访问 8081。部署前核对目标环境访问记录、调用方清单与负责人；存在有效调用则暂停停服并修订方案。
- **误删/不可恢复：** 实际库名和角色可由环境变量覆盖，卷名也可能带 Compose 项目前缀。按真实配置与数据库目录核对独占性，备份并验证恢复后逐个删除；禁止对整套 Compose 使用 `down --volumes`，也不删除其他服务的迁移版本表。
- **部署差异：** 当前本地默认栈与整仓 Compose 对结果服务的处理不同。分别验证两份 Compose 与默认本地栈；发布时确认实际使用的部署方式。
- **回退：** 保留可定位的退役前代码版本/镜像、原 Compose 配置和已验证的数据库/附件备份；在隔离环境验证旧服务读取恢复的数据。回退需恢复服务、库和附件，不能靠创建空库冒充恢复。

## 实施顺序

1. 盘点外部消费者、部署实例、旧库/角色与附件，完成备份及隔离恢复验证。
2. 删除服务目录、仓库配置和现行文档，验证新部署与当前主链路。
3. 停旧实例，按确认的对象清理独占数据库、角色、附件卷/目录；复查主服务数据与链路，记录清理及回退证据。
