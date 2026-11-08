# deep_agent_demo

Deep Agents 的单项机制示例，仅在 `langgraph.demo.json` 注册。阅读 [agent.py](agent.py) 学习显式 Backend、Skills、受限角色；生产组合参考 [Showcase](../showcase_demo/README.md) 和 [开发指南](../../../../../docs/standards/runtime-agent-development-guide.md)。

## 实际装配

- `StateBackend` 承载 checkpoint 文件状态，不等于宿主 Workspace 或沙箱隔离。
- bundled Skill 位于 [skills/runtime-notes/SKILL.md](skills/runtime-notes/SKILL.md)，本例通过包内路径装配；生产资源路由参考 Showcase。
- 根文件工具仅开放 ls/read_file/glob/grep，按配置可委派 `summarizer`。
- summarizer 虽声明 `tools=[]`，其 Filesystem middleware 仍装配 read_file，不能理解为“完全没有文件能力”。权限需核对工具参数和 middleware 最终工具面。

## 身份、模型与验证

示例**不会默认使用 fake 模型**。无验证身份时只有显式 `_runtime_test_local_auth=True` 的本地测试路径；测试模型键为 `_runtime_test_model`，不是 reference 的 `_runtime_model`。不得把测试开关作为正式认证方式。

本例未完整接入正式四图的受管模型 bundle、预算及其他公共能力，不是可直接注册生产的新 Agent 模板。本地 checkpointer 与 fake 测试不能证明真实模型、持久 Workspace 或 Worker 恢复。

在应用目录执行：

```bash
uv run pytest tests/services/test_r4_capability_demos.py -q
```

重点读 [对应测试](../../../../../tests/services/test_r4_capability_demos.py) 中 Skill 只读、角色限制、真实 task 委派、子图 namespace 和伪造工具拒绝断言。环境见 [运行与验证](../../../../../docs/standards/runtime-service-onboarding-and-verification.md)。
