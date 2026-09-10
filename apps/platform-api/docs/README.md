# Platform API 文档

| 任务 | 文档 |
| --- | --- |
| 安装、启动、最小验证 | [服务README](../README.md) |
| 平台能力与使用流程 | [使用手册](handbook/project-handbook.md) |
| 服务、模块与数据归属 | [架构](handbook/architecture.md) |
| 新增接口、用例或表 | [开发规范](handbook/development-playbook.md) |
| 配置数据库、认证和Runtime | [配置](handbook/configuration.md) |
| 初始化与变更数据库 | [数据库](handbook/database.md) |
| 排障、发布和恢复 | [运维](handbook/runbook.md) |
| 角色、项目与服务账号 | [权限标准](standards/permission-standard.md) |
| 审计动作与收尾 | [审计标准](standards/audit-standard.md) |
| Runs、审批与SSE | [网关标准](standards/runtime-gateway-interface-standard.md) |

## 事实来源与维护

代码、配置和测试证明实际行为；活文档维护当前约束。冲突时核实代码并修正文档，不用旧文档指导新增兼容层。

服务README负责启动，本文负责导航，handbook/standards负责长期规则。[重构工程](../../../docs/projects/20260910-platform-api-refactor/README.md)保留实施与验收过程，不把逐轮状态和测试数字复制进手册。

遵循[根AGENTS](../../../AGENTS.md)，修改功能时更新正文与[功能总览](../../../docs/FEATURES.md)。实际需要时再新增changes或独立ADR，不建空模板目录。

[历史索引](archive/README.md)不再指导开发。前端/浏览器、整套容器部署、完整Server等价性仍后置；前端调整只维护在[交接清单](../../../docs/projects/20260910-platform-api-refactor/05-frontend-handoff.md)。
