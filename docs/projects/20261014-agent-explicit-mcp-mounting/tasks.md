# Agent 显式挂载多 MCP 与 MultiServerMCPClient 极简治理方案 - 任务拆分

## Phase 1: 基础建设与极简加载器重构

### Task 1.1: 重构 `tools/mcp.py` 为极简原生适配器
- **改动内容：**
  - 精简 `load_mcp_tools` 函数实现，移除繁复胶水逻辑，紧凑且贴合官方 `MultiServerMCPClient`。
  - 支持传入 `target_servers: list[str] | tuple[str, ...] | None`，使用 `client.get_tools(server_name=server_key)` 精准捞取指定 Server 的工具。
  - 提取并保留必要的错误处理（`tool_error_content`）与结果拦截器（`knowledge_result_interceptor`）。
- **代码位置：** `apps/runtime-service/src/runtime_service/tools/mcp.py` → `load_mcp_tools()`
- **预期结果：** 函数签名清晰，只根据显式声明的 Server 列表提取工具，单文件代码精炼且易维护。
- **验证项：** 运行 `pytest apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py` 验证基本加载与错误处理。
- **预计：** 0.5 天
- **状态：** `[x]` 已完成

### Task 1.2: 清理 `mcp_config.py` 中的静态列表与解耦
- **改动内容：**
  - 彻底删除 `DYNAMIC_KNOWLEDGE_TOOLS` 静态元组。
  - 在 `tools/knowledge.py` 中集中定义业务常量 `KNOWLEDGE_MCP_TOOLS`。
  - 重构 `dynamic_knowledge_tools()`，使其按需懒加载 `KNOWLEDGE_MCP_TOOLS`，消除了与底层 `mcp_config` 的反向污染与假硬编码。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/mcp_config.py`, `apps/runtime-service/src/runtime_service/tools/knowledge.py`
- **预期结果：** 代码库核心配置中没有写死的 MCP 业务工具名称。
- **验证项：** 运行测试验证动态知识库工具反射正常。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成

---

## Phase 2: Agent 显式声明与跨服务契约对齐

### Task 2.1: 在 `dearflow_agent` 中显式声明挂载目标
- **改动内容：**
  - 在 `dearflow_agent/agent.py` 模块顶部显式定义 `REQUIRED_MCP_SERVERS = ("knowledge",)`。
  - 在 `create_agent` 工厂函数中，显式将 `target_servers=REQUIRED_MCP_SERVERS` 传递给 `load_mcp_tools`。
  - 工具装配逻辑从无差别全局池改为明确的针对性装配。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py` → `create_agent()`
- **预期结果：** 该 Agent 无论外部环境有多少个 MCP Server，启动时绝对只加载并注入 `knowledge` 服务的工具。
- **验证项：** 运行 `pytest apps/runtime-service/tests/services/dearflow_agent/test_agent.py` 全部 20 个测试通过。
- **预计：** 0.3 天
- **状态：** `[x]` 已完成

### Task 2.2: 优化 Agent 提示词，对齐 MCP 工具调用认知
- **改动内容：**
  - 在 Agent 系统提示词（`SYSTEM_PROMPT`）中，加入对知识库 MCP 工具的清晰调用指引：当被问及平台规范、架构设计、技术决策或业务流程时，优先主动检索知识库。
  - 明确各工具入参及使用场景，指导模型遵循 KISS 与精准检索原则。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`
- **预期结果：** 大模型在收到用户知识库相关提问时，能够主动、精准地触发工具调用，不再产生幻觉或盲猜。
- **验证项：** `test_agent_system_prompt_references_knowledge_capabilities` 测试通过。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成

---

## Phase 3: 验证和优化

### Task 3.1: 单元测试补齐与多 Server 隔离验证
- **改动内容：**
  - 编写专门的多 Server 隔离测试用例 `test_load_mcp_tools_with_target_servers`：在环境中同时配置 `knowledge` 与 `other_unrelated_server` 两个 MCP Server，断言当声明 `target_servers=["knowledge"]` 时，绝对不加载无关 Server 的工具，且精准返回知识库工具。
  - 修复 `test_knowledge_upload_http.py` 中测试夹具设置隔离问题（显式指定 `settings.knowledge_key_id = "knowledge-v1"`，避免本地开发环境 `.env` 干扰）。
- **代码位置：** `apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py`, `apps/runtime-service/tests/tools/test_knowledge_upload_http.py`
- **预期结果：** 单测 100% 覆盖多 Server 隔离断言。
- **验证项：** `pytest apps/runtime-service/tests/services/dearflow_agent/test_mcp_tools.py` 与 `test_knowledge_upload_http.py` 全绿通过。
- **预计：** 0.3 天
- **状态：** `[x]` 已完成

### Task 3.2: Final 全量回归与端到端验证
- **改动内容：**
  - 运行 `apps/runtime-service` 全量服务与工具测试套件（106 passed, 0 failed）。
  - 运行 `apps/platform-api` 知识库绑定与迁移测试（6 passed, 0 failed）。
- **代码位置：** 全仓库
- **预期结果：** 所有现有测试与新测试无损通过，多 Server 隔离和知识库挂载逻辑稳固。
- **验证项：** 执行完整回归命令全部通过。
- **预计：** 0.2 天
- **状态：** `[x]` 已完成

---

## 进度追踪
- [x] Phase 1 完成（tools/mcp.py 极简重构与清理）
- [x] Phase 2 完成（Agent 显式声明与 Prompt 优化）
- [x] Phase 3 全量验证通过（多 Server 隔离单测与全量回归）
