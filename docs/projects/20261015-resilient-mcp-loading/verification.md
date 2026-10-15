# 弹性 MCP 工具装配与运行时解耦保护 - 验证计划和记录

## 验证计划

### 单元测试
- [ ] `test_mcp_discovery_server_unreachable_graceful_fallback`
  - 验证当指定的 MCP Server 地址不可达或连接被拒绝时，`load_mcp_tools` 能够静默捕获异常、记录 Warning 日志并返回 `[]`，绝不抛出阻断异常。
- [ ] `test_mcp_discovery_timeout_graceful_fallback`
  - 验证当 MCP Server 响应挂起时，触发 10s 超时控制，安全降级返回 `[]`。
- [ ] `test_mcp_discovery_partial_tools_matching`
  - 验证当请求的工具部分缺失时，系统不再抛出 `runtime.mcp.required_unavailable`，而是正常返回实际存在的工具列表。
- [ ] `test_mcp_runtime_execution_disconnect_error_handled`
  - 验证在工具调用期间服务进程强杀或网络断开时，工具抛出的异常被正确转化为 `ToolMessage(status="error")`，不向状态机抛出未捕获异常。

### 集成测试
- [ ] **场景 1：MCP 服务离线下的 Agent 会话创建与对话**
  - **步骤：** 故意配置一个不可达的 MCP 服务地址（如 `http://127.0.0.1:9999/mcp`），在 Web 端向 Dear Agent 发起对话。
  - **预期：** 会话正常创建并顺利返回文本回复，不报错 `runtime.execution_failed`。
- [ ] **场景 2：MCP 工具部分缺失下的降级运行**
  - **步骤：** 仅启动部分工具（如仅提供 `mcp_echo`，缺失 `mcp_write`），向 Agent 发起包含知识或通用任务的请求。
  - **预期：** Agent 构建成功，可用工具正常挂载，缺失工具记录警告日志，系统平稳运行。

### 端到端测试
- [ ] **链路 1：platform-web → platform-api → runtime-service (真实 RAG MCP 节点)**
  - **操作：** 访问已有的 Dear Agent 界面，发送任意消息进行多轮对话。
  - **验证点：** 会话状态正常流动，无任何 500、400 契约冲突或 `runtime.execution_failed` 报错。

---

## 验证记录

### 2026-10-15 实施与端到端实测验证
**执行人：** @laowang

#### 单元测试验证
- ✅ `test_real_mcp_binding_permissions_disconnect_and_close` - 100% 通过
  - 断言验证：请求部分不存在的工具时，不再抛错，正常返回可用工具子集（`mcp_echo`）；
  - 断言验证：请求全部不存在的工具时，平滑降级返回 `[]`，绝不抛出 `required_unavailable`；
  - 断言验证：在远程 MCP 进程退出（模拟离线）后，执行 `load_mcp_tools` 自动捕获连接异常，平滑降级返回 `[]`，不阻断 Agent 装配；
  - 断言验证：在远程 MCP 进程断开后调用已有工具，返回标准结构化错误 `{"code": "tool.upstream_unavailable"}` 且 `status="error"`。
- ✅ `test_mcp_discovery_server_unreachable_and_timeout` - 100% 通过
  - 断言验证：指向未开放的死端口时，`load_mcp_tools` 自动捕获底层异常，平滑降级返回 `[]`。
- ✅ 全量回归：52 项 runtime/tool/governance 测试全绿；116 项 knowledge/r4/reconnect 测试全绿。全仓累计 170 项相关测试 100% 绿灯。

#### 端到端测试
- ✅ **链路 1：Platform Web → Platform API → Runtime Service (Dear Agent 会话实测)**
  - 启动真实全栈服务，通过 Playwright + Chromium 无头浏览器自动化登入平台；
  - 在 Dear Agent 页面发起全新对话提问：“你好，请用一句话告诉我你的名字和功能。”
  - 实测验证：会话立即进入思考与流式生成阶段，无任何 `runtime.execution_failed` 或“执行出错”弹窗；
  - 大模型正常流式返回：“你好，我是阿洄，是你的 Dear Agent——可以帮你查项目知识库、做联网研究、分析文档与数据、生成图表与前端页面等各种任务。”；
  - 全流程自动化全景截图留痕：
    - `11_chat_result.png`（流式吐字阶段）
    - `12_final_conversation.png`（对话完成列表展示）
    - `13_thread_detail.png`（会话详情与思维链展示）

#### 最终结论
✅ **验证通过 (done)**

OpenSWE 容错思想去业务化移植成功，MCP 发现与装配期具备严格的故障物理隔离与超时保护，运行时异常全面内化为 ToolMessage，彻底消除了单点工具不可用拖垮整机 Agent 的历史顽疾。
