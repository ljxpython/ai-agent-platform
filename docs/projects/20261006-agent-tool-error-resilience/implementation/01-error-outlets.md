# T01：实际错误出口与实施基线

2026-10-06；用户已评审批准。使用锁定 Runtime 环境检查本工作树，未修改主检出或依赖。

## 已复现基线

新增真实 DearFlow 主/子图测试，使用既有身份配置、Workspace、Deep Agents 和本地受控模型。首次测试辅助模型签名不兼容，修正辅助模型后取得有效基线：`3 failed, 2 passed`（9.50 秒）。

- `search_web(query="")`：原 native handler 返回字符串 `invalid_research_query`，缺少批准的 JSON 字段。
- `tavily()` 抛未归类 `ToolException`：原 `handle_tool_error=True` 吞异常，模型继续；应传播并终止。
- researcher 内部非法输入：子图继续但同样缺少结构化内容。
- RuntimeAuthError、未知 RuntimeError：既有主图正确传播，必须保留。

首次接线后同组及 Reference 测试 `14 passed`；后续任务的最终结果另记 verification.md，不用此记录替代资源和跨服务验收。

## 逐出口策略

| 工具/边界与代码位置 | 原处理 | 本期处理与副作用边界 |
| --- | --- | --- |
| `tools/search.py:build_research_tools()`：search_web/fetch_page | ToolException native=True；Tavily/Jina 内部归类输入、provider、size、empty | 精确工具名/稳定 code 共用 JSON；输入发生在操作前；provider 只读失败为 failed。证据 hash/write/probe 错误不转业务错误；未知 Jina 异常不得吞掉 |
| `tools/research_http.py:get_public()`；github_query/arxiv_search/fetch_web_guidelines | 固定站点；HTTP/timeout 转稳定 ToolException；schema/编码另有 code | 保持既有只读调用和 SSRF 约束；输入与上游响应分别归类；内部 endpoint_denied 不放行；403/429 不触发自动重试 |
| `tools/documents.py:parse_document()`；`tools/artifacts.py:present_artifacts()` | DocumentError native=True | 可修正引用、文件/格式/参数错误转安全 JSON；hash/conflict、工作区基础故障传播；成功解析和不可变产物保留 |
| `tools/memory.py:build_memory_tools()` | DocumentError native=True，含 scope/shared/maintenance | 仅已明确的输入/事务前 revision/容量失败可恢复；scope/shared/maintenance/config/storage 错误传播，无新增重试 |
| `tools/skills.py:build_skill_tools()` | DocumentError native=True；下载有稳定 code | 参数、包校验、revision 和已批准操作拒绝可恢复；身份、快照和存储错误传播；成功结果不变 |
| `tools/media.py:build_media_tools()` | ToolException native=True；宽泛 ValueError 包装；提交后 Exception/取消进入 durable unknown | 只对精确输入错误归一化；收紧 ValueError 包装；保留 durable task_id/unknown/attempts 与取消 shield；不重复供应商提交 |
| `tools/deployment.py:deploy_preview()` | DocumentError native=True；提交后 durable unknown | 精确包/manifest/digest 校验可恢复；workspace/配置/scope 不吞；原 unknown 和 claim 事实保留 |
| 共享 `tools/images.py:build_image_tools()` | native=True；provider/body 原文拼接；未知异常也包装 | 输入使用共享 formatter；已提交图片不返回 not_started；已知 SDK 错误给安全 unknown/只读 unavailable；未知程序异常传播；根目录失败与单文件缺失区分 |
| 共享 `tools/chart.py:build_chart_tools()` | interceptor 返回 MCP isError，拼接 validation/provider 原文，catch Exception 兜底 | 已确认输入/协议/transport 失败使用安全 JSON；工作区/权限/转换/未知异常传播；成功多模态与 runtime_images 保留 |
| `tools/mcp.py:load_mcp_tools()` | 构图绑定/冲突/只读检查；adapter 已处理 isError | 构图仍 fail-closed；只为已授权 read-only transport 安装 adapter interceptor；保留原生协议错误 handler 与多模态 artifact；混合 ExceptionGroup 传播 |
| FilesystemMiddleware 与 service Backend | 文件失败已有结果；execute 捕获 ValueError 为参数错误 | 普通文件失败/非零退出保留；根/prepare、确定的执行启动错误停止，不替换空目录或回退宿主执行 |
| `task`、request_information、HITL/预算 | Command/GraphBubbleUp、cancel 与限额已有语义 | 父 task 不兜底子图致命失败；主子图独立接线；中断、取消、guard 传播 |
| `patches.py:_patch_stream_tool_call_handler()` | tool-error 独立使用原异常文本 | 保留 call ID/namespace/event，message 固定 `tool.execution_failed`；中断/取消不生成失败事件 |

表中未写完整前缀的 `tools/` 位于 `apps/runtime-service/src/runtime_service/services/dearflow_agent/`；“共享”路径位于 `apps/runtime-service/src/runtime_service/`。

## 代码核对导致的最小调整

`RuntimeWorkspaceError` 不能继承 RuntimeErrorBase（其继承 ValueError）：锁定 Deep Agents 的 execute 会将 ValueError 吞成参数错误。改为稳定 code 的 RuntimeError 子类，显式从共享容错分类排除；不修改其他 RuntimeErrorBase 的既有契约。

所有第一方 code 为静态已审阅集合；未新增错误 Registry、生产故障开关、通用自动重试或新的运行状态。
