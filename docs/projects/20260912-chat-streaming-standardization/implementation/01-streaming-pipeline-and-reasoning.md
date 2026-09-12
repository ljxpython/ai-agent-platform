# Chat 流式消息管道与 Reasoning 呈现实现记录

## 改动时间
2026-09-12

## 相关任务
- Task 1.1: 梳理与核验 Gateway / Runtime 流模式契约
- Task 1.2: 重构 `useTranscriptMessages.ts` 释放 Live 流
- Task 2.1: 优化 `transcript.ts` 纯函数视图映射
- Task 2.2: 升级 `ChatSession.vue` 视口平滑跟随
- Task 2.3: `ChatMessageList.vue` 流式视觉优化
- Task 3.1: Chat 模块单元测试与 Lint 回归

## 改动文件
- `apps/platform-web/src/modules/chat/transcript.ts`
- `apps/platform-web/src/modules/chat/transcript.test.ts`
- `apps/platform-web/src/modules/chat/components/MessageContent.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatModelSelector.vue`
- `apps/platform-web/src/modules/chat/components/ChatModelSelector.spec.ts`

## 具体改动

### 1. `transcript.ts`：纯函数提取推理链与流式块
**位置：** `apps/platform-web/src/modules/chat/transcript.ts`

**改动内容：**
- 扩展 `ContentItem.kind` 联合类型，增加 `"loading"` 支持等待态。
- 新增 `extractReasoningFromMessage(message: BaseMessage): string`：
  - 从 `additional_kwargs.reasoning_content` 或 `response_metadata.reasoning_content` 中提取大模型的思考链。
- 增强 `contentItems(message: BaseMessage): ContentItem[]`：
  - 遇到思考标签（`<think>...</think>` 或 `<thinking>...</thinking>`），自动拆分剥离出独立的 `reasoning` 内容块。
  - 自动拼装未剥离的 extraReasoning 为首个 `reasoning` 块，紧接着渲染 `text` 回复块。
- 更新 `buildTranscript`：
  - 遇到 pending 或思考中状态时，生成对应的思考或 loading 项目。

**理由：**
- 对齐 open-swe 视图投影设计，不需要依赖额外的 store 中间状态，直接利用单向纯函数把 LangChain/LangGraph 的消息格式（包含各类模型思维链格式）转化为结构化渲染单元。

### 2. `MessageContent.vue`：打字机光标与思考折叠状态
**位置：** `apps/platform-web/src/modules/chat/components/MessageContent.vue`

**改动内容：**
- 新增 `isStreaming?: boolean` prop。
- 当 `isStreaming` 为 true 且处于文本块末尾时，添加打字机光标动画（CSS 脉冲闪烁）。
- 将 `reasoning` 块在流式生成中默认展开，顶部附带“思考中...”动态跳动小圆点；当流式结束完成后自动恢复收起（显示总用时或点击展开）。
- 对 `loading` 类型内容提供骨架式思考中占位指示。

### 3. `ChatMessageList.vue`：流式状态透传与白屏等待占位
**位置：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`

**改动内容：**
- 在 `visibleDisplayMessages` 中，根据当前会话 `props.isRunning` 以及是否为最后一个 Assistant Turn，计算并打上 `isStreaming: boolean` 标记。
- 在用户提问刚发出、Assistant 尚未产生第一个 chunk 的空档期，注入带有 `loading` 占位块的临时气泡，彻底避免用户等待期间的界面白屏与无响应感。
- 透传 `:is-streaming` 给 `<MessageContent />`。

### 4. `ChatSession.vue`：视口平滑跟随与清理
**位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`

**改动内容：**
- 针对流式打字期间消息数组长度不变但文字不断累加的场景，将 `watch(messages)` 改为 `{ deep: true, flush: "post" }`。
- 采用 `requestAnimationFrame` 调度平滑滚底，防止高频 SSE chunk 导致的频繁 DOM 重排卡顿；在组件销毁（`onScopeDispose`）时安全 `cancelAnimationFrame` 释放资源。

### 5. `ChatModelSelector.vue`：修复点击外部无脑抢夺焦点导致无法输入消息的 Bug
**位置：** `apps/platform-web/src/modules/chat/components/ChatModelSelector.vue`

**原因与现象：**
- `handleClickOutside` 在面板未开启时依然被全局 `document.click` 捕获，且无条件调用 `close()`；
- 原 `close()` 中无条件执行 `triggerRef.value?.focus()`，导致用户每次点击输入框 `textarea` 准备输入时，焦点被瞬间强行抢夺回模型选择器按钮；
- 模型选择器按钮获取焦点触发 `:focus` 高亮样式，呈现“下方模型框亮一下”，同时 `textarea` 失去焦点，键盘输入完全被阻断。

**改动内容：**
- `close(restoreFocus = true)`：增加 `if (!isOpen.value) return` 守卫，避免在关闭状态下无意义执行和夺取焦点；
- `handleClickOutside`：面板未打开时直接返回；关闭时不传 `restoreFocus`（即 `close(false)`），确保用户点击外部目标（如输入框、操作按钮）时保留用户期望的焦点；
- 仅在用户键盘按 `Escape` 取消或键盘回车选择模型项时（a11y 场景）才归还焦点给触发按钮；
- 补充 `ChatModelSelector.spec.ts` 自动化测试用例，确保后续绝不再出现点击外部抢焦点的回归隐患。

## 验证
- [x] 单元测试通过：`pnpm exec vitest run src/modules/chat`（覆盖 reasoning 提取、think 标签剥离、单/多块图构建、防抢焦点测试等用例）
- [x] 整体单元测试套件：`pnpm test:run`（37 个测试套件通过，94 个测试通过）
- [x] 类型检查通过：`pnpm typecheck`
- [x] 代码风格规范检查通过：`pnpm lint`
- [x] 构建测试通过：`pnpm build`
