# 开发范式

## 目标
总结 Showcase Demo 的最小、可复制实现模式，指导新增 Agent Service 及其运行时能力。

## 方案设计
- 组合根唯一：`agent.py` 负责身份、Context、模型、Middleware 和工具装配。
- 业务边界清晰：prompts 纯函数化，tools 只放真实业务动作，backend 只处理资源边界。
- 优先官方能力：Agent 循环、Todo、Filesystem、Skills、Subagent、HITL、流式和持久化不重复封装。
- 权限显式收缩：角色工具集、Context 校验、tenant/project/thread 作用域和审批边界必须可追踪。
- Graph 注册唯一：`langgraph*.json -> graphs -> services/<name>/agent.py`。
- 测试分层：组合测试验证装配，集成测试验证 Agent Server，E2E 验证真实链路。

## 任务拆分
- [ ] 从 Showcase README 提炼标准模板和反例。
- [ ] 编写 Agent、Tool、Backend、Middleware、Skill、Subagent 小节。
- [ ] 增加安全、资源隔离、错误和可观测性检查清单。

## 验证要求与记录
- [ ] 新增 Demo 可按范式完成 import、composition、integration 验证。
- [ ] 文档示例命令在应用目录可执行。

## 状态
规划中
