# 前端历史会话回放防误触（Replay Immunity）与上下文整理状态机收敛

**日期**：2026-10-27
**服务**：`platform-web`
**类型**：`fix`

## 背景与问题

当用户在界面中打开或刷新已完成的历史会话（例如已达到终态 `status: success` 的会话）时，LangGraph 协议的 `/threads/{id}/stream/events` 连接会从游标开始全量重播该会话历史上产生的全部事件帧（可达万帧级别）。
历史流中如果包含中间件派发的上下文整理事件（`seq: conversation_offloading: started`），前端 `useChatSession` 盲目消费该事件，误将历史瞬间发生的整理态当成当前实时的活跃任务，导致对话框顶部长时间闪烁或永久悬挂“🔄 正在整理上下文...”的悬挂提示。

## 改动内容

1. **`apps/platform-web/src/modules/chat/composables/useChatSession.ts`**：
   - 在 `useChannelEffect(stream, ["custom"], ...)` 事件消费者入口增加精准终态判定：
     - 若当前已知最新 `run.value` 已经处于终态（`!active(run.value)`），且无任何实时发送/流式交互（`!stream.isLoading.value && !streamInFlight.value`），判定为纯历史会话重放（Replay），丢弃所有历史 `started` 整理过渡态事件。
     - 若事件携带 `run_id` 且与当前活跃任务的 `currentRunId` 不匹配，说明属于过去运行回合，直接丢弃。
   - 在 `verify()` 状态自愈兜底处，一旦核查最新 run 已达终态，强制执行 `clearOffloadState()` 立即清除任何未收敛的整理残留状态。

2. **`apps/platform-web/src/modules/chat/components/ChatSession.vue`**：
   - 显式在停止确认（`onStopConfirmed`）时调用 `clearOffloadState()`，确保取消与中断时状态干净复位。
   - 优化重连（`handleReconnect`）逻辑，清除旧有报错并重设乐观状态。

3. **`apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`**：
   - 增加针对已完结历史会话的重放免疫（`replay immunity`）专项单测，确保历史事件不再点亮 `isOffloading`。
   - 全部 51 项测试跑绿。

## 验证结果

- **单元测试**：`pnpm run test:run src/modules/chat/composables/useChatSession.spec.ts` 51/51 项全部通过。
- **类型检查**：`vue-tsc --noEmit` 0 报错通过。
- **端到端测试**：通过 Playwright 自动化访问 `d98998bf` 与 `4af71d7c` 两大历史超长会话，经过 8-12 秒全量 10,000 帧回放消费，界面全程未触发任何“正在整理上下文”浮条，截图留证通过。
