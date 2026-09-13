# 会话详情时间旅行角色筛选与历史发问分叉

## 背景与诉求
1. **历史长对话定位发问检查点成本高**：
   在复杂多轮对话或包含密集工具调用（如 Open-SWE、展示 Demo、代码编辑与系统中间件）的会话中，检查点（Steps）动辄上百个。即使开启了“仅显示关键节点”，列表中仍然混杂大量 AI 工具调用、系统中断与 AI 回复，用户如果想找到某一次自己的发问并分叉重新执行（Fork），需要反复逐条肉眼甄别查找。
2. **纯粹聚焦时间旅行抽屉的核心体验**：
   保持主聊天窗口极简无干扰，所有历史回退、检查点筛选与分叉操作统一收敛在「会话详情 - 时间旅行」抽屉中。

## 变更内容
1. **检查点角色智能分类与统计 (`history-view-model.ts`)**：
   - 定义并导出 `CheckpointRole = 'user' | 'agent' | 'tool' | 'system'` 及角色标签映射。
   - 实现 `extractHistoryEntryRole`：精准解析检查点角色属性（用户提问 `user`、纯 Agent 回复 `agent`、工具调用与返回 `tool`、系统中间件 `system`）。
   - 在 `ChatHistoryView` 中统计各角色快照数量（`userCount`, `agentCount`, `toolCount`, `systemCount`）。
2. **时间旅行角色过滤与快照操作醒目化 (`ChatContextDrawer.vue`)**：
   - 历史列表顶部新增角色过滤 Pill 按钮组（全部、👤 用户提问、🤖 Agent 回复、🛠️ 工具调用），带实时数量徽章。
   - 支持与“仅显示关键节点”多维叠加组合过滤。例如开启“仅显示关键节点”并选择“👤 用户提问”，可将上百个步骤瞬间精简为纯粹的几次用户发问点。
   - 历史快照卡片上展示显式角色徽章（如“👤 用户提问”、“🤖 Agent 回复”等），一眼看清快照角色。
   - 选中发问快照后，直接在抽屉顶部或卡片内点击【从此快照重新执行】，或者关闭抽屉后在底部输入框直接分叉（Fork）执行新指令。
3. **单元测试与质量验证**：
   - `history-view-model.test.ts` 补充针对 `extractHistoryEntryRole` 和各类角色计数统计的完整单元测试。
   - `vue-tsc --noEmit` 0 报错通过。
   - 全量 Vitest 测试套件全部绿灯通过。

## 涉及文件
- [MODIFY] `apps/platform-web/src/modules/chat/history-view-model.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/history-view-model.test.ts`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatContextDrawer.vue`
