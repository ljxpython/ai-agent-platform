# 前端对话页面美化与交互体验重构 - 任务拆分

## Phase 1: 消息流与操作栏沉浸化改造
- [x] Task 1.1: 重构 `ChatMessageList.vue` 的操作栏为 Hover 浮动微型图标工具栏，支持复制反馈，优化气泡层次与 Agent 名称展示
- [x] Task 1.2: 美化 `MessageContent.vue` 的思考过程（Reasoning）卡片容器与加载动效

## Phase 2: 顶栏 Header 与工作台导航升级
- [x] Task 2.1: 创建 `ChatAgentSelector.vue` 并替换 `ChatPage.vue` 中的原生 `<select>` 控件
- [x] Task 2.2: 优化 `ChatSession.vue` 顶栏操作区（按钮视觉主次分级、Thread ID 复制微交互）

## Phase 3: 工具调用与执行卡片升级
- [x] Task 3.1: 优化 `ToolResult.vue`（替换文本箭头为 `BaseIcon` 动画、美化文件 Diff 及终端命令执行卡片）
- [x] Task 3.2: 重构 `ChatSession.vue` 新会话空白态为带有快捷 Prompt 推荐的 Agent Hero 看板

## Phase 4: 输入框微交互与全量验证
- [x] Task 4.1: 优化 `ChatComposer.vue`（聚焦呼吸光晕、快捷键提示微标）
- [x] Task 4.2: 跑通前端单元测试、TypeScript 类型检查与全量构建，确保零报错

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成
- [x] Phase 4 完成
