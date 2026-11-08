# reference_agent

普通工具 Agent 的参考组合根。先读 [Agent 开发指南](../../../../docs/standards/runtime-agent-development-guide.md)，再按本例学习受信身份、Context、受管模型与只读工具装配；它不是 Workspace、MCP 或复杂委派的完整模板。

## 入口与模块

- [agent.py](agent.py)：`get_agent(config)` 区分探测与执行，`_build_agent()` 按本次运行事实装配模型、工具、middleware 和追踪。
- [tools.py](tools.py)：只读业务工具 `read_reference`。
- [prompts.py](prompts.py)：业务指令。
- [graphs/reference_agent.py](../../graphs/reference_agent.py)：稳定导出；正式与 demo JSON 均注册本图。

schema 探测不取真实模型连接，探测图不能执行任务。正式执行读取已验证的 `langgraph_auth_user`，校验 Context 与策略，通过受管模型引用取得连接；演示默认模型 ID 不替代平台模型目录。不得缓存带其他用户身份、模型连接或资源的 graph。

## 装配要求

`RuntimeConfigMiddleware` 同时约束模型可见工具与真实调用。组合根还接入 Token/调用次数/Run 时间预算、Plan、错误分类、消息队列及按配置启用的隐私与循环检测；精确顺序以 [装配测试](../../../../tests/services/reference_agent/test_middleware_order.py) 为准。

`read_reference` 的重试仅覆盖明确的只读连接失败。正式模型容错来自受管 bundle policy；测试用 fallback/retry 注入不属于客户端配置。未知异常、权限、取消和隐私失败不能伪装成功。Context 当前不接受 `tools`；工具目录和签名禁用策略沿公共 Runtime 规则。

## 测试与接入边界

在应用目录运行：

```bash
uv run pytest tests/services/reference_agent -q
uv run pytest tests/services/test_schema_introspection.py -q
```

本地模型注入参考 [test_agent.py](../../../../tests/services/reference_agent/test_agent.py) 的 `test_get_agent_accepts_explicit_fake_model_and_runtime_context`：使用测试支持的 `BindableFakeChatModel` 和 `configurable._runtime_model`。不要直接替换成不支持 `bind_tools()` 的 FakeListChatModel，也不要把测试身份注入带入正式请求。

重点读受信身份逐 Run 生效、Context 覆盖、策略拒绝、无身份失败和拓扑稳定的断言。拓扑稳定不等于可跨用户复用实例。测试源码不是运行结果；正式接入仍需 [平台链路验证](../../../../docs/standards/runtime-service-onboarding-and-verification.md)。
