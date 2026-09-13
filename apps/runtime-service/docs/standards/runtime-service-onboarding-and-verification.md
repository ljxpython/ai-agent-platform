# Runtime Service 介入与验证

## 本地介入

```bash
cd apps/runtime-service
uv sync
docker pull python:3.13-slim
uv run graphharbor serve --config langgraph.demo.json --host 127.0.0.1 --port 8123
```

先运行不依赖外部服务的快速测试：

```bash
uv run pytest tests/services/showcase_demo -m "not integration and not e2e"
```

需要 Docker 隔离时运行 integration；需要真实模型或外部 MCP 时显式设置对应环境变量和 marker，凭据缺失必须失败并说明原因，禁止静默降级。

## 提交前检查

- Graph entrypoint 可导入，注册文件指向正确的 `get_agent`。
- 组合测试确认工具列表、Middleware 顺序、Subagent 权限和 Context 语义。
- integration 测试确认真实文件产物、退出码、隔离和资源限制。
- HITL 测试覆盖批准、拒绝、多 action 请求和 resume。
- 跨服务改动验证请求契约、错误码、事件顺序和 scope。
- 文档链接、命令、环境变量与代码一致。

## 故障定位顺序

先看 Graph 注册和 import，再看 Context/身份校验，再看 Middleware 和工具授权，最后看模型、Docker、PostgreSQL/Redis 等外部依赖。每次失败记录复现命令、日志摘要和边界归属。
