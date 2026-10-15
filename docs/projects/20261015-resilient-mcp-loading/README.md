# 弹性 MCP 工具装配与运行时解耦保护 (Resilient MCP Loading)

## 项目概述
- **时间：** 2026-10-15 至 2026-10-16
- **目标：** 对标 OpenSWE 生产级容错设计并去业务化移植，实现 MCP 服务与工具的装配期故障隔离与运行时优雅降级，彻底杜绝单点 MCP 不可用导致 Agent 初始化崩溃与运行失败。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** done

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `runtime-service`
- **改动级别：** 链路改动（影响 Runtime 工具装配契约、错误隔离与降级行为）
- **预计工作量：** 1 人天

## 关键决策
1. **装配期故障物理隔离（去业务化移植 OpenSWE `_load_tools`）**：
   对外部 MCP Server 的连接发现与工具获取过程实施严格的异常拦截与超时控制。任何外部 MCP 服务挂死、握手超时、网络断开或鉴权失败，一律记录警告日志（Warning）并降级跳过（返回空工具列表），绝不允许单点故障中断 Agent 的构建过程。
2. **废除硬编码的强一致性校验**：
   彻底移除 `if names - set(actual): raise RuntimeResolutionError("runtime.mcp.required_unavailable")` 这种“缺一个工具就自爆”的反模式。改为对实际获取的工具与请求工具做交集过滤，对缺失的工具记录日志并允许 Agent 降级启动。
3. **运行时内化与错误优雅降级（对齐 OpenSWE `_wrap_tool` 与 `handle_tool_error`）**：
   所有 MCP 工具强制配置健壮的 `handle_tool_error` 处理器，捕获网络抖动、服务断连、5xx 错误及超时，将其转化为模型可理解的错误响应（`ToolMessage`），由大模型自主解释或切换策略，彻底消灭未捕获异常引发的 `runtime.execution_failed`。
