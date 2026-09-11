# Docs 文档导航

目标：让人和 AI 只读取当前任务需要的最小文档集合。

## 1. 开始一个任务

1. [根目录 AGENTS.md](../AGENTS.md) —— 开发流程、改动分级标准（本地/链路/治理改动）、Skills 入口
2. 最窄的 app/service 自己的 `docs/`（如 `apps/platform-api/docs/`）

不要默认读取整个 `docs/` 目录。

## 2. 启动、部署和运维

- [本地开发说明](./quickstart/local-dev.md)
- [环境变量矩阵](./quickstart/env-matrix.md)
- [部署文档](./quickstart/deployment-guide.md)
- [本地部署契约](./local-deployment-contract.yaml)
- [容器化交付指南](../deploy/README.md)
- [从零到一容器化部署](./quickstart/zero-to-one-container-deploy.md)
- [容器更新 Runbook](./runbooks/container-update-runbook.md)

## 3. 变更与发布

- [提交与 Changelog 规范](./guides/commit-and-changelog-guidelines.md)
- [更新日志](./CHANGELOG.md)
- [发布记录](./releases/)
- [功能现状总览](./FEATURES.md) —— 按服务分组的当前功能清单，看仓库现在有什么直接看这份
- [Platform Web 架构与 Agent Chat 重构](./projects/20260910-platform-web-refactor/README.md) —— 原前端六专题已批准、待实施；第 07 专题多端队列与 Runtime Middleware 最后完成，记录 GraphHarbor 仓库位置及通用引擎边界

链路/治理改动的项目文档统一放在 [projects/](./projects/) 下，AI 判断出对应级别后自动用 `plan-project` Skill 创建，无需手动调用；单服务改动的留痕记录见对应 `apps/{app}/docs/changes/`，仓库级/工具链改动见 [changes/](./changes/)。三者的选择标准见 `AGENTS.md` 的「文档组织」。

## 4. 目录说明

- `quickstart/`：新人必读（架构、本地开发、部署）
- `guides/`：开发规范
- `FEATURES.md`：全仓库功能现状总览
- `changes/`：仓库级/工具链级单项目改动记录
- `projects/`：链路/治理改动的项目文档
- `decisions/`：仓库级/跨服务技术决策（ADR）
- `archive/`：过时内容归档
- `releases/`：历史发布记录
- `runbooks/`：运维操作手册
