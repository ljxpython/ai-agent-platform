# 本机 Docker 旧数据清理

## 时间与任务

2026-09-24；Task 1.1、1.2、3.1。本记录只覆盖本机 Compose 项目 `platform-pg-migration-20260920`，不代表其他部署环境。

## 清理前对象

- 旧服务容器 `platform-pg-migration-20260920-interaction-data-service-1` 已停止；本机 8081 无监听。其独占卷 `platform-pg-migration-20260920_interaction-data-storage` 检查为 0 个文件。
- 共享卷 `platform-pg-migration-20260920_stack-postgres-data` 承载 `postgres`、`platform_api`、`runtime_service` 和 `interaction_data_service` 四库，不在删除范围。
- 旧库 `interaction_data_service` 由同名角色拥有，仅有 `test_case_documents`（1 行）和 `test_cases`（0 行）及其主键/唯一索引。`pg_shdepend` 显示该角色只依赖这两表和旧库所有权。
- `platform_api` 与 `runtime_service` 的 `alembic_version` 表各有 1 行。本机宿主 PostgreSQL 无旧库或同名角色。

## 备份与恢复

- `pg_dump -Fc` 备份位于 `apps/platform-api/.data/backups/20260924-interaction-data-service-retirement/interaction_data_service.dump`，目录权限 `0700`、文件权限 `0600`、大小 5224 字节；`.data/` 被 Git 忽略。
- SHA-256：`cafa5969dc879449984f608cf417fe7fa137ed434dcbfd89b1be92ef2e7dcf37`。
- `pg_restore --list` 确认两表的数据及约束/索引均在归档中；在同一容器的隔离临时库 `interaction_retirement_restore_20260924` 以 `--no-owner --exit-on-error` 恢复成功，读得 `test_case_documents:1`、`test_cases:0`，旧文档 `id` 非空。临时库随后删除。

## 定向清理与复查

- 依次删除旧库、确认无剩余依赖后删除独占角色；旧库和临时库均不再存在。
- 删除已停止的旧服务容器及其空专属卷；未执行 `docker compose down --volumes`，共享 Postgres 卷仍存在。
- 复查 `platform_api`、`runtime_service` 两库仍在，且各自 `alembic_version` 均为 1 行。为盘点临时启动的旧 PostgreSQL 容器已恢复为 `Exited (0)`。

## 剩余边界

仓库外调用方及其他部署环境没有访问证据，不能把本机清理结论推广到生产。完整聊天与成果 E2E 仍未通过现有测试夹具，见 `verification.md`。
