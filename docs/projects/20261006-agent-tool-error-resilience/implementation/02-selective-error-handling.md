# 选择性错误出口与生产接线

实施日期：2026-10-06；对应 T02-T06。用户已批准方案，不新增依赖、自动重试或生产故障开关。

## 共享策略

`apps/runtime-service/src/runtime_service/tools/errors.py` 的 `tool_error_content()` 以受信工具名、真实异常类型和精确安全 code 分类，`on_tool_error()` 供官方组件使用，`tool_error_handler()` 绑定第一方 native handler。分类不读取 cause、请求参数或供应商正文；内容不超过 2 KiB。未分类返回 None/native re-raise。

原有 `handle_tool_error=True` 会先吞掉 ToolException，使外层策略失效；现改受信工具名绑定的 formatter。修改范围为 DearFlow 研究、媒体、部署、记忆、技能，公共文档/成果/图片，以及 Showcase 文档工具。成功结果、Command、媒体 durable receipt 和 MCP 多模态协议结果保留。

`services/{dearflow_agent,reference_agent}/agent.py` 和 `services/demo/showcase_demo/agent.py` 的局部 middleware 添加/复用官方 ToolErrorMiddleware；子图复用各自组合根策略。Reference 原有 read-only 有限重试保留，其他组合根不新增重试。

## 资源与控制流

- `services/dearflow_agent/tools/mcp.py:load_mcp_tools()` 保持构图授权/只读拒绝；调用 interceptor 只转换已知 transport，ExceptionGroup 每个 leaf 都必须已知。协议 `isError` 仍交给 adapter 原 handler，保留 text/image/artifact。
- `tools/chart.py:persist_image()` 在既有 interceptor 使用安全 JSON；schema 错误、受信 transport 和 MCP 协议错误可恢复，未知 conversion/存储故障传播。缺 npx 仅在调用阶段判定。
- `workspace/execution.py` 对可信根、配置和创建执行进程失败抛稳定 RuntimeWorkspaceError；不靠退出码或 stderr 猜 workspace 是否死亡，不回退宿主执行。
- `tools/images.py:ImageWorkspace._directory()` 区分可信根不可用和单文件不安全；生成结果未知使用 do_not_repeat，不拼原供应商文本。
- `services/dearflow_agent/tools/media.py:submit()` 先保存已开始操作的 unknown 回执，再传播未分类/安全/工作区/取消错误；已知结果未知保留 task_id，同幂等请求不重复提交。

RuntimeWorkspaceError 实际继承 RuntimeError，**不继承规划时建议的 RuntimeErrorBase/ValueError**。锁定 Deep Agents 文件系统 execute 会将 ValueError 降为参数错误，这会吞工作区基础故障；实测 graph 传播和缺 CLI 测试证明该最小调整必要。

## 独立流出口和观测

`patches.py:_patch_stream_tool_call_handler()` 复用既有 patch，把公开 tools `tool-error.message` 改为固定 `tool.execution_failed`；event/call ID/namespace 保留，GraphBubbleUp 和取消只清理，不产生工具错误事件。

`observability/langfuse.py:_RuntimeDiagnosticsCallback` 区分 raised `tool_error` 与 native error ToolMessage 的 `tool_result_error`，安全记录名称/code/既有请求关联；中断不计工具或 Run 失败，取消保留 cancelled。没有新状态机或Exporter。

## 已执行证据

- 共享/流/观测/图片图表定向：54 passed / 2 deselected。
- DearFlow/Showcase 主子图与权限/预算：13 passed。
- Reference 锁定基线：11 passed / 14 deselected。
- 受控 MCP/Docker 资源：7 passed；真实非零退出和 timeout 后副作用文件只包含两次独立请求，没有自动重发。

后续媒体传播、控制流计数和全范围回归见 verification.md 的持续 Phase 记录；本记录不代表 T09 或前端 Final 已通过。
