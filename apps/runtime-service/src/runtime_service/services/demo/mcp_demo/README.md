# mcp_demo

服务私有 MCP loader 的教学例，仅在 `langgraph.demo.json` 注册。阅读 [loader.py](loader.py) → [agent.py](agent.py)，理解官方 adapter、允许名单、名称冲突和资源绑定。

## 两条连接路径

- 本地测试：显式测试身份下用 stdio 启动 [fake_server.py](fake_server.py)，调用真实 MCP 协议，模型需另用 `_runtime_test_model` 注入。
- 已验证的非本地身份：`resolve_resource_binding(..., "mcp")` 要求 `mcp_http`，从服务端 `RUNTIME_MCP_CONNECTIONS_JSON` 取得 streamable_http 配置。

工具按 allowed_names 筛选，名称冲突拒绝，全部禁用时不连接。连接地址与凭据不由 Context、Prompt 或工具参数提供。

本地 loader 的 `required=False` 才允许加载失败返回空列表；非本地资源恢复失败不能套用这个测试选项。该教学 loader **不是正式公共 MCP 容错规范**：新业务优先复用 [tools/mcp.py](../../../tools/mcp.py)，其发现失败隔离、缺失工具过滤和运行错误投影见 [已完成专项](../../../../../../../docs/projects/20261015-resilient-mcp-loading/README.md)。资源授权、工具冲突和 annotation 校验仍是独立门禁。

## 验证与限制

测试入口为 [test_r4_capability_demos.py](../../../../../tests/services/test_r4_capability_demos.py)，冲突测试键为 `_runtime_test_mcp_conflict`，不是 `_mcp_conflict`。

```bash
# 在 apps/runtime-service 目录
uv run pytest tests/services/test_r4_capability_demos.py -q
```

测试覆盖实际 stdio 工具调用、allowlist、冲突、必需/可选失败和伪造调用拒绝。它不证明外部 MCP 可达，也未展示外部写工具审批。正式知识工具与安全要求见 [项目知识 MCP](../../../../../docs/standards/project-knowledge-mcp.md)；完整 Agent 接入仍按 [开发指南](../../../../../docs/standards/runtime-agent-development-guide.md)。
