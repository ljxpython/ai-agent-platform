# 仓库内结果服务退役

## 时间与任务

2026-09-24；Task 2.1、2.2 完成。本机 Docker 资源清理见 [后续记录](02-local-docker-cleanup.md)；其他环境和完整 E2E 仍待验收。

## 实施

- 删除 `apps/interaction-data-service/` 全目录，包括 `app/db/models.py` 的两张表定义、`app/db/init_db.py` 的 `create_all()`/补列/索引逻辑、测试、依赖和本机私有 `.env`/`.venv`。删除前 `storage/` 为空，`.env` 的 `DATABASE_URL` 为空；未发现旧服务 Alembic 迁移目录。
- `deploy/docker-compose.stack.yml`、`deploy/docker-compose.stack.nginx.yml` 不再构建/启动旧服务，不再给 Runtime 注入旧连接变量，也不再声明专属附件卷。`deploy/postgres/init/01-init-shared-databases.sh` 只创建 Runtime 与 Platform API 的库/角色；`deploy/.env.stack.example` 和 Runtime 部署示例删除旧变量。
- 更新根 README 中英双语、`AGENTS.md`、`docs/local-deployment-contract.yaml`、快速开始/运维/开发文档、`docs/FEATURES.md`、`docs/CONTEXT.md`；移除失效的架构图、启动图及 Testcase 当前演示图。历史项目、发布记录和 changelog 保留为历史事实。
- `apps/platform-web/src/`、`apps/platform-api/src/`、`apps/runtime-service/src/` 均无旧服务名、旧 URL、旧表名或旧环境变量引用，未改三应用业务代码。当前成果由 Runtime workspace/artifacts 提供。

## 本机资源核查

- `psql` 连本机 PostgreSQL 成功；`pg_database` 无 `interaction_data_service`，`pg_roles` 无同名角色。`platform_api` 库内无 `test_cases` 或 `test_case_documents`；未执行 DROP。
- 8081 无监听进程；旧服务 `storage/` 为空。
- 初次核查时 Docker daemon 未运行；随后启动 Docker Desktop 完成旧库备份、隔离恢复及独占卷清理，详见 [后续记录](02-local-docker-cleanup.md)。其他目标环境及外部调用者尚未核实。

## 验证和限制

两份 Compose `config --quiet` 和服务列表通过；建库脚本 `sh -n` 通过。Platform API 18 个相关测试、前端 16 个相关单测及 typecheck/build、Runtime 3 个相关测试通过；Runtime 另有 1 个测试跳过。本地四进程健康，Playwright 只读检查 Web 总览、项目列表和经 Platform API 查询 Runtime Graph 均成功。

完整 Playwright Agent E2E 在夹具准备阶段因旧工具策略路由 `404 route_not_found` 失败，未进入页面断言。`scripts/check_docs.py` 报出 Dear Agent Memory 项目中 3 处既有 macOS 绝对路径，与本次删除无关。以上证据不足以将整个项目标记 `done`；详细命令与结果见 `verification.md`。
