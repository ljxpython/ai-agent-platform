# 前端超时治理、停止确认与终态门禁实装

日期：2026-10-07；对应 T11 任务。在 detached HEAD 独立工作区实装前端治理方案，满足 GraphHarbor post42 契约与 F01-F10 规范。

## 1. 架构与改动细节

### 1.1 服务层 (session.service.ts)
- 保留原有轻量 `cancel` 方法保证既有测试向后兼容。
- 新增窄方法 `cancelAndWait(threadId, runId)`：通过内置授权 `read` 发送 POST JSON body `{"wait": true, "action": "interrupt"}`，包含 `x-project-id` header 与路径校验转义，平台网关可单请求完成取消并等待 Worker 执行退出确认。
- 单测：`session.service.spec.ts` 11/11 项全部通过。

### 1.2 状态机与 Composable (useChatSession.ts)
- **消灭布尔地狱**：导出强类型联合类型 `SessionTurnState` (`idle` | `running` | `stopping` | `stop_unconfirmed` | `stopped` | `timeout` | `awaiting_review` | `error`) 与 `SessionStopState` (`idle` | `stopping` | `unconfirmed` | `stopped`)，由 Composable 统一派生单一事实源，避免组件层拼装冲突。
- **可靠停止与双通道容错**：`stop()` 调用 `cancelAndWait`；若初次取消请求超时或失败，转入 `stop_unconfirmed` 并暴露 `verifyStop()`。`verifyStop()` 优先回查目标 Run 状态，若已终态直接就地收敛，若仍 active 才重发 cancelAndWait，彻底规避 400/409 死锁。
- **防状态串扰与提交阻断**：`resumeInterruptedRun` 拦截 `cancel_requested`，严禁把停止运行误当 HITL 恢复；`send()` 与 `queueMessage()` 增加 `stopping` / `unconfirmed` 顶层一票否决，封锁提交；新轮次 `send()` 重置 `stopState = "idle"`。
- 单测：`useChatSession.spec.ts` 31/31 项全部通过。

### 1.3 UI 表现与输入管控
- **ChatAgentStatusBar.vue**：打破原有 `v-if="isInterrupted || error"` 结构限制，全面接入 `turnState`；`timeout` 展示黄色警示胶囊（“上一回合执行超时，已完成的内容已保留”，不带多余操作按钮）；`stopping` 展示转圈状态；`stop_unconfirmed` 展示“停止结果待确认”并提供【核实停止】操作；HITL 仅在真正需要审批时展示“等待人工确认”及【查看审批】；390px 移动视口自然换行不挤爆。
- **ChatComposer.vue**：在 `stopping` 与 `stop_unconfirmed` 期间，`canSubmitFreshOrQueue` 顶层一票否决，全量封锁发送、队列入口与 Enter 提交，仅允许纯文本编辑草稿。
- **ChatSession.vue**：将 `turnState` 统一下发至状态条与 Composer；浮动停止按钮与状态条接入 `handleStop` 与 `handleVerifyStop`；顶层 `send()` 增加停止阻断守护。
- 单测：`ChatAgentStatusBar.spec.ts` (7/7)、`ChatComposer.spec.ts` (10/10) 全部通过。

### 1.4 推荐问题终态门禁 (useFollowUpSuggestions.ts)
- 接入 `turnState` 与 `runStatus` 门禁；当处于 `timeout`、`error`、`stopping`、`stop_unconfirmed`、`stopped`、`awaiting_review` 或 `runStatus !== "success"` 时严格抑制后续建议生成，彻底消除半截回答误触发推荐漏洞，且与 `verify(true)` 权威完成态时序对齐。
- 单测：`useFollowUpSuggestions.spec.ts` 7/7 项全部通过。

## 2. 验证证据

在 `apps/platform-web` 执行全套工程验证：
```bash
rtk pnpm test:run src/services/threads/session.service.spec.ts \
  src/modules/chat/composables/useChatSession.spec.ts \
  src/modules/chat/composables/useSessionConnection.spec.ts \
  src/modules/chat/composables/useSessionInterrupts.spec.ts \
  src/modules/chat/composables/useFollowUpSuggestions.spec.ts \
  src/modules/chat/composables/usePromptQueue.spec.ts \
  src/modules/chat/components/ChatAgentStatusBar.spec.ts \
  src/modules/chat/components/ChatComposer.spec.ts \
  src/modules/chat/components/QueuedMessagesBanner.spec.ts \
  src/modules/chat/run-actions.test.ts
# 结果：10 个测试文件，108 项测试全部通过（108 passed, 0 failed）

rtk pnpm typecheck
# 结果：vue-tsc --noEmit 零错误通过（TypeScript: No errors found）

rtk pnpm lint
# 结果：0 errors

rtk pnpm build
# 结果：Vite 生产构建成功打包（built in 1.41s）
```

所有改动严格保持在工作区，未执行任何未授权的 git commit 或 git push。
