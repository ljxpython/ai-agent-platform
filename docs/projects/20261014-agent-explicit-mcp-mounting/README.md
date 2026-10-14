# Agent 显式挂载多 MCP 与 MultiServerMCPClient 极简治理方案

## 项目概述
- **时间：** 2026-10-14 至 2026-10-16
- **目标：** 基于 LangChain 官方 `MultiServerMCPClient` 原生多 Server 纳管能力，坚决贯彻 KISS 原则剔除过度设计；建立 Agent 维度的 MCP 显式按需挂载（Explicit Mounting）与工具隔离机制，让专用 Agent 只感知被显式授权的专属 MCP 服务，彻底杜绝所有工具大杂烩注入大模型导致的 Token 浪费与幻觉误调。
- **负责人：** @lijiaxin (老王技术流督导)
- **模板类型：** 标准模板
- **状态：** 已完成

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：**
  - `runtime-service`：重构 `tools/mcp.py` 为原生简洁适配层，按 `server_name` 精准捞取工具；Agent 工厂（如 `dearflow_agent/agent.py`）显式声明与按需挂载；彻底移除 `mcp_config.py` 中的硬编码静态工具列表。
  - `platform-api`：在 Agent / Thread 资源绑定（`runtime_resource_bindings`）中打通 `enabled_mcp_servers` 声明，实现控制面细粒度服务级授权与下发。
  - `platform-web`：Agent 工具展示与配置界面对齐 Server 命名空间，让用户清晰看到 Agent 显式挂载了哪些 MCP 服务。
- **改动级别：** 链路改动（跨服务契约与运行时工具装配链路演进）
- **预计工作量：** 1.5 人天

## 关键决策
1. **全面依托 LangChain 官方 `MultiServerMCPClient` 原生能力，严禁重复造轮子**：
   官方已原生实现多协议连接池（SSE/Streamable HTTP/Stdio）、Schema 动态反射为 `BaseTool`、以及 `client.get_tools(server_name=...)` 过滤功能。代码结构保持单文件极简 `tools/mcp.py`，绝不搞冗余的 `loader.py`、`client.py` 多层空转封装。
2. **Agent 显式按 Server 声明依赖（Explicit Server-Level Mounting）**：
   抛弃“只要存在就全部灌给模型”的糊涂做法。Agent 必须在代码定义（`REQUIRED_MCP_SERVERS = ["knowledge"]`）或会话配置（`enabled_mcp_servers`）中显式指定目标 MCP Server，由 `MultiServerMCPClient.get_tools(server_name=...)` 精准提取。
3. **彻底清除静态硬编码**：
   废除 `DYNAMIC_KNOWLEDGE_TOOLS` 等在 Runtime 中的静态数组残留，所有工具元数据和 Schema 100% 由 MCP Server 在线反射与平台 Catalog 数据库表驱动。
