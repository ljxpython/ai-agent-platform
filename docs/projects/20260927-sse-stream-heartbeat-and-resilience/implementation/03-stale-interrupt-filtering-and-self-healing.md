# 实现记录 03：历史僵尸中断过滤与审批状态自愈机制

## 背景与目标
在多轮工具调用（HITL 审批）场景中，上游 GraphHarbor 在 SSE 事件重放阶段会重新推送已解决的历史中断事件，导致前端 `stream.interrupts` 混入已失效的旧审批项。当用户针对旧审批项提交时，前端校验发现当前后端状态已推进，触发 `审批请求已变化` 报错且界面卡死在旧卡片上。
本改动目标：在前端构建权威状态对齐与自愈过滤机制，自动剔除过期历史中断，并在状态变更时自动刷新为最新审批项，彻底解除用户死锁。

## 改动文件
- `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.ts`
- `apps/platform-web/src/modules/chat/composables/useSessionInterrupts.spec.ts`

## 核心实现
1. **引入 `resolvedReviewIds` 响应式集合**：
   记录已被消费或失效的审批项 ID，在 `reviews` 计算属性中过滤掉不在当前生命周期的历史中断。
2. **权威状态主动同步 (`syncAuthoritativeReviews`)**：
   当 `stream.interrupts` 发生变化时，异步拉取权威 `service.state(threadId)`，对比后自动将非当前活跃的僵尸中断标记至 `resolvedReviewIds`，阻止其渲染到 UI。
3. **`approve()` 提交时自愈防线**：
   若提交时检测到前后端状态不一致，自动将已不存在于后端当前 Checkpoint 的旧 ID 剔除，使前端界面立即响应式切换至最新审批项，消除死锁。

## 验证证据
- `pnpm test:run src/modules/chat/composables/useSessionInterrupts.spec.ts` (2 passed)
- `pnpm test:run src/modules/chat/` (39 test files passed, 173 passed, 1 skipped)
