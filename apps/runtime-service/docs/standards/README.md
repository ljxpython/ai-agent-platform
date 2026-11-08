# Runtime Service 当前开发标准

## 开发一个新 Agent

1. [Agent 设计与开发指南](runtime-agent-development-guide.md)：需求设计、选型、模块架构、目录、装配与交付。
2. [开发范式与规则](runtime-service-development-standard.md)：现行必守约束及能力细节。
3. [案例与资料导航](runtime-service-reading-guide.md)：案例用途、源码/测试、按需专题、官方资料查询方法。
4. [运行与验证](runtime-service-onboarding-and-verification.md)：本地环境与验证入口。

## 按需专题

- [通用后台任务接入](background-task-integration.md)：受管 Docker、生命周期及正式启用边界。
- [模型上下文隐私保护](model-context-privacy.md)：主/子模型、摘要及辅助调用的保护要求。
- [项目知识 MCP](project-knowledge-mcp.md)：项目范围、来源契约、共享上传及维护。
- [上下文窗口管理](runtime-service-development-standard.md#上下文窗口管理)、[Plan Mode](runtime-service-development-standard.md#通用-plan-mode-接入)、[Run Token 额度](runtime-service-development-standard.md#run-token-额度保护)：按需接入，不默认覆盖所有图。
- [Workspace 规则](runtime-service-development-standard.md#workspace-执行目标与恢复)与[沙箱运行手册](../../../../docs/runbooks/runtime-sandbox-node.md)：local/Docker/remote 及持久绑定。
- [用量聚合查询](runtime-service-development-standard.md#已采集用量的受控聚合查询)：仅在修改采集/报表能力时阅读。

## 规范、案例与事实如何使用

- 根 [AGENTS.md](../../../../AGENTS.md) 规定改动分级、人工评审、资源隔离和冲突处理；服务文档不覆盖这些要求。
- 本目录描述当前开发约束；新指南解释如何使用这些约束，不替代各专题。
- 源码和测试用于核对当前实际行为；案例 README 用于导读，不自动成为所有 Agent 的通用契约。
- `docs/knowledge/` 用于理解设计原因；Draft 或历史阶段说明不能直接升级为当前强制规则。

发现差异先明确“当前代码行为”和“规范预期”。安全、权限、契约类冲突必须标记并交人工裁决，不能只改文档将偏差合法化，也不能照着旧设计直接修改代码。生产可用性以相应专项的真实验证证据为准。
