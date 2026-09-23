# 敏感工具审批中断状态优化与回合处理指示条精准化

## 背景

在 Agent 对话中，用户反馈了两处破坏交互体验与状态展示合理性的问题：
1. **工具状态过早标为“未完成 / 已中止”**：当工具（如 `write_file`）触发审批安全中断（Interrupt）挂起等待用户审批时，因流式连接暂时断开（`running=false`），前端 `buildTranscript` 将未完成工具粗暴标为 `incomplete`（未完成 / 已中止），随后才弹出审批卡片，导致用户困惑“为什么我还没批准就已经中止了”。
2. **“Agent 正在处理当前回合”拖泥带水残留**：当 Agent 已经打完所有文字、流式传输结束，用户已在阅读完整回复时，因后台 `verify(true)` 仍在轮询 Run 终态，底部的 `Agent 正在处理当前回合` 指示条依然高亮挂起数秒才突然消失，造成界面卡顿和迟钝感。

## 改动内容

1. **工具中断状态精准识别（`transcript.ts`）**：
   - 在 `modules/dear-agent/transcript.ts` 与 `modules/chat/transcript.ts` 中增强 `isInterruptError` 识别；
   - 明确将触发审批中断（Interrupt）的工具从 `incomplete` 判定中豁免，保持 `running` 活跃等待态；
   - 彻底解决工具未决时过早且误导性展示“未完成 / 已中止”的问题。

2. **工具审批态感知与徽章增强（`ToolResult.vue`）**：
   - 在 `modules/dear-agent/components/ToolResult.vue` 与 `modules/chat/components/ToolResult.vue` 中引入 `isAwaitingReview`；
   - 工具命中待办审批中断时，状态文案显示为 **“等待审批”**，徽章呈现温暖警示的琥珀色呼吸光效；非审批待决态呈现蓝色“执行中”，与下方审批决策卡片自然呼应。

3. **回合处理指示条精准化与 0 延迟收敛（`ChatMessageList.vue`）**：
   - 在 `modules/dear-agent/components/ChatMessageList.vue` 与 `modules/chat/components/ChatMessageList.vue` 中，将底部指示条展示条件由粗暴的 `isRunning` 升级为严密的 `shouldShowLiveStep`；
   - 助手文本已输出完毕且流式传输已结束时，**立即隐藏 `Agent 正在处理当前回合`**；仅在真正需要向用户表达“思考中 / 运行工具中”时展示，彻底消除文字输出完毕后的几秒钟逗留。

4. **会话终态探测加速（`useDearAgentSession.ts` 与 `useChatSession.ts`）**：
   - 优化 `verify` 轮询初始探测间隔（首轮由 500ms 缩短为 150ms），使得正常结束的 Run 能够快 70% 完成终态对齐，减少 busy 状态的无谓逗留。

## 涉及文件

- `apps/platform-web/src/modules/dear-agent/transcript.ts`
- `apps/platform-web/src/modules/chat/transcript.ts`
- `apps/platform-web/src/modules/dear-agent/components/ToolResult.vue`
- `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- `apps/platform-web/src/modules/dear-agent/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/dear-agent/transcript.spec.ts`
- `apps/platform-web/src/modules/dear-agent/components/ChatMessageList.spec.ts`
