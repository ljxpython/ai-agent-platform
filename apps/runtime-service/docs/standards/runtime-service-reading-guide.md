# Agent 开发案例与资料导航

> 目的：让开发者知道先读什么、参考哪种案例、查哪个官方 API。
> 2026-11-08 已核对下面的本地入口和主要案例源码。案例测试未在本轮重跑，链接存在不等于运行通过。

## 必读路径

| 顺序 | 文档 | 读完应能回答 |
|---|---|---|
| 1 | [Agent 设计与开发指南](runtime-agent-development-guide.md) | 选哪种 Agent、模块如何划分、从设计到平台接入要做什么 |
| 2 | [开发范式与规则](runtime-service-development-standard.md) | 信任边界、工具/资源、失败语义及相关能力约束是什么 |
| 3 | 本页的所选案例源码与测试 | 具体如何装配、哪些只是演示、怎样验证 |
| 4 | [运行与验证](runtime-service-onboarding-and-verification.md) | 用哪个环境、跑哪些检查、哪些证据尚不具备 |

无需先通读全部 knowledge，也不要求为了简单工具 Agent 学完所有文件/子 Agent 能力。

## 案例选择表

以下案例 README 已按当前源码修订用途、接线和限制；先读导读，再对照源码与测试，不能只复制片段。

| 需求 | 源码入口 | 测试入口 | 学什么 / 不可直接照搬什么 |
|---|---|---|---|
| 普通工具 Agent | [reference_agent/agent.py](../../src/runtime_service/services/reference_agent/agent.py)、[tools.py](../../src/runtime_service/services/reference_agent/tools.py) | [reference 测试](../../tests/services/reference_agent/)、[schema 探测](../../tests/services/test_schema_introspection.py) | 受信身份、Context、模型解析、显式装配和只读工具；不要复制测试身份、演示模型 ID 或按早期说明缓存带运行身份的图 |
| 固定流程/审批恢复 | [workflow_demo](../../src/runtime_service/services/demo/workflow_demo/)：先 schemas/workflow，再 agent | [Workflow 测试](../../tests/services/workflow_demo/test_agent.py) | State、节点、条件分支、最新消息、interrupt/resume 和已完成步骤不重复；本地内存恢复不等于真实 Worker 重启恢复 |
| Deep Agent 的最小机制 | [deep_agent_demo/agent.py](../../src/runtime_service/services/demo/deep_agent_demo/agent.py) | [R4 机制测试](../../tests/services/test_r4_capability_demos.py) | StateBackend、只读 Skill、受限 summarizer；fake 模型与测试配置不作为正式平台接入代码 |
| MCP 单项机制 | [mcp_demo/loader.py](../../src/runtime_service/services/demo/mcp_demo/loader.py)、[agent.py](../../src/runtime_service/services/demo/mcp_demo/agent.py) | [R4 机制测试](../../tests/services/test_r4_capability_demos.py) | 本地 stdio 与受信 HTTP 绑定、工具允许列表/冲突；正式业务复用公共 loader，fake Server 不证明远端可用 |
| Backend 单项机制 | [backend_demo/agent.py](../../src/runtime_service/services/demo/backend_demo/agent.py) | [R4 机制测试](../../tests/services/test_r4_capability_demos.py) | 本地 StateBackend 与非本地受信 Workspace 绑定两条路径；资源分支存在不等于真实 Worker/沙箱验收 |
| 文件/工具/审批/子 Agent 的组合 | [Showcase agent.py](../../src/runtime_service/services/demo/showcase_demo/agent.py)、[backend.py](../../src/runtime_service/services/demo/showcase_demo/backend.py)、[subagents.py](../../src/runtime_service/services/demo/showcase_demo/subagents.py) | [Showcase 测试](../../tests/services/showcase_demo/) | 线程资源、角色权限、审批、真实工具与探测；按能力读取，不复制整个销售报表业务或全部工具 |
| 复杂业务能力的现有接线 | [DearFlow agent.py](../../src/runtime_service/services/dearflow_agent/agent.py)、[服务目录](../../src/runtime_service/services/dearflow_agent/) | [DearFlow 测试](../../tests/services/dearflow_agent/) | 调研、技能、记忆等能力如何接入当前公共层；它是完整业务实现，不是所有新 Agent 的最小模板 |

**案例限制：** reference 按运行事实构图；Workflow 保留本地 InMemorySaver；Deep/MCP/Backend 是机制案例，必须显式注入测试身份/模型，且未完整接入正式四图的全部公共能力。注册与本地测试不代表生产验收。具体入口和限制已在各案例 README 中说明。

当前注册层见 [graphs/](../../src/runtime_service/graphs/)；Showcase/DearFlow 的入口还包含调度/后台完成包装，不能把旧“只重导出”描述理解为所有图的当前实现。

## 按能力追加阅读

| 当前任务 | 现行规则/入口 | 对照源码或测试 |
|---|---|---|
| 身份、Context、模型选择 | [开发指南生命周期](runtime-agent-development-guide.md#5-组合根必须理解的生命周期) | [runtime/contracts.py](../../src/runtime_service/runtime/contracts.py)、[resolver.py](../../src/runtime_service/runtime/resolver.py)、[modeling.py](../../src/runtime_service/runtime/modeling.py)、[runtime 测试](../../tests/runtime/) |
| 工具目录与图能力 | [开发指南接入步骤](runtime-agent-development-guide.md#6-从设计到接入的具体步骤) | [runtime/capabilities.py](../../src/runtime_service/runtime/capabilities.py)、[实际 capability 实现](../../src/runtime_service/services/dearflow_agent/capabilities.py) |
| 上下文/大结果/预算 | [上下文窗口管理](runtime-service-development-standard.md#上下文窗口管理)、[Run Token](runtime-service-development-standard.md#run-token-额度保护) | [摘要测试](../../tests/middlewares/test_conversation_offloading.py)、[输出预算测试](../../tests/middlewares/test_tool_output_budget.py)、[Token 测试](../../tests/middlewares/test_token_budget.py) |
| Plan Mode / 子角色权限 | [Plan 接入规则](runtime-service-development-standard.md#通用-plan-mode-接入) | [Plan 图测试](../../tests/services/test_plan_mode_graphs.py)、[Plan 安全测试](../../tests/middlewares/test_plan_mode_safety.py) |
| 文件/沙箱/取消 | [Workspace 规则](runtime-service-development-standard.md#workspace-执行目标与恢复)、[停止与资源](runtime-service-development-standard.md#通用会话停止与资源适配)、[沙箱手册](../../../../docs/runbooks/runtime-sandbox-node.md) | [workspace/](../../src/runtime_service/workspace/)、[workspace 测试](../../tests/workspace/) |
| 模型容错与工具失败 | [准备与重试装配](runtime-service-development-standard.md#准备与重试装配) | [模型容错组合测试](../../tests/services/test_model_resilience_composition.py)、[工具错误公共实现](../../src/runtime_service/tools/errors.py) |
| 隐私/追踪 | [隐私规范](model-context-privacy.md) | [PII 组合测试](../../tests/services/test_pii_composition.py)、[observability/](../../src/runtime_service/observability/) |
| 项目知识/MCP | [知识规范](project-knowledge-mcp.md) | [公共 MCP](../../src/runtime_service/tools/mcp.py)、[知识组合测试](../../tests/services/test_knowledge_composition.py) |
| 后台任务 | [后台接入](background-task-integration.md) | [公共后台工具](../../src/runtime_service/tools/background.py)、[后台完成包装](../../src/runtime_service/runtime/background_completion.py) |

需要设计原因时，按[knowledge 索引](../README.md#设计依据与历史资料)找对应专题。历史阶段的图数量、版本、路径、能力完成状态需单独核对，不能直接用来约束当前实现。

## 官方资料怎么查

### 查询顺序

1. 先查本项目指南、当前案例源码及测试，确定问题是框架机制还是平台约束。
2. 查 [pyproject.toml](../../pyproject.toml) 的声明和 [uv.lock](../../uv.lock) 的实际锁定版本。开发环境在本应用目录用 `uv sync --frozen` 安装所属依赖；不要为了照抄新示例升级依赖。
3. 用 `langchain-docs` MCP 搜索概念、教程和使用模式；用 `langchain-reference` MCP 搜索精确 Python 符号、参数和类型。先找真实路径/符号，再读对应页面。
4. 对照本地锁定版本的 API、已有调用和测试确认可用性。官网可能比锁文件新，尤其是 Deep Agents 的 State、Backend、Skills、子 Agent 和 middleware。
5. 若 MCP 不可用，使用下表的官方站点。第三方文章只补充理解；不能覆盖项目权限、错误和持久化契约。

### 问题到资料的映射

| 要解决的问题 | 官方资料 | 建议查询 |
|---|---|---|
| 普通 Agent 的构图与工具调用 | [LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents) / [create_agent API](https://reference.langchain.com/python/langchain/agents/factory/create_agent) | create_agent、context_schema、middleware、structured output |
| Tool 参数及受信运行上下文 | [Tools](https://docs.langchain.com/oss/python/langchain/tools) / [Runtime](https://docs.langchain.com/oss/python/langchain/runtime) | ToolRuntime、工具 schema、context 与 state 的区别 |
| 自定义横切行为 | [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) | before/after/wrap hooks、执行顺序、异常传播 |
| Agent 与确定流程如何选择 | [Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents) / [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api) | StateGraph、state/reducer、节点与条件边 |
| 审批、暂停和恢复 | [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) / [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | interrupt、Command、thread_id、重放与幂等 |
| Deep Agent 如何构建 | [Overview](https://docs.langchain.com/oss/python/deepagents/overview) / [create_deep_agent API](https://reference.langchain.com/python/deepagents/graph/create_deep_agent) | 内置能力、backend、subagents、state/context |
| 文件与存储应该放哪里 | [Backends](https://docs.langchain.com/oss/python/deepagents/backends) | StateBackend、CompositeBackend、SandboxBackendProtocol |
| 如何组织技能与委派 | [Skills](https://docs.langchain.com/oss/python/deepagents/skills) / [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents) | 按需加载、角色工具集、状态/上下文隔离 |

资料用途是解释框架机制；平台实际使用 GraphHarbor、现有模型目录与追踪实现，不因官网示例使用其他部署/观测产品就更换平台组件。

### 查询结果怎样落到开发里

在新 Service README 或所属项目记录里简短注明：选用的模式、参考案例/测试、关键 API 的来源与核对版本、未覆盖的能力。例如“采用 reference_agent 的受管模型接入，工具只读；未接 Workspace、委派和调度”。不要只留下“参考官方最佳实践”而没有具体入口。

本页官方入口已通过 docs/reference MCP 发现与核对；这不构成本地代码兼容性或真实运行测试通过的声明。
