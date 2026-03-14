# graph_src_v2 智能体开发团队规范（Playbook）

本文是团队在 `graph_src_v2` 下开发智能体的统一实践，目标是：

- 代码简单可维护
- 运行时能力可配置
- 在同一套运行时契约下选择合适模式

## 1. 总原则

- `config-first`：优先使用运行时配置驱动行为，不写死环境分支。
- `factory-light`：工厂函数只负责装配，不做重初始化。
- `dynamic + required tools`：平台工具动态加载，业务必备工具显式追加。
- 不强行统一成一种实现：`create_agent` / `LangGraph graph` / `deepagent` 按场景选。

## 2. 模式选型规则

### 2.1 什么时候用 create_agent

适用：

- 单智能体为主
- 线性对话流程
- 需要工具调用
- 需要 HITL、多模态、subagent 等增强能力，但不需要显式图编排

推荐方式：

- 用工厂函数 `make_graph(...)` 返回 `create_agent(...)`
- 通过 `build_runtime_config(...)` 统一解析模型与工具配置
- 通过 middleware 注入 HITL、多模态等横切能力

当前范例：

- `graph_src_v2/agents/assistant_agent/graph.py`

### 2.2 什么时候用 LangGraph graph

适用：

- 需要显式状态流
- 需要步骤切换、handoff、条件推进
- 需要把流程结构本身当成主要设计对象

推荐方式：

- 仍然沿用相同的运行时工厂入口：`make_graph(config, runtime)`
- 外层 graph 负责流程编排
- 具体状态推进可放在工具、middleware 或节点内部

当前范例：

- `graph_src_v2/agents/customer_support_agent/graph.py`
- `graph_src_v2/agents/customer_support_agent/tools.py`

说明：

- 当前这个范例在外层仍复用了 `create_agent(...)`，但它体现的是“显式流程/图式编排”这类开发思路。
- 团队后续若真要写更重的 `StateGraph`，也应沿用同一套 runtime config 解析方式，而不是脱离现有契约另起一套。

### 2.3 什么时候用 deepagent

适用：

- 复杂多步任务
- 强任务分解/规划能力
- 工具链较长，执行路径不固定
- 需要 skills / subagents / 文件系统产物

推荐方式：

- 用工厂函数 `make_graph(...)` 返回 `create_deep_agent(...)`
- 运行时只解析模型、工具和必要上下文
- `skills` / `subagents` 保持静态注册，降低复杂度

当前范例：

- `graph_src_v2/agents/deepagent_agent/graph.py`

## 3. 三种模式的共同基线

无论最终落到哪一种模式，统一基线都应保持一致：

1. 使用工厂函数签名

```python
async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    ...
```

2. 优先沿用统一运行时解析链路

```python
runtime_context = merge_trusted_auth_context(config, {})
options = build_runtime_config(config, runtime_context)
model = apply_model_runtime_params(resolve_model(options.model_spec), options)
tools = await build_tools(options)
```

3. 把模式差异放在“最终返回什么”这一层：

- `create_agent(...)`
- graph / 流程式 agent
- `create_deep_agent(...)`

也就是说，这三种模式不是完全割裂的三套体系，而是同一套 runtime contract 下的三种落地形式。

## 4. 工厂函数规范

推荐签名：

```python
async def make_graph(config: RunnableConfig, runtime: ServerRuntime) -> Any:
    ...
```

要求：

- 工厂函数负责装配，不做不必要重初始化。
- `RunnableConfig` 用于本次运行参数（模型、开关、工具等）。
- `ServerRuntime` 作为统一签名保留；当前大多数场景不直接使用它。
- 若当前场景不需要 `user/store`，可以 `del runtime`，但不要另起一套不兼容签名。

## 4.1 system_prompt 全局规则

统一规则：

- `runtime/options.py` 不再提供“前端不传时的全局默认提示词”
- 当前端/调用方未传 `system_prompt` 时，`options.system_prompt == ""`
- 每个 graph 必须在自己的 `graph.py` 内显式决定业务默认提示词

推荐写法：

```python
system_prompt = options.system_prompt or SYSTEM_PROMPT
```

如果该 graph 需要对外部 prompt 做更复杂处理，也必须在 graph 内完成，而不是回退到 runtime 层统一默认值。

说明：

- `SYSTEM_PROMPT` 属于业务 graph 的默认行为，不属于全局 runtime 的统一默认值
- 这样可以保证不同业务 graph 在前端不传 prompt 时，仍然各自按自己的业务语义运行
- 新 graph 禁止直接把 `options.system_prompt` 原样透传后假定它总会有默认值

## 5. 工具装配规范（重点）

统一采用“两段式装配”：

1) 动态平台工具（来自 `graph_src_v2/tools`）

```python
tools = await build_tools(options)
```

2) 本地必备工具（当前 agent 目录）

```python
tools.extend([...])
tools.append(...)
```

MCP 约定：

- 后续新增 MCP，默认也按“本地必备工具”处理
- 优先在当前服务/agent 内单独封装 helper，然后在 graph 中显式 `tools.extend(...)`
- 除非明确要求做成公共共享能力，否则不要先注册到公共 `mcp/` 模块

说明：

- 动态部分保证按配置启用/禁用能力。
- 本地必备部分保证关键业务能力稳定可用。
- 不再增加无意义中间封装层。

## 6. HITL（人机审核）规范

- 默认优先官方 `HumanInTheLoopMiddleware`。
- 不重复封装新的审批协议。
- 在 `langgraph dev` / 托管持久化环境，不在图内手动注入本地 checkpointer。
- 若未来使用更重的图编排模式，再单独评估是否用节点级 `interrupt(...)`。

## 7. assistant 历史实现说明

当前推荐样板：

- `graph_src_v2/agents/assistant_agent/graph.py`

历史实现：

- `graph_src_v2/agents/assistant_agent/graph_legacy.py`

要求：

- 新功能默认落在 `graph.py`
- `graph_legacy.py` 只保留兼容和参考价值

## 8. 开发流程（执行清单）

1. 明确业务场景，先做模式选型（`create_agent` / `LangGraph graph` / `deepagent`）
2. 落地工厂函数与统一运行时配置解析
3. 按“两段式装配”接入工具
4. 接入 HITL / 多模态等横切能力（若需要）
5. 验证：
   - 相关文件无语法错误
   - `compileall` 通过
   - 最小冒烟测试通过

补充：

- 若是业务服务开发，目录与边界请按 `docs/07-service-modularization.md` 执行。

## 9. 禁止事项

- 为了“看起来统一”强行让所有智能体都写成一种模式
- 为简单场景引入过重图编排
- 绕开 `build_runtime_config(...)` 自己重新发明一套配置解析
- 把历史实现 `graph_legacy.py` 继续当作默认新范式
