# 子智能体卡片对齐 Open SWE 与未读消息悬浮窗体验优化

## 背景与问题
1. **子任务卡片重复且格式凌乱**：主智能体完成回复后，消息列表下方突兀地多出一个 `research 已返回` 的全局卡片；同时在时间线内部将 `task` 工具作为普通工具渲染，暴露未经解析的 Python 原生字符串 `Command(update=... ToolMessage(content=...`。
2. **子智能体工具调用泄漏至外层主时间线**：子智能体内部执行的 `ls /workspace`、`read_file /workspace/report.py` 等工具调用，不仅在 `useTranscriptMessages` 中曾被提前放行，且在 `buildTranscript` 的 `calls` 处理中被当作孤儿工具强行塞入主时间线，导致子智能体框外多出一次重复卡片。
3. **子智能体内部展开显示“你”产生角色混淆**：展开子任务详情时，内部复用了主会话 `<Transcript>` 组件，导致主智能体派发给子智能体的任务提示词（以 HumanMessage 形式注入子图）被硬编码渲染为用户聊天气泡并标注为“你”。
4. **未读消息提示反复遮挡视线**：当用户向上滚动翻阅历史时，频繁弹出右下角大面积（320px）的未读消息卡片，且滚回底部后未重置未读数，再次上滑又重复误弹。

## 变更内容
1. **修复 `transcript.ts` 根视图孤儿工具拦截机制**：
   - 在 `buildTranscript` 的未匹配 `calls` 遍历中加入作用域保护：在根视图（`namespace.length === 0`）下，**坚决不采纳任何非根图消息发起的孤儿工具调用**（如子智能体在子图内部调用的 `read_file`、`ls` 等）；
   - 确保根时间线上仅渲染根图自身发起并请求的工具（如 `task`），彻底杜绝子图工具外泄到子任务卡片下方。
2. **修复 `useTranscriptMessages.ts` 命名空间严格隔离**：
   - 移除原先对带有 `tool_calls` 或 `type === 'tool'` 的无条件提前放行逻辑；
   - 严格拦截属于子智能体（`stream.subagents` 或带有 `tools:`/`task:` 来源命名空间）的消息，确保子智能体内部的所有工具调用与消息彻底收敛在其自身作用域中。
3. **重构 `SubtaskDetail.vue` 专属子任务视图（彻底消除“你”，内聚展示工具步骤）**：
   - 彻底摒弃复用 `<Transcript>` 的做法；
   - 提取主智能体派发的指令，以带有小徽标的“主智能体指派任务”卡片呈现，杜绝“你”字样；
   - 在卡片内部使用 `useToolCalls` 与 `ToolResult` 优雅渲染子智能体执行的全部工具操作（如 `ls /workspace`、`read_file /workspace/report.py` 等），支持展开查看输入与结果。
4. **新增 `SubagentCard.vue` 专用组件**：
   - 对齐 Open SWE 渲染规范，以专有卡片形式嵌入工作流时间线。
   - 提取角色标识（如 `research`，附带“子智能体”蓝色标签）、简述（`description`）、状态徽标（执行中 / 已返回）。
   - 折叠/展开交互：内置 Markdown 结果渲染，将后端返回的 Python 字符串自动清洗反序列化为结构化分析报告。
   - 支持 `tools:${props.tool.id}` 的 namespace fallback 机制。
5. **删除重复悬挂的全局 subtasks**：
   - 从 `ChatSession.vue` 消息列表底部彻底移除残留的全局 `subtasks` DOM 渲染，杜绝双重出现。
6. **未读消息提示重构为轻量居中胶囊**：
   - 将原右下角大卡片重构为底部居中 32px 的微型圆角悬浮胶囊，半透明磨砂背景，绝不遮挡阅读历史。
   - 视口监听在滚回底部（Near Bottom）时立即清空 `unreadMessageCount = 0`，防止再次上滑重复误弹。

## 涉及文件
- [NEW] `apps/platform-web/src/modules/chat/components/SubagentCard.vue`
- [NEW] `apps/platform-web/src/modules/chat/components/SubagentCard.spec.ts`
- [NEW] `apps/platform-web/src/modules/chat/components/SubtaskDetail.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/SubtaskDetail.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/transcript.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/transcript.test.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/Transcript.vue`
