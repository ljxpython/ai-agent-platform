# 修复消息队列状态机分流、前端排队守卫与横幅展示缺陷

## 背景

用户在连续输入消息时，后续消息直接作为普通人类消息直发并冲撞后端（导致 `409 Conflict`），且前端消息队列横幅（`QueuedMessagesBanner`）未展示。
经深度剖析，此前因历史澄清表单残留导致 `hasPendingInterrupts` 恒为 `true`，用户发送时碰巧走进了 `if (!canSubmit.value)` 的降级保护分支入队；当修复表单残留后，由于 `isSessionRunning` 遗漏了 `promptQueue.queue.value.length > 0`，且 `ChatComposer` 输入框仅根据窄化的 `isRunning` 判断排队，使得在网络提交间隙和队列已有消息时，后续回车绕过了队列直接触发直发。

## 改动内容

1. **`DearAgentSession.vue` & `ChatSession.vue`**：
   - 将 `promptQueue.queue.value.length > 0` 纳入 `isSessionRunning`；
   - 在 `send(queued = false)` 中完善 `shouldQueue` 守卫，涵盖运行中、提交中、乐观等待中以及已有排队项的全场景，杜绝并发直发冲撞；
   - 向 `ChatComposer` 传递 `:has-queued-items="promptQueue.queue.value.length > 0"`。

2. **`ChatComposer.vue` (dear-agent & chat)**：
   - 引入 `hasQueuedItems?: boolean` prop；
   - 增加 `isQueueMode = computed(() => (props.isRunning || Boolean(props.hasQueuedItems)) && Boolean(props.canQueue))`；
   - 在排队模式下，当输入框有文字时常驻 `<kbd>↵</kbd> 排队` 与 `补充要求` 按钮，按回车强制走 `@queue`；
   - 细化 `helperText` 提示文案。

3. **`QueuedMessagesBanner.vue`**：
   - 第一条排队消息状态文案对齐为 `#1 等待自动执行 · 当前轮次完成后自动发送`，避免误导性的“正在调取”；
   - 后序项展示 `#2 排队等待中 · 顺延等待处理`，并保留完整的排序、恢复草稿与删除能力。

4. **`DearAgentPage.vue` & `ChatPage.vue`**：
   - 恢复基于 `mountVersion` 的稳定组件 key，避免新建会话首次发消息生成 threadId 时因 key 突变而重新挂载会话。

## 涉及文件

- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/dear-agent/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/chat/components/ChatComposer.spec.ts`
- `apps/platform-web/src/modules/dear-agent/components/ChatComposer.spec.ts`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.spec.ts`
