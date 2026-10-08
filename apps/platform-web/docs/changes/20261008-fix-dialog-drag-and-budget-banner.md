# 修复弹窗鼠标拖选误关、错误条文案截断及继续执行时报错未清空问题

## 背景

用户在对话界面遇到三项交互缺陷：

1. 在“运行参数与执行模式”弹窗中，使用鼠标向右拖拽选中文本数字时，弹窗意外关闭退出。
2. 顶部的步骤超限错误横幅末尾文案被省略号截断（显示为 `可调整或...`），信息展示不全。
3. 用户调整完参数在对话框中输入“继续”发起新的执行后，上一轮的红色步骤上限中断报错横幅依然残留悬挂在顶部，未即时清除。

## 改动内容

1. `apps/platform-web/src/components/base/BaseDialog.vue`：
   - 彻底修复经典的“拖拽选中文本导致遮罩层误判定点击”问题。
   - 替换外层 overlay 的 `@click.self` 为精确的 `mousedown` 与 `mouseup` 组合判定：仅当鼠标按下与释放均在遮罩背景自身上时才触发 `closeOnClickOutside`，用户在弹窗内部拖选任何文本拖到外部均绝对不会误触发关闭。
2. `apps/platform-web/src/modules/chat/components/ChatAgentStatusBar.vue`：
   - 去除文本容器的 `truncate` 单行截断，改为自适应换行 `break-words flex-1 leading-relaxed`，确保报错说明及引导建议文案完整展开；
   - 优化外层布局自适应及按钮对齐，避免宽度受限时挤压截断；
   - 优化渲染状态与优先级：当 `isRunning` 为 true 且处于新一轮执行中时，屏蔽上一轮的历史终态错误横幅，仅在有运行时动态预警时展示。
3. `apps/platform-web/src/modules/chat/composables/useRunBudget.ts` & `ChatSession.vue`：
   - 向 `useRunBudget` 接入当前会话运行状态 `isRunning`；
   - 当会话处于活跃执行中（`isRunning: true` 或 `status === 'running' | 'pending'`）时，忽略上一轮派生的终态安全错误（`effectiveSafetyError: null`），使得用户点击“继续”时旧报错横幅即时清除。

## 验证

- 单元测试：`pnpm test:run` 116 个文件、574 项测试 100% 通过。
- 类型检查：`pnpm check` 0 errors。
- 端到端测试：`scripts/test_three_issues_e2e.cjs` 验证拖选数字不退出、文案无省略号完整显示、发送“继续”后顶部报错条即时清除，三项测试真实浏览器 100% 通过。
