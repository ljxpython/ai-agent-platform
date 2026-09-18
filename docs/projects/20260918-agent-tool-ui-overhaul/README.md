# Agent & 工具界面全面优化

## 项目概述
- **时间：** 2026-09-18 至 TBD
- **目标：** 补全 Agent 创建能力、美化 Agent 管理/详情/工具界面、理清参数传递链路、补全工具授权权限逻辑
- **负责人：** @lijiaxin
- **状态：** done（已全量通过前端构建与单元测试、后端测试）

## 快速导航
1. [01-agent-list-and-create.md](01-agent-list-and-create.md)：Agent 管理列表页美化 + 新增创建 Agent 功能
2. [02-agent-detail.md](02-agent-detail.md)：Agent 详情页高级化改造 + 参数传递全链路核查
3. [03-tool-auth-and-ui.md](03-tool-auth-and-ui.md)：工具界面美化 + 工具授权权限逻辑核查与补全

## 改动范围
- **影响服务：** platform-web（前端）、platform-api（后端 iam 模块）
- **改动级别：** 链路改动

## 落地决策与结果
1. **Agent 创建**：采用方案 A（复用 AgentEditorPage），新增 `/projects/:projectId/agents/new` 路由；补全了 `createAgent` API 封装与 `save()` 新建流程分支，创建后自动跳转到对应 Agent 详情页。
2. **参数全链路**：核实 `temperature`/`max_tokens`/`top_p`/`execution_mode` 全链路生效（在 runtime-service 的 `resolver.py` 中有完整的解析与运行时注入机制）；修复了 `execution_mode` 在详情页中被错误渲染成数字输入框的 bug（改为选择模式：Flash/Standard/Pro/Ultra）。
3. **工具授权与权限**：发现后端 `PROJECT_RUNTIME_WRITE` 错误包含 `EXECUTOR` 角色并进行了收紧（仅限 `{ADMIN, EDITOR}`）；前端将工具列表升级为卡片式视图，集成状态 Pill、授权/撤权操作按钮及“同步工具”动作。
