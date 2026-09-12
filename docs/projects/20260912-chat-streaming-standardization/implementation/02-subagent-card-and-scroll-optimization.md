# 实施记录 02：子智能体卡片对齐 Open SWE 与视口通知优化

## 1. 目标概述
解决在 Showcase Demo 与多智能体委派中暴露的前端体验缺陷：
1. **子智能体工具调用泄漏至主消息列表外部**：
   - 子智能体内部调用的 `ls /workspace`、`read_file /workspace/report.py` 等工具，由于命名空间过滤漏判，被错误提升到外层父会话时间线上展示；
   - 主智能体在输出最终回复后，消息列表底部外部重复渲染一个硬编码的 `research 已返回` 全局卡片；
   - 消息流时间线内直接输出未经清洗的 Python 源码字符串（如 `Command(update={'messages': [ToolMessage(content=...`）。
2. **子智能体卡片展开内部显示“你”产生角色混淆**：
   - 展开子任务卡片时，内部复用了主会话 `<Transcript>` 组件，导致主智能体派发给子智能体的任务指令被硬编码渲染为用户聊天气泡并标注为“你”。
3. **向上滚动时的视口未读浮窗体验糟糕**：
   - 浮窗面积大（320px），遮挡视线；
   - 即使滚回底部，未读计数未清空，每次只要再次向上翻看历史，立刻再次弹出“有 2 条新消息”。

## 2. 方案与关键代码实现

### 2.1 修复 `useTranscriptMessages.ts` 命名空间严格隔离
- **文件：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **实现要点：**
  1. 移除对带有 `tool_calls` 或 `type === 'tool'` 的无条件提前放行逻辑；
  2. 严格拦截属于子智能体（`stream.subagents` 或带有 `tools:`/`task:` 来源命名空间）的消息，确保子智能体内部的所有工具调用与消息彻底收敛在其自身作用域中，绝不泄漏到外层根时间线；
  3. 支持事件中 `data` 为数组时的全量消息 ID 来源捕获。

### 2.2 彻底重构 `SubtaskDetail.vue` 专属子任务视图
- **文件：** `apps/platform-web/src/modules/chat/components/SubtaskDetail.vue`
- **实现要点：**
  1. 彻底摒弃复用 `<Transcript>` 的做法；
  2. 提取主智能体派发的指令，以带有小徽标的“主智能体指派任务”卡片呈现，杜绝“你”字样；
  3. 在卡片内部使用 `useToolCalls` 与 `ToolResult` 优雅渲染子智能体执行的全部工具操作（如 `ls /workspace`、`read_file /workspace/report.py` 等），支持展开查看输入与结果。

### 2.3 新建 `SubagentCard.vue` 对齐 Open SWE 渲染规范
- **文件：** `apps/platform-web/src/modules/chat/components/SubagentCard.vue`
- **设计要点：**
  1. 顶部 Header 包含 Bot 图标、子智能体角色（提取自 `args.subagent_type` 或名称）、蓝色“子智能体”标签，以及一句话任务说明（提取自 `args.description` 或 `args.prompt`）。
  2. 右侧状态徽章指示：执行中（带脉冲动画）/ 已返回。
  3. 可点击展开折叠，展开后自动清洗反序列化 Python 原生 `Command(update=...)` / `ToolMessage(content='...')` 格式，将其转为排版规整的 Markdown 报告。
  4. 支持 `tools:${props.tool.id}` 的命名空间 fallback 机制，确保即时挂载。

### 2.4 彻底清理底部重复悬挂卡片（`ChatSession.vue`）
- 移除原写在 `<ChatMessageList>` 下方多余的全局 `subtasks` 循环渲染与无用响应式变量。

### 2.5 视口悬浮通知胶囊化与状态流重置（`ChatSession.vue`）
- 将原本右下角固定 320px 的重度遮挡卡片重构为底部居中（`left: 50%; transform: translateX(-50%)`）的 32px 高度微型浮动胶囊（Pill）。
- 在 `handleViewportScroll` 监听中，当视口滚回底部（`isChatViewportNearBottom` 为 true）时，立即触发 `unreadMessageCount = 0` 与 `bufferedStreamActivity = false`，保证阅读历史时不产生死循环误弹。

## 3. 测试覆盖
- 新增 `apps/platform-web/src/modules/chat/components/SubagentCard.spec.ts`：验证角色解析、任务描述与 Markdown 清洗。
- 新增 `apps/platform-web/src/modules/chat/components/SubtaskDetail.spec.ts`：验证主智能体指派任务标识（无“你”），以及卡片内部内聚渲染子智能体工具调用。
- 增强 `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`：新增测试验证子智能体内部工具调用（`AIMessage` 与 `ToolMessage`）绝不泄漏到父视图。
- 全量测试通过：39 个测试套件，104 个用例全部 Pass。
