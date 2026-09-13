# 前端对话页面美化与交互体验重构 - 整体方案

## 背景
当前平台前端（`apps/platform-web`）在经历架构重构后，功能链路（LangGraph 编排、分支快照、中断审批、多模型接入）已基本打通且趋于稳定。但对话交互界面遗留了大量早期脚手架的粗糙样式：
1. 智能体选择使用了生硬的原生 HTML `<select>` 下拉框；
2. 每条对话消息底部常驻大号实体按钮（`pw-table-tool-button`），产生极大视觉噪声；
3. 工具调用与过程卡片使用硬编码字符 `▾ / ▸`，文件 Diff 与命令行缺乏科技感；
4. 新会话空白态缺乏引导与质感，输入框微交互和键盘快捷键提示不够细腻。

为了让产品从“功能可用”迈入“体验愉悦、专业高级”的标准，启动本次视觉与交互全方位重构。

## 目标
1. **视觉减负**：消息操作栏改为 Hover 浮动微型图标栏，Agent 回复去除粗重外框，建立自然通透的内容排版。
2. **控件升级**：替换顶栏与中部的原生 `<select>` 为高颜值 Agent 胶囊选择器，统一操作按钮优先级。
3. **极客与科技质感**：美化思考过程（Reasoning）、工具调用展开折叠动效、终端卡片及文件对比视图。
4. **体验升级**：新对话呈现专属 Agent Hero 引导与一键填充的 Prompt 快捷推荐卡，输入框提供丝滑聚焦光晕。

## 方案设计

### 1. 消息流与气泡改造 (`ChatMessageList.vue` + `MessageContent.vue`)
- **Hover 浮动工具栏**：
  - 消息气泡包裹在 `group relative` 容器中，操作栏设置 `opacity-0 group-hover:opacity-100 transition-opacity duration-200`。
  - 操作栏按钮由纯文本大方块改为微型图标按钮，内置复制成功视觉反馈（Check 绿标/Tooltip）。
  - 编辑与分支切换交互保持完整，但在非编辑态下视觉收敛。
- **角色标识**：
  - 用户标头增加首字母/头像 Badge。
  - Agent 标头增加专属微标与当前 Agent 实际名称（通过 props 传递 `targetName`）。
- **思考过程（Reasoning）**：
  - 渐变边框卡片，增加脉冲呼吸灯，展示思考耗时或字数，展开平滑过渡。

### 2. 工作台 Header 与控件分级 (`ChatPage.vue` + `ChatSession.vue`)
- **Agent 选择器**：
  - 新建/封装 `ChatAgentSelector.vue`，支持显示当前 Agent 名字、状态圆点、下拉选择与高亮。
- **顶栏操作按钮重组**：
  - “新对话”设置为 Primary Button；
  - “专注模式”、“运行参数”、“会话详情”重组为紧凑且带图标的 Secondary 工具按钮组。
  - 增加 Thread ID 一键复制微交互。

### 3. 工具调用与执行卡片 (`ToolResult.vue`)
- 展开/收起替换为 `BaseIcon` 配合旋转动画。
- Diff 代码对比视图重构：双栏卡片包装，顶部添加文件路径与状态标头。
- 命令执行卡片加入 macOS 终端风格窗口装饰与高质感深色背景。

### 4. 空白引导与输入框微交互 (`ChatSession.vue` + `ChatComposer.vue`)
- 空白页（Empty State）：大号 Agent 图标 + 简要定位 + 3~4 个可点击的预设 Prompt 指令推荐卡片。
- Composer 输入框：增强 `focus-within:border-primary-500/80 focus-within:ring-2 focus-within:ring-primary-500/10 focus-within:shadow-md`，并在右下角增加按键提示胶囊（`↵ 发送`，`⇧ ↵ 换行`）。

## 风险与依赖
- **依赖**：保留 Vue 3、Tailwind、`@langchain/vue` 既有依赖，不引入多余臃肿组件库。
- **兼容性**：必须保证暗黑模式（Dark Mode）与浅色模式下所有新组件视觉舒适、对比度合规；保留所有既有测试契约与事件 emits。
