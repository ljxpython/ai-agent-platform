# 任务胶囊收起与时间旅行卡片标题精准化优化

## 背景与问题
1. **任务进度吸顶胶囊遮挡正文且无法关闭**：聊天页面顶部的任务进度条固定吸顶，无论任务是否已完成（2/2）都一直霸占顶部整行宽度，且在页面向上滚动时直接覆盖在消息气泡文字上方，且没有提供任何关闭（`✕`）或收起按钮。
2. **会话详情“时间旅行”卡片标题千篇一律**：在会话详情抽屉的历史标签页中，数十甚至上百个 Step 的卡片标题全部显示为会话最初的第一句用户提问（如“请开始修复 report.py...”），原因是 `getHistoryEntryPreviewText` 错误地每次都查找全场第一条 human 消息，导致用户完全无法分辨各个 Step 实际发生了什么动作。

## 变更内容
1. **重构 `ChatStickyTaskPill.vue` 任务进度胶囊**：
   - 增加 `isDismissed` 折叠与隐藏状态控制。
   - 右上角操作区新增优雅的 `✕` 收起按钮（带 `aria-label="收起任务进度"`）。
   - 收起后自动切换为右上角极简的微型恢复胶囊（Mini Chip），仅占几十像素宽度，附带彩色状态圆点与当前任务数，绝不横向铺满遮挡正文。
   - 用户点击微型恢复胶囊可随时重新展开大横幅。
2. **重构 `threads.ts` 中 `getHistoryEntryPreviewText` 标题生成算法**：
   - 提取当前 Step 产生的最新消息或状态突变，新增 `formatMessageActionPreview` 辅助解析器。
   - **工具调用阶段**：精准识别 AI 决策发起的工具调用，输出 `🔧 调用工具: {tool_name} ({参数关键目标})`（例如 `write_file (report.py)`）。
   - **工具返回阶段**：精准提取工具返回结果，输出 `📥 工具完成 [{tool_name}]: {执行摘要}`。
   - **用户提问阶段**：提取当前回合提问，输出 `👤 用户: {提问内容}`。
   - **Agent 回复阶段**：提取当前输出文本，输出 `🤖 Agent: {回答正文摘要}`。
   - **人工审批阶段**：优先检测 `interrupts`，输出 `🛑 等待审批: 需要人工确认操作`。
3. **补充单元测试**：
   - `ChatStickyTaskPill.spec.ts` 新增对收起与恢复微型胶囊的交互测试。
   - `history-view-model.test.ts` 新增对审批、工具调用、工具完成、Agent 回复等各种 Step 动作预览标题的断言测试。

## 涉及文件
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatStickyTaskPill.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatStickyTaskPill.spec.ts`
- [MODIFY] `apps/platform-web/src/utils/threads.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/history-view-model.test.ts`
