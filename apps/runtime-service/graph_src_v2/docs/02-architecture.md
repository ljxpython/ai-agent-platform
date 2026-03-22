# LangGraph v2 架构说明（纯 Graph-Native）

## 作用范围

- `graph_src_v2` 是 `runtime-service` 下独立维护的执行层。
- 目标是保持一个统一且简单的心智模型：`已编译 graph 入口 + RuntimeContext`。

## 核心约定

- 每个 agent 模块对外导出 graph 入口，供 `langgraph.json` 注册。
- 运行时参数统一通过 `context` 传入，并由 `RuntimeContext` 约束字段结构。
- `config` 只用于执行控制参数，例如 `recursion_limit`，不承担业务运行时配置的主入口职责。

## 关键目录

- `graph_src_v2/langgraph.json`：graph 注册表、HTTP app 挂载点、CORS 与 `.env` 加载入口。
- `graph_src_v2/runtime/context.py`：共享 `RuntimeContext` 定义，约束模型、工具、租户等运行时字段。
- `graph_src_v2/runtime/options.py`：合并 `context`、`configurable`、环境变量与鉴权上下文，生成最终运行配置。
- `graph_src_v2/runtime/modeling.py`：按模型组配置解析模型，并绑定温度、`max_tokens`、`top_p` 等运行时参数。
- `graph_src_v2/tools/registry.py`：统一装配内建工具与 MCP 工具。
- `graph_src_v2/services/`：业务服务模块目录（推荐承载生产/业务智能体能力）。
- `graph_src_v2/agents/assistant_agent/graph.py`：默认 assistant graph 入口，也是当前推荐范式。
- `graph_src_v2/agents/assistant_agent/graph_legacy.py`：历史 assistant 入口，仅保留兼容与参考价值。
- `graph_src_v2/agents/deepagent_agent/graph.py`：deepagent graph 入口。
- `graph_src_v2/agents/personal_assistant_agent/graph.py`：subagent / supervisor 协作范式入口。

说明：

- `agents/` 作为 demo/范例保留。
- 新增业务能力建议落在 `services/`，目录规范见 `docs/07-service-modularization.md`。

推荐模板参考：

- `graph_src_v2/agents/assistant_agent/graph.py`
- `graph_src_v2/agents/deepagent_agent/graph.py`
- `graph_src_v2/agents/personal_assistant_agent/graph.py`

流程文档参考：

- `docs/archive/02-runnableconfig-vs-serverruntime.md`
- `docs/04-agent-scaffold-templates.md`
- `docs/05-template-to-runnable-agent-10min.md`

## 运行时流程

1. LangGraph 根据 `langgraph.json` 定位 graph 入口与自定义 HTTP app。
2. graph 在运行时读取 `runtime.context`，并结合 `config` 进入统一解析链路。
3. `build_runtime_config(config, context)` 生成本次执行的有效配置。
4. 运行时根据配置解析模型、工具、MCP 开关等能力。
5. graph 使用本次执行所需的模型和工具，调用内部 agent 或 deepagent 完成任务。

## 多 Graph 设计规则

- `assistant`、`deepagent_demo` 等 graph 共享同一套运行时约定。
- `graph_entrypoint.py` 仍保留兼容导出，但默认注册入口已经统一收敛到 `assistant`。
- 模型切换、工具白名单、MCP 开关都应由运行时参数驱动，而不是写死在部署配置中。
- `deepagent_demo` 当前保留静态 `skills` / `subagents` 列表，以降低维护复杂度。

## 启动示例

```bash
uv run langgraph dev --config graph_src_v2/langgraph.json --port 8123 --no-browser
```
