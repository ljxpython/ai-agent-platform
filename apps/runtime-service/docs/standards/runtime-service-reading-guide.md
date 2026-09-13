# Runtime Service 资料导航

## 先看哪里

| 目的 | 入口 | 你要找什么 |
| --- | --- | --- |
| 了解目录和部署入口 | `apps/runtime-service/README.md`、`langgraph*.json` | 启动方式、Graph 注册、环境变量 |
| 看标准实现 | `src/runtime_service/services/demo/showcase_demo/` | 组合根、工具、Backend、Skills、Subagent、HITL、MCP |
| 查当前规则 | `docs/standards/` | 本项目生效的边界、开发和验证要求 |
| 查设计依据 | `docs/knowledge/` | 为什么这样分层、契约和失败语义 |
| 查真实行为 | `tests/services/showcase_demo/`、`tests/runtime/` | 可执行断言、测试标记和边界 |

## knowledge 借鉴地图

- 目录与依赖方向：`13-runtime-service-target-code-layout.md`、`11-agent-service-directory-architecture.md`
- Context、契约和模型解析：`12-runtime-context-and-local-debug-architecture.md`、`14-runtime-contracts-and-resolution-design.md`
- Middleware 生命周期与错误：`15-runtime-middleware-lifecycle-and-failure-semantics.md`
- Graph、Thread、Backend、Checkpoint：`23-graph-thread-backend-checkpoint-lifecycle-design.md`
- 启动、关闭和 Graph 配置：`24-package-langgraph-startup-shutdown-design.md`
- Tool、MCP、副作用：`19-runtime-tool-capability-mcp-and-side-effect-design.md`
- Workspace、Skills、Subagent：`20-runtime-backend-workspace-skills-and-subagents-design.md`
- 可观测性：`16-runtime-observability-and-langfuse-design.md`
- 测试与跨服务契约：`25-runtime-testing-and-cross-service-contract-design.md`
- Platform 接入：`22-platform-runtime-contract-design.md`、`27-platform-runtime-integration-phased-design.md`

## 使用 MCP/外部资料查询

优先查询官方文档 MCP（LangChain、LangGraph、Deep Agents、MCP Server）；涉及 API、参数、版本或迁移时先查文档再写代码。查询结果只作为依据，最终以项目锁定版本、测试和本地实现为准。第三方文章只用于理解概念，不作为契约来源。
