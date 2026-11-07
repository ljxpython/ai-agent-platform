# 前端 Markdown 产物链接拦截下载与空闲会话长连接断开误报治理

## 项目概述
- **时间：** 2026-11-06 至 2026-11-07
- **目标：** 解决 Agent 文本中 `[下载 PPTX](artifact://...)` 链接被 Markdown 误清洗为 `#` 导致新开空白标签页的缺陷，实现产物协议安全放行与一键原生下载拦截；同时消除多会话池切换切回已完成会话时由于空闲 SSE 流重连被拒导致的 `Event stream closed.` 假死误报警。
- **负责人：** 老王
- **模板类型：** 标准模板
- **状态：** 全部完成（`done`），已完成全量单测、构建并成功部署到生产环境 `/www/wwwroot/agent-platform`。

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`
- **改动级别：** 链路改动（涉及 Markdown 协议安全清洗契约、Chat 会话池流恢复状态机、以及产物下载端到端交互）
- **预计工作量：** 1 人天

## 关键决策
1. **Markdown 协议放行与点击事件事件委托拦截**：在 `markdown.ts` 中将 `artifact:` 纳入 `SAFE_PROTOCOLS` 白名单，保留原始 `artifact://<artifact_id>` URI；在消息渲染容器或全局链接点击处理器中建立委托拦截，匹配 `artifact://` 协议后阻止浏览器默认页面跳转，提取 `artifact_id` 并调用 `getWorkspaceContentBlob` 触发流式文件下载。
2. **长连接断开非致命过滤（Reconnection Idempotence）**：在 `useChatSession.ts` 的 `isNonFatalStreamError` 中增加 `Event stream closed` 与 `Protocol event stream closed` 过滤；对于已经处于空闲完成态（无 active run）的会话，重连被拒仅代表无新事件产生，严禁污染 `error.value` 与状态栏。
