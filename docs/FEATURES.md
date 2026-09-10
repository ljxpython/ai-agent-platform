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
| 控制面边界与代码简化重构 | 进行中：知识库/测试用例退役、可安装 src 包和远端 Graph/schema 后端已落地；真实联调、单表 Agent、新数据库、网关与 Operations 退役待完成 | `docs/projects/20260910-platform-api-refactor/` |
| 运行时网关（受管模型/工具/prompt 契约下发） | 已完成 | `apps/platform-api/docs/standards/runtime-gateway-interface-standard.md` |
| 中转站维度模型管理、对话高级模型选择器 | 已完成 | （提交 8056869） |

## runtime-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| Graph 注册、模型参数解析、工具装配 | 已完成 | `apps/runtime-service/docs/standards/*.md` |
| MCP 接入 | 已完成 | `apps/runtime-service/docs/knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md` |
| Runtime 鉴权、middleware 层、reference agent | 已完成 | `apps/runtime-service/docs/knowledge/28-runtime-refactor-development-plan.md` |
| showcase_demo — 教学智能体（工具调用/HITL/子智能体/Todo/Sandbox/Skills） | 部分完成：后端教学范围已验收；平台联调/前端验收暂缓至 platform-api 重构后 | `docs/projects/20260908-showcase-demo/` |

## interaction-data-service

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 结果域落库与查询 | 已完成 | `apps/interaction-data-service/docs/service-design.md` |

## 仓库级 / 工具链

| 功能 | 状态 | 关联文档 |
|---|---|---|
| 改动分级 + Skills 自动触发（plan-project/implement-feature/verify-change） | 已完成 | `AGENTS.md` |
| 文档一致性检查（`scripts/check_docs.py`） | 已完成 | `scripts/check_docs.py` |
