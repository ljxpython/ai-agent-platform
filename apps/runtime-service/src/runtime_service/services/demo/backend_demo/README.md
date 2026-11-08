# backend_demo

Backend 装配的单项机制示例，仅在 `langgraph.demo.json` 注册；入口 [agent.py](agent.py) 的 `get_agent(config)`。

## 两条资源路径

- 显式本地测试身份：使用 `StateBackend`，可注入测试 checkpointer。
- 已验证的非本地身份：通过 `resolve_resource_binding(..., "backend")` 取受信绑定，要求 `graphharbor_workspace` provider、thread_id 和绝对 `GRAPHHARBOR_WORKSPACE_ROOT`，再调用公共 `build_deepagent_workspace()`。

因此本例并非始终进程内存储。初始化失败不静默回退；客户端不能指定资源或凭据。实际文件工具为 ls/read_file/write_file/edit_file/delete_file/glob/grep，不提供 execute 或 task。

## 能借鉴什么

借鉴显式装配、线程资源绑定和失败关闭。代码通过模块级 `register_harness_profile` 关闭默认子 Agent，是现存教学实现，**不要把修改全局 profile 作为新生产 Agent 的设计方式**；使用当前生产组合根的显式角色声明。

本例也不是完整受管模型与预算模板；需要文件执行、正式模型、停止与恢复时参考 [Showcase](../showcase_demo/README.md) 及 [开发指南](../../../../../docs/standards/runtime-agent-development-guide.md)。

## 验证

不会默认注入 fake 模型。测试显式使用 `_runtime_test_local_auth`、`_runtime_test_model` 和可选测试 saver，具体配置见 [R4 测试](../../../../../tests/services/test_r4_capability_demos.py)。

```bash
# 在 apps/runtime-service 目录
uv run pytest tests/services/test_r4_capability_demos.py -q
```

阅读同线程重建保持文件、跨线程隔离、初始化失败、不允许 task/execute 和伪造调用拒绝的断言。这些本地测试不替代真实 Worker、存储后端、租户和资源清理验收。
