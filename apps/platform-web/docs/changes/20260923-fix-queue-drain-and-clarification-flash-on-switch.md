# 修复切回会话界面时历史需求澄清卡片闪现及消息队列抢跑排空无回复问题

- **日期**：2026-09-23
- **范围**：`apps/platform-web`（单服务内部修复与队列状态机优化）

## 背景与根因分析

在 `dear-agent` / `chat` 会话页面连续发送多条消息进入前端队列（`promptQueue`），随后切换到其他界面再切回时，出现以下两类连锁异常：

1. **历史「需求澄清」卡片短暂闪过随后消失**：
   - 切回页面时，`useStream` 重新连接 `/stream/events` 回放历史事件，`stream.interrupts` 会比 `stream.values.messages` / `stream.messages` 更早到达。
   - 在消息尚未完成 Hydration（`rawMessages.length === 0`）的约 100ms 窗口期内，`isClarificationActive` 判定为 `true`，且 `clarifications` 未校验 `hydrated` 状态及当前最新 `run` 是否为已完结终态（`status === "success"`），导致已在历史回合回答过的澄清卡片短暂渲染后又在消息加载完毕时消失。

2. **前端消息队列切回后瞬间全部发送、产生重复用户消息气泡且无 AI 回复**：
   - 首条消息发起新回合（`POST /runs -> 201 Created`）后，`send()` 调用 `actions.acknowledge(action.key, run.value?.run_id)`；由于 `run-actions.ts` 中 `runId: runId ?? current.value.runId` 优先使用了参数传入的旧 `run.value?.run_id`（上一轮已 `success` 的旧回合 ID），覆盖了 `dispatch()` 刚从响应体解析出的新 `runId`。
   - 同时初始 Hydration 流结束触发 `onCompleted: () => void verify(true)`，拿被覆盖的旧 `runId` 查询到 `status: "success"`，误判当前无活跃运行并调用 `stream.disconnect()` 切断新回合 SSE 流，将 `busy` 置为 `false`、`canSend` 置为 `true`。
   - `DearAgentSession.vue` / `ChatSession.vue` 的队列 `watch` 监听到 `!busy && canSend` 后，每隔 350ms 触发 `drainNextQueuedItem()`，而后端 `runtime-worker` 仍在执行首个新回合，导致后续队列消息全部命中 `409 Conflict`。
   - `send()` 在 3 次 409 重试后进入 `queueMessage()`，因本地 `busy === false` 未查出活跃 run 又递归回退调用 `send()`（每次生成新 UUID 往前端流塞入重复乐观气泡），最终返回 `true` 导致前端队列误以为发送成功并将队列全部排空。

## 改动内容

1. **修复 `acknowledge()` 旧 `runId` 覆盖 Bug**：
   - `apps/platform-web/src/modules/dear-agent/run-actions.ts`
   - `apps/platform-web/src/modules/chat/run-actions.ts`
   - 将 `runId: runId ?? current.value.runId` 改为 `runId: current.value.runId ?? runId`，确保 `dispatch()` 已捕获的新 `run_id` 绝不被旧缓存覆盖。

2. **增加 Hydration 门控与终态 Run 守卫，消除历史澄清/审批卡片闪现**：
   - `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
   - `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
   - 新增 `hydrated` 状态与 `isTerminalNonInterruptedRun` 守卫：在 `hydrated` 完成前或当前最新 `run` 处于非 `interrupted` 终态（如 `success`）时，抑制历史 `interrupts` 渲染为 `clarifications` / `reviews`。

3. **修复 `verify()` 断流条件、后台活跃回合轮询与队列 409 防排空机制**：
   - `verify(waitForTerminal)` 仅在 `actionRunId` 或明确处于 `active(run.value)` 时按单 ID 查询，否则通过 `service.runs(id)` 优先选取 `active` 的最新回合；仅当非提交态且 `latest.run_id === actionRunId` 时才允许 `stream.disconnect()`。
   - 当切回页面发现后台有 `active(run.value)` 但当前未挂载活跃 SSE 流（`!stream.isLoading.value`）时，启动 `scheduleBackgroundRunPoll` 定时同步后台运行状态，直至回合结束后自动调用 `onRefresh()` 刷新最新历史消息。
   - `send()` 新增 `sendOptions?: { fromQueue?: boolean }`，`DearAgentSession.vue` 与 `ChatSession.vue` 的 `sendQueuedContent` 传入 `{ fromQueue: true }`：队列消息遇到 `409 Conflict` 时立即通过 `verify(true)` 恢复 `busy = true`，清除乐观气泡并返回 `false`，将消息安全保留在前端 `promptQueue` 队首等待后台回合真正结束后再依次执行。
   - `displayedMessages` 在非流式加载且 `history[0].values.messages` 消息数多于当前 `messages` 时自动合并展示最新 Checkpoint 消息，确保后台完结的 AI 回复切回后立即可见。

## 涉及文件

- `apps/platform-web/src/modules/dear-agent/run-actions.ts`
- `apps/platform-web/src/modules/chat/run-actions.ts`
- `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
