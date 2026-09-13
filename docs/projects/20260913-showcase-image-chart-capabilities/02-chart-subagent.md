# 图表 MCP 子 Agent

## 目标
将 `@antv/mcp-server-chart` 作为独立 MCP 工具集挂载到 chart 子 Agent，由主 Agent 通过 `task` 委派使用。

## 方案设计
- 通过官方 MCP adapter 使用 stdio `npx -y @antv/mcp-server-chart@0.9.10`。
- `get_agent()` 依据随包发布的 schema 构造原生 MCP tools，传给 `build_subagents()`；实际调用时才建立会话。
- 增加显式 `chart-agent`，只拥有图表 MCP 工具及完成任务所需的最小读取能力。
- chart-agent 不获得再次委派、shell 执行或任意写文件权限。
- 管理 MCP client/子进程生命周期，避免每次调用泄漏进程。
- 图表结果由 Agent 返回；如需落盘，统一通过受控 workspace 适配逻辑写入 `/workspace/...`。

## 任务拆分
- [x] 复用官方异步会话生命周期，schema 探测零网络。
- [x] 增加 `chart-agent` Prompt、描述和最小工具集。
- [x] 将 chart 工具纳入 runtime-service 内部权限校验。
- [x] 增加主 Agent 委派图表任务的示例。

## 验证要求与记录
- [x] MCP server 可启动并成功发现工具（schema 来源为实际 get_tools）。
- [x] 主 Agent 能通过 `task` 调用 chart-agent。
- [x] chart-agent 不暴露 shell、写文件或再次委派工具，Runtime 调用边界执行角色集合校验。
- [x] 清空 PATH 注入 npx 不存在的操作系统级启动故障；返回原生 MCP 错误结果，未生成任何产物。会话清理由官方 adapter 管理，运行中进程崩溃/强制取消未做专项测试。

2026-09-13：真实模型 `test_live_main_model_delegates_chart` 通过（47.90 秒）。DeepSeek 主模型自行选择 chart-agent；子模型调用 AntV `generate_bar_chart`；图片已写入 `/workspace/charts/`。
确定性委派、图片 URL 转存及未授权 URL/重定向拒绝测试通过。故障测试发现普通 ToolException 会被 adapter 再抛出，已改用 `CallToolResult(isError=True)` 并验证模型收到错误状态。MCP 输出是文本 URL，`artifact=null`；电子表格工具不装配，不承诺未测试图表类型均成功。

## 状态
done（已验收条形图完整链路）；进程崩溃专项不属于本次完成证据。
