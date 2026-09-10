# Phase 4：前端缺口补齐与联调

## 改动时间
2026-09-08

## 相关任务
- 前端补齐对 Showcase Demo 的特性支持，包括 `stream_mode`，Subagent Token 渲染，和 Sandbox 布局展示。

## 改动文件
- `apps/platform-web/src/modules/chat/composables/usePlatformChatStream.ts`
- `apps/platform-web/src/modules/chat/stream-messages-to-ui.ts`
- `apps/platform-web/src/modules/chat/components/BaseChatTemplate.vue`
- `apps/platform-web/src/modules/chat/types.ts`

## 具体改动

### 1. 流式模式支持
**位置：** `usePlatformChatStream.ts`
**改动内容：** 
- 在调用 `useStream` 时新增了 `streamMode: ['messages', 'updates']` 和 `subgraphs: true`，以便能正确接收 `ShowcaseState` 里的 `todos` 更新（updates 模式）以及抛出带有命名空间的子智能体消息流。

### 2. Subagent Token UI 渲染
**位置：** `stream-messages-to-ui.ts`
**改动内容：**
- 修改了 `streamMessagesToUi` 解析 AI 消息的逻辑。
- 识别到 `raw.name` 并且判断出是具体的子智能体名称时，为对话加上了 `**[Subagent - ${name}]**` 的文本前缀区分显示，使得前端用户可以清晰感知到研究智能体 (research) 和执行智能体 (implementor) 在后台的运作。

### 3. Sandbox 三栏布局
**位置：** `BaseChatTemplate.vue`, `types.ts`
**改动内容：**
- 在 `types.ts` 中为 `PlatformChatFeatures` 增加了 `showSandbox?: boolean` 开关。
- 提取并重构了 `BaseChatTemplate.vue` 里的响应式栅格 (`lg:grid-cols-...`) 控制逻辑。
- 引入缺漏的 `<ChatTasksFilesPanel />`，并在计算出 `hasSandboxFiles` (即包含 `todos`, `tasks`, 或 `files`) 且 `showSandbox` 开启时，将其放在原有 `ChatArtifactPanel` 的左侧。
- 实现了 Sandbox 三栏布局 (侧边历史栏 + 中间聊天与交互区 + 右侧沙箱执行/文件任务面板) 的无缝拼接。

## 验证
- [x] TypeScript 类型检查验证（无 `any` 滥用或 Prop 传递错误）。
- [x] Vue 组件布局计算属性逻辑已验证通过。
