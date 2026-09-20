# Docs 文档导航

目标：让人和 AI 只读取当前任务需要的最小文档集合。

## 1. 开始一个任务

1. [根目录 AGENTS.md](../AGENTS.md) —— 开发流程、改动分级标准（本地/链路/治理改动）、Skills 入口
2. 最窄的 app/service 自己的 `docs/`（如 `apps/platform-api/docs/`）

不要默认读取整个 `docs/` 目录。

## 2. 启动、部署和运维

- [数据库部署、迁移与本地开发规范](./guides/database-operations.md)
- [本地开发说明](./quickstart/local-dev.md)
- [环境变量矩阵](./quickstart/env-matrix.md)
- [非 Docker 新机部署手册](./quickstart/deployment-guide.md) —— 原生依赖、账号、空库、配置、SSH 访问和验收
- [运维交接与验收回执](./quickstart/operator-handoff.md) —— 接收源码/私有配置、操作顺序、异常处理和交付标准
- [本地部署契约](./local-deployment-contract.yaml)
- [容器化交付指南](../deploy/README.md)
- [从零到一容器化部署](./quickstart/zero-to-one-container-deploy.md)
- [容器更新 Runbook](./runbooks/container-update-runbook.md)

## 3. 变更与发布

- [提交与 Changelog 规范](./guides/commit-and-changelog-guidelines.md)
- [更新日志](./CHANGELOG.md)
- [发布记录](./releases/)
- [功能现状总览](./FEATURES.md) —— 按服务分组的当前功能清单，看仓库现在有什么直接看这份
- [Platform API PostgreSQL 迁移专项](./projects/20260920-platform-api-postgresql-migration/README.md) —— 已完成本地切换、完整验收及历史清理；部署、迁移与恢复规范已交付
- [GraphHarbor v3 对齐与平台迁移](./projects/20260915-graphharbor-v3-alignment/README.md) —— 已批准实施；A及B1/B2完成，Server补验与平台恢复接入进行中，前端本轮只交接
- [Dear Agent 总纲与能力迁移](./projects/20260913-dearflow-agent/README.md) —— 第二版规划；先搭前后端框架，独立前端复用 Chat，逐章接续与 23 个 Skills 验收，待治理评审
- [Dear Agent 记忆闭环补齐](./projects/20260920-dear-agent-memory/README.md) —— 五专题：源码/目录、Runtime、Platform接口、前端交接、分层验证；我们实施后端与Runtime，前端交同事；规划待评审，尚未实施
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
