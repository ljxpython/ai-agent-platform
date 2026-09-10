# 功能现状总览

全仓库当前功能清单，按服务分组。每次 `apps/{app}/docs/changes/`、根目录 `docs/changes/` 或
`docs/projects/` 落一笔新记录时，同步在这里新增一行或更新对应行的状态，不需要每次改动都重写整份文档。

状态取值：规划中 / 进行中 / 已完成 / 部分完成（说明缺什么）。

## platform-web

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 正式聊天 v2（LangChain 流式运行时、线程续接、工具调用与中断展示） | 已完成 | `docs/projects/20260908-platform-chat-rewrite/` |
| 独立调试工作台（运行级模型/工具/提示词配置） | 已完成 | `docs/projects/20260908-platform-chat-rewrite/` |
| 控制面核心页面（overview/projects/users/assistants/me/security/audit） | 已完成 | `apps/platform-web/docs/control-plane-page-standard.md` |
| 知识库、测试用例工作台退役 | 已移除页面、路由、菜单与专属依赖；整体平台重构进行中 | `docs/projects/20260910-platform-api-refactor/` |

## platform-api

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 鉴权、项目治理、审计、catalog | 已完成 | `apps/platform-api/docs/handbook/project-handbook.md` |
| 重构后文档体系重建 | done：10篇活文档、28文件归档与引用修复，配置/契约核对及33项相关测试通过 | [文档工程](projects/20260910-platform-api-docs-rebuild/README.md) |
| 控制面边界与代码简化重构 | 本阶段后端 done：事务/目录、Docker Showcase、真实备份恢复、混合负载及 20 条公开接口矩阵已验收；前端、整套容器部署与完整 Server 等价性 deferred | `docs/projects/20260910-platform-api-refactor/` |
| 运行时网关（受管模型/工具/prompt 契约下发） | 已完成 | `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` |
| 中转站维度模型管理、对话高级模型选择器 | 已完成 | （提交 8056869） |

## runtime-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| Graph 注册、模型参数解析、工具装配 | 已完成 | `apps/runtime-service/docs/standards/*.md` |
| MCP 接入 | 已完成 | `apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md` |
| Runtime 鉴权、middleware 层、reference agent | 已完成 | `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` |
| showcase_demo — 教学智能体（工具调用/HITL/子智能体/Todo/Sandbox/Skills） | 部分完成：post26 平台后端真实联调、审批重启恢复与报表 43.50 已验收；前端后置 | `docs/projects/20260908-showcase-demo/` |

## interaction-data-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 结果域落库与查询 | 已完成 | `apps/interaction-data-service/docs/service-design.md` |

## 仓库级 / 工具链

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 改动分级 + Skills 自动触发（plan-project/implement-feature/verify-change） | 已完成 | `AGENTS.md` |
| 文档一致性检查（`scripts/check_docs.py`） | 已完成 | `scripts/check_docs.py` |

- Platform API：Agent/Profile ORM 已合并，空库静态基线已通过 SQLite/PostgreSQL 往返验证；完整控制面重构仍为 partial，见 [实现记录](projects/20260910-platform-api-refactor/implementation/08-agent-single-table.md)。

- Agent resync / Operations：后端全链路已退役，20 表及字段收缩和真实 Runtime 验收通过；当前状态见 [11](projects/20260910-platform-api-refactor/implementation/11-backend-closeout.md)。
