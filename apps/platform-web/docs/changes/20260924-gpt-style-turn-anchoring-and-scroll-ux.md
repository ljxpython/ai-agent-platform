# 仿 GPT 聊天界面回合锚定与流式滚动体验优化

## 背景与问题
1. **首次提问时空状态残留闪烁**：`ChatSession.vue` 原先使用 `!messages.length && !checking` 判断欢迎卡片显示，而乐观上屏的用户消息写入在 `displayedMessages` 中，导致用户首次提问回车后欢迎卡片仍占据顶部，等首个 SSE 包到达才突然跳变消失。
2. **粗暴滚底导致问题贴底且流式上蹿**：原先每次 `displayedMessages` 变化均无条件执行 `viewport.scrollTop = viewport.scrollHeight`，导致后续提问紧贴底部输入框，且流式输出每增加一行字就把用户提问向上顶移直至顶出视野。
3. **重复“回到最新”按钮引起布局跳动**：在 `ChatComposer` 上方存在块级“回到最新”按钮，显隐时改变 Flex 容器高度导致输入框上下跳动。
4. **首次对话欢迎页回闪与后续轮次气泡闪烁**：
   - 首次发送消息时，`session.send()` 中 `await service.create()` 先改变了 `threadId`，此时 `streamInFlight` 尚未置 `true`（`busy === false`），触发 `ChatSession.vue` 的 `watch([messages, busy])` 将 `optimisticUserMessage` 误清空为 `null`，导致欢迎画面在首个 SSE 分片到达前瞬间回闪。
   - 后续轮次发送后，服务端回显的 `HumanMessage.id` 替换了前端乐观生成的 `optimisticUserMessage.id`，导致 `ChatMessageList.vue` 与 `MessageContent.vue` 中基于 `message.id` 的 `v-for` `:key` 全部失效并卸载重建整棵 DOM 树；叠加 `useTranscriptMessages.ts` 在 `snapshot` 尚未追上最新轮次时提前裁剪未落库消息、以及 `.pw-chat-turn-animated` 的 `opacity: 0 -> 1` 帧动画，造成肉眼可见的对话区闪烁。

## 改动内容
1. **首轮提问即时置顶 + 欢迎画面单向锁死**：
   - 将欢迎空状态条件加固为 `v-if="!props.threadId && !session.threadId.value && !hasConversationStarted && !displayedMessages.length && !checking && !isSessionRunning"`；只要发出首条消息，`hasConversationStarted` 立即单向锁死为 `true`，且 `useChatSession.send()` 入口第一行立即置 `streamInFlight = true`，欢迎页绝不回闪。
   - 首次提问（`turnCount === 1`）发送瞬间问题直接定位到视口顶部（`scrollTop = 0`），下方留出整屏空间从上往下流式输出。
2. **后续对话偏中间位置锚定 + 稳定 Turn Key 防闪烁**：
   - 在 `scroll-state.ts` 中新增 `computeTurnAnchorScrollTop`、`computeDynamicBottomSpacerHeight`、`computeStreamingFollowScrollTop` 与 `isChatViewportNearContentBottom`。
   - 当后续提问（`turnCount > 1`）发送时，同步预置底部留白垫片（`chat-turn-spacer`）并将最新用户提问平滑滚动至距离视口顶部约 `32%` 的偏中间位置；AI 流式吐字时垫片等量收缩，文字在问题下方空白区自然向下生长。
   - 将 `ChatMessageList.vue` 与 `MessageContent.vue` 的渲染 `:key` 从易变的 `message.id` 改为基于回合位置的稳定标识（`turn-${turnIndex}:user`、`turn-${turnIndex}:agent` 及块索引 key），移除 `.pw-chat-turn-animated` 透明度闪烁动画，并在 `useTranscriptMessages.ts` 中校验 `hasSnapshotCaughtUp` 后再裁剪历史消息，彻底根除乐观消息切换至服务端消息时的 DOM 卸载重绘闪烁。
3. **自由上下滑动与悬浮胶囊统一 + 底部对话框位置恒定锁死**：
   - 监听 `wheel` 上滑手势与主动上拉滚动条立即解除 `following`，流式期间绝不抢夺用户滚动条；移除输入框上方会引发高度抖动的块级“回到最新”按钮，统一收敛为视口底部居中的毛玻璃悬浮胶囊。
   - 根治底部输入框（`ChatComposer`）随运行状态、消息回显和排队输入上下蹦跳的问题：
     - 移除 `ChatComposer.vue` 内部动态 `v-if="helperText"` 的 `<p>`（原先在发送/结束时撑高或收缩 `26px`），以及 `ChatSession.vue` 输入框下方条件挂载的 `chatMetrics` 统计栏（原先首条消息回显时顶起 `22px`）和冗余的“排队发送当前草稿”块级按钮（原先运行中打字时顶起 `46px`）；
     - 将运行提示（`helperText`）与耗时指标（`footerText`）统一收口到 `ChatComposer.vue` 底部常驻且固定高度（`h-4`）的单行状态槽位，并将底部工具栏严格锁定为 `h-8`（`32px`），实现整个对话生命周期内底部对话框垂直位置零偏移。
   - 为 `.pw-chat-stream` 增加 `overflow-anchor: none` 杜绝浏览器原生滚动锚定干扰。

## 涉及文件
- `apps/platform-web/src/modules/chat/scroll-state.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/MessageContent.vue`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/styles/index.css`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.spec.ts`
