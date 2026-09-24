# interaction-data-service 退役

## 项目概述

- **启动日期：** 2026-09-24
- **目标：** 完整删除旧 Testcase 结果服务、现行配置/文档及其独占数据资源，并验证其余三个应用不受影响。
- **负责人：** 用户确认退役范围和目标环境；AI 协助实施与验证。
- **模板类型：** 标准模板
- **状态：** done（本机范围）；仓库与本机 Docker 独占资源退役、备份恢复、真实浏览器聊天及成果生成/预览/下载已验证。未来 Docker 部署由用户另行管理。

## 快速导航

- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证计划和记录](verification.md)

## 改动范围

- **影响范围：** `apps/interaction-data-service/` 全目录、两份整仓 Compose、Postgres 初始化与部署配置、现行文档/架构图、旧服务独占数据库和存储；`platform-web`、`platform-api`、`runtime-service` 做依赖检查及回归验证。
- **改动级别：** 治理改动（服务退役与部署拓扑调整）。
- **预计工作量：** 仓库清理与验证约 1-2 人天；目标环境盘点、数据备份/恢复演练和清理另计。

## 关键决策与评审

1. 退役对象是旧 Testcase 结果服务；Dear Agent 的成果仍由 Runtime workspace 提供，现阶段不建设替代结果服务或迁移旧接口。
2. 用户已明确要求清理旧服务独占数据库、相关表/索引和存储。该服务没有 Alembic 迁移链或专属版本表；不得删除 Platform API / Runtime 的迁移历史或共享数据库。
3. 仓库静态搜索只能证明仓库内没有现行调用；本次仅清理并验证本机，未来 Docker 部署由用户另行管理。

**评审记录：** 2026-09-24，用户先同意退役方向，随后明确授权直接删除 `apps/interaction-data-service`、清理相关文档/脚本，以及旧服务数据库和迁移痕迹；要求验证前后端及 Runtime 是否受影响。实际数据库实例与存储卷按环境核对。本机清理与备份证据见[环境记录](implementation/02-local-docker-cleanup.md)，仓库实施见[记录](implementation/01-repository-retirement.md)，决策见[退役 ADR](../../decisions/20260924-interaction-data-service-retirement.md)。
