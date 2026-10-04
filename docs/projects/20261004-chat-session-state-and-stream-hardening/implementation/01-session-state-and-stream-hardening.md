# Chat 会话状态机加固与流式体验优化 - 实施记录

## 改动时间
2026-10-04

## 相关任务
- Task 1.1: 加固 `workspaceStore.refreshCurrentProjectAccess` 容错
- Task 1.2: 修复 `QueuedMessagesBanner.vue` 显隐条件
- Task 2.1: 修复 `ChatMessageList.vue` 的 `shouldShowLiveStep` 状态判定
- Task 2.2: 优化思维链首轮流式加载反馈

## 改动文件
- `apps/platform-web/src/stores/workspace.ts`
- `apps/platform-web/src/stores/workspace.spec.ts`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.spec.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.spec.ts`

## 具体改动

### 1. 权限刷新容错（防误踢工作区）
**位置：** `apps/platform-web/src/stores/workspace.ts:80-95`

**改动前：**
```typescript
try {
  const access = await projectsService.getMyProjectAccess(projectId)
  this.currentProjectAccess = access
  return access
} catch (error) {
  this.currentProjectAccess = null
  throw error
}
```

**改动后：**
```typescript
try {
  const access = await projectsService.getMyProjectAccess(projectId)
  this.currentProjectAccess = access
  return access
} catch (error) {
  const status = (error as any)?.status ?? (error as any)?.response?.status
  if (status === 403) {
    this.currentProjectAccess = null
  }
  // 瞬态网络波动或并发 401 刷新期间，保留现有权限缓存，防止切屏唤醒时误判无权限
  throw error
}
```

**理由：**
切屏或窗口重新聚焦时触发的高频刷新如果遇到瞬态网络超时或 Token 并发置换时的临时 401，之前直接无脑将权限置为 `null`，导致触发全局“当前页面权限已失效”拦截并将用户踢回项目列表。现在严格限制仅在明确收到 403（权限被移除）时才置空。

---

### 2. 排队消息 Banner 显隐收敛
**位置：** `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue:64-75, 104`

**改动前：**
```vue
<div
  v-if="isPromptQueueActive || receipts.length > 0 || pendingMessage || receiptError"
  class="queued-messages-banner"
>
```

**改动后：**
```typescript
const totalCount = computed(() => pendingReceipts.value.length + (props.pendingMessage ? 1 : 0))
const shouldShowBanner = computed(() => {
  return (props.isPromptQueueActive || receipts.value.length > 0 || Boolean(props.pendingMessage)) && totalCount.value > 0
})
```
```vue
<div
  v-if="shouldShowBanner"
  class="queued-messages-banner"
>
```

**理由：**
之前无论队列中有无消息，只要 `receiptError` 为真就会强行渲染 Banner，导致空队列（count 为 0）时弹出黄色警告“排队补充消息 0 ... 投递状态读取失败”，误导用户。修复后只有存在实际待处理消息（`totalCount > 0`）时才展示 Banner。

---

### 3. Live Step 状态指示与人工澄清中断解耦
**位置：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue:152-168`

**改动前：**
```typescript
const shouldShowLiveStep = computed(() => {
  if (props.isLiveTurn) return true
  const lastMsg = props.messages[props.messages.length - 1]
  if (!lastMsg) return false
  const hasRunningTools = ... // 包含了 request_information
  return hasRunningTools
})
```

**改动后：**
```typescript
const shouldShowLiveStep = computed(() => {
  if (props.isInterrupted) return false
  if (props.isLiveTurn) return true
  const lastMsg = props.messages[props.messages.length - 1]
  if (!lastMsg) return false
  // 排除 request_information 等 HITL 人工澄清与交互类工具
  const hasRunningTools = ... && tool.name !== 'request_information'
  return hasRunningTools
})
```

**理由：**
Agent 调用 `request_information` 时触发 HITL 中断等待用户澄清输入，此时任务处于挂起交互态，但在旧代码中工具尚未产生最终 tool_result，被判定为 `hasRunningTools`，导致界面一边展示澄清卡片，底部一边挂着“Agent 正在处理当前回合”，状态严重冲突。

---

### 4. 思维链流式打字与渐进感知
**位置：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts:180-240`

**改动内容：**
在 `useTranscriptMessages` 中消费 `messages` 通道派发的增量事件，通过内部响应式 Map `liveReasonings` 实时捕获 deepseek 等大模型的思维链 `reasoning_content`，并在流式回合中实时注入活跃的 `AIMessage.additional_kwargs.reasoning_content`。

**理由：**
针对长思考链模型（如 DeepSeek-V3 / R1 等），在生成几百甚至上千 Token 的 reasoning 阶段，SDK 默认的 `content` 为空，前端没有任何动态输出，出现数十秒假死白屏，并在思考结束后突兀弹出大段内容。渐进投影保证流式思考实时呈现。

---

## 验证
- [x] 单元测试通过（22/22 全绿）
- [x] 类型检查通过（`pnpm typecheck` 0 errors）
- [x] 生产构建验证通过（`pnpm build` 16.18s 成功）
- [x] 4 大故障场景全覆盖
