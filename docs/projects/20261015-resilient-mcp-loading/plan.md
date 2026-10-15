# 弹性 MCP 工具装配与运行时解耦保护 - 整体方案

## 背景

当前平台在集成 MCP（Model Context Protocol）工具时，存在致命的**脆弱性耦合与单点故障扩散**问题：
1. **装配期自爆反模式**：在 `apps/runtime-service/src/runtime_service/tools/mcp.py` 的 `load_mcp_tools` 中，代码通过 `await client.get_tools(server_name=server_key)` 发现远程工具。若外部 MCP 服务宕机、网络超时或临时不可用，未受保护的调用会直接向上抛出底层异常（如 `httpx.ConnectError` 或 `httpx.TimeoutException`），导致整个 Agent 初始化过程彻底瘫痪。
2. **硬编码的强一致性检查**：当前存在极其生硬的逻辑 `if names - set(actual): raise RuntimeResolutionError("runtime.mcp.required_unavailable")`。当远程 MCP 服务的工具名称有轻微调整、工具缺失或未能全部就绪时，Runtime 会主动抛出异常自杀，直接拒绝为用户提供服务。
3. **运行时异常未捕获导致链路崩溃**：工具调用期间如果遇到外部网络抖动或远端 5xx，部分非 transport 异常容易逃逸，导致 LangGraph 节点抛错并触发顶层的 `runtime.execution_failed`。

而在工业级项目（如 `/Users/lijiaxin/PyCharmMiscProject/research/open-swe`）中，成熟的做法是**“外部集成工具作为可选增强，其可用性绝不应阻断核心 Agent 的正常运转”**。

## 目标

1. **装配期故障隔离（Discovery Fault Isolation）**：外部 MCP 服务连不上、握手超时、工具缺失时，一律记录警告日志（Warning）并平滑降级，返回空列表或可用子集，绝对不打断 Agent 的初始化。
2. **去业务化移植 OpenSWE 容错设计**：借鉴 OpenSWE 的 `_load_tools` 与 `_wrap_tool` 思想，去除其特有的 Workspace、OAuth、Multi-tenant 等定制业务属性，将纯粹的容错与错误转换机制无缝移植入平台。
3. **运行时内化（Runtime Execution Graceful Degradation）**：强化所有 MCP 工具的 `handle_tool_error` 机制，将运行期网络断连、调用超时与服务端异常规范化为 `ToolMessage(status="error")`，使大模型能够自适应降级处理，彻底消除 `runtime.execution_failed`。

---

## 方案设计

### 整体架构

```
[Agent Build / Request]
        │
        ▼
[load_mcp_tools]
        │
        ├─► [Safe Connection & Discovery] (OpenSWE _load_tools 思想)
        │      ├─ 设定超时 (asyncio.wait_for, 默认 10s)
        │      ├─ try...except 拦截所有网络/握手/服务异常
        │      └─ 发生故障: logger.warning() 记录日志，降级返回 []
        │
        ├─► [Relaxed Tool Matching] (废除 names - set(actual) 强校验)
        │      ├─ 获取实际工具 set(actual)
        │      ├─ 计算交集 selected = [t for t in tools if t.name in names]
        │      └─ 缺失工具记 warning，不阻断 Agent 构建
        │
        └─► [Runtime Resilient Wrapper] (OpenSWE _wrap_tool 思想)
               ├─ 绑定 handle_tool_error
               ├─ 捕获 ToolException, TimeoutError, ConnectError
               └─ 输出给 LLM: "MCP tool {name} call failed: ... Continue without it."
```

### 关键改动点

#### 1. 外部 MCP 工具获取故障隔离与超时保护
- **文件：** `apps/runtime-service/src/runtime_service/tools/mcp.py`
- **改动：**
  在调用 `client.get_tools(server_name=server_key)` 时，外包 `asyncio.wait_for(..., timeout=10.0)` 并用 `try...except Exception as exc` 严密包裹。
- **理由：**
  去业务化移植 OpenSWE `_load_tools` 的隔离逻辑，避免外部依赖服务不可达时拖垮主服务。

#### 2. 移除工具缺失的强制中断异常
- **文件：** `apps/runtime-service/src/runtime_service/tools/mcp.py`
- **改动：**
  删除 `if names - set(actual): raise RuntimeResolutionError("runtime.mcp.required_unavailable")`。改为：
  ```python
  missing = names - set(actual)
  if missing:
      logger.warning("Requested MCP tools missing from %s: %s", server_key, sorted(missing))
  selected = [tool for tool in tools if tool.name in names]
  ```
- **理由：**
  遵循鲁棒性原则（Robustness Principle），系统应当对外部输入的微小差异宽容，只挂载实际可用的工具。

#### 3. 增强工具运行时错误处理与转化
- **文件：** `apps/runtime-service/src/runtime_service/tools/mcp.py`
- **改动：**
  对齐 OpenSWE 中对工具 `handle_tool_error` 的处理。在 `handle_error(exc, ...)` 中全面覆盖超时、网络连接重置及未知异常，转化为友好、结构化的错误字符串，确保触发 LangChain 的工具错误内化机制（返回 `status="error"` 的消息），而不是将异常抛出给状态机。
- **理由：**
  避免大模型在执行单点工具失败时整个会话崩溃报错。

---

## 链路影响

### 受影响的调用链路
```
Platform Web → Platform API → Runtime Service (load_mcp_tools) → Remote MCP Gateway
```
- **改动前**：Remote MCP Gateway 异常 → `load_mcp_tools` 抛异常 → Runtime Service 500 / Agent 运行失败。
- **改动后**：Remote MCP Gateway 异常 → `load_mcp_tools` 拦截并记日志 → Runtime 正常加载基础工具 → Agent 正常运行。

### 契约变更
- **Runtime 工具装配契约**：
  不再对外抛出 `runtime.mcp.required_unavailable` 致命异常；当外部 MCP 服务不可达或缺失工具时，降级为空或部分工具，调用方始终能够正常启动 Agent 会话。

---

## 风险和依赖

- **风险 1：已有单测断言了 `required_unavailable` 异常**
  - **应对：** 检查 `tests/` 下针对 `load_mcp_tools` 的单元测试，将期望“缺失工具抛错”的测试用例重构为断言“平滑降级并记录 Warning，返回实际可用工具”。
- **风险 2：大模型在工具缺失时可能会产生幻觉**
  - **应对：** 系统提示词中已有工具列表约束，若工具未注入模型上下文，模型根本不会感知到该工具的存在，自然不会主动调用；若运行时调用失败，通过 `ToolMessage(status="error")` 明确告知工具不可用，引导其基于常识回答。

---

## 实施计划

1. **Phase 1: 契约与装配隔离改造**
   - 改造 `load_mcp_tools` 的连接和工具检索逻辑，加装超时与 `try...except` 故障隔离。
   - 移除 `required_unavailable` 自杀逻辑，改为宽松交集与 warning 日志。
2. **Phase 2: 运行时错误捕获与降级包装**
   - 完善 `handle_tool_error` 与 `_read_only_transport`，确保所有网络抖动和超时均能优雅内化。
3. **Phase 3: 单元测试重构与全链路验证**
   - 适配既有单测用例，新增模拟 MCP 离线、超时、部分工具缺失的容错单测。
   - 联调验证 Web 与 Runtime 端到端表现。
