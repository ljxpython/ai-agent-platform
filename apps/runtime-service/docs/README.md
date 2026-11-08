# Runtime Service 开发文档

这里帮助开发者在现有平台中新增或扩展 Agent。先看当前开发路径，再按任务查专题和历史设计。

## 新开发者的阅读顺序

1. [Agent 设计与开发指南](standards/runtime-agent-development-guide.md)：选择 Agent 类型、理解模块架构、划分目录、接入平台并完成验证。
2. [开发范式与规则](standards/runtime-service-development-standard.md)：必须遵守的约束及各能力的具体规则。
3. [案例与资料导航](standards/runtime-service-reading-guide.md)：当前任务该看哪段源码、哪组测试、哪些官方资料。
4. [运行与验证](standards/runtime-service-onboarding-and-verification.md)：所属环境启动、按类型选测试和结果记录。

[应用 README](../README.md) 提供安装与启动背景；[standards 首页](standards/README.md) 汇总当前规则。关联 Worktree 先读[资源隔离规范](../../../docs/standards/worktree-development.md)。

## 常见任务从哪里进入

| 任务 | 先读 |
|---|---|
| 新增一个普通工具 Agent | 开发指南中的类型选择、模块架构与接入步骤；reference_agent 源码和测试 |
| 固定步骤、条件分支、人工确认 | 开发指南中的 Workflow 边界；workflow_demo 源码和恢复测试 |
| 文件操作、Skills、子 Agent | 案例导航中的 deep_agent_demo / backend_demo / Showcase |
| 接入 MCP、文档、知识或后台任务 | 案例导航的按需专题，不复制整套 DearFlow |
| 修改模型/Context、权限或跨服务能力 | 对应现行专题与双端代码；按根 AGENTS 判断影响级别 |
| 查当初为何这样设计 | 下方 knowledge 索引；不能直接把历史 Draft 当作当前规范 |

## 设计依据与历史资料

`knowledge/` 保存架构推导、早期 R0～R6 计划和专项资料。其中的版本、目录、能力状态可能对应当时阶段，不能代表当前运行状态。仍有效的设计保留在原位置；有差异时先核对源码、测试和当前标准，安全/权限/契约问题按根规则人工裁决。

按问题选择阅读，不要求新开发者通读全部资料：

- Service/Graph/目录职责：[11 服务架构](knowledge/11-agent-service-directory-architecture.md)、[13 目标目录](knowledge/13-runtime-service-target-code-layout.md)。
- Context/模型与策略：[14 契约与解析](knowledge/14-runtime-contracts-and-resolution-design.md)。
- 生命周期/失败：[15 Middleware](knowledge/15-runtime-middleware-lifecycle-and-failure-semantics.md)、[23 Graph/Thread/Checkpoint](knowledge/23-graph-thread-backend-checkpoint-lifecycle-design.md)。
- 工具与资源：[19 Tool/MCP](knowledge/19-runtime-tool-capability-mcp-and-side-effect-design.md)、[20 Workspace/Skills/Subagents](knowledge/20-runtime-backend-workspace-skills-and-subagents-design.md)。
- 测试与整合：[25 测试设计](knowledge/25-runtime-testing-and-cross-service-contract-design.md)、[22 平台契约设计](knowledge/22-platform-runtime-contract-design.md)。
- 历史阶段证据：[28 重构计划](knowledge/28-runtime-refactor-development-plan.md)、[31 早期对齐审计](knowledge/31-runtime-refactor-alignment-audit.md)。

当前功能状态查[全仓功能总览](../../../docs/FEATURES.md)和对应项目验证记录；不能用早期 R6 的状态覆盖后续专项，也不能凭当前依赖版本解除旧验收限制。
