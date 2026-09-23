# 消息出队与即时提交会话执行态感知优化

## 背景

用户在连续对话与消息排队机制中反馈：
在首条消息发出或排队消息出队开始执行时，前端页面缺乏及时的“AI 正在执行”与“Agent 正在组织答复...”小提示（页面呈现一片空白，无法感知 AI 是否已在处理）。

根本原因分析：
1. **执行态（Running）定义脱节**：之前传给 `ChatMessageList`、`TrajectoryView`、`ChatAgentStatusBar`、`ChatComposer` 等组件的 `:is-running` 仅依赖 `busy`。在用户点击发送设置乐观消息（`optimisticUserMessage`）、或排队消息出队（`drainNextQueuedItem`）的窗口期内，底层 SSE 连接尚未建立，后端 Run 尚未生成或处于重试退避中，`busy` 短暂为 `false`。
2. **小提示与指示条丢失**：因 `props.isRunning` 短暂为 `false`，导致 `ChatMessageList` 中负责展示微动效 loading 的卡片（`Agent 正在组织答复...`）以及底部的 `Agent 正在处理当前回合` 进度指示条完全不渲染，造成界面静止留白。
3. **出队反馈不明显**：消息出队提交时，队列第一项在移入会话流的瞬间缺乏明确的“正在调取出队并执行中...”视觉反馈。

## 改动内容

1. **统一综合会话运行态 `isSessionRunning`（`DearAgentSession.vue` & `ChatSession.vue`）**：
   - 综合计算属性：涵盖 `busy`、`isDrainingQueue`（出队中）、`checking`（发送中）、`actions.current.status === 'submitting'` 以及 `Boolean(optimisticUserMessage)`；
   - 只要有排队出队或乐观消息上屏等待执行，0 毫秒即可确立 `isSessionRunning = true`；
   - 将 `ChatMessageList`、`ChatAgentStatusBar`、`TrajectoryView`、`ChatComposer`、`SessionDrawer` 统一对接 `isSessionRunning`，确保状态机严密闭环。

2. **出队反馈与交互保护增强（`QueuedMessagesBanner.vue`）**：
   - 引入 `isDraining` prop；当第一项排队消息正在调取出队并发起连接时，徽章高亮显示为蓝色的“#1 正在调取执行中...”，辅以 `animate-ping` 呼吸灯动效与“· 正在建立会话连接”提示；
   - 出队过程中对正在出队项的操作按钮（下移、删除、恢复草稿）实施保护性禁用，杜绝并发竞争。

## 涉及文件

- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.spec.ts`
- `apps/platform-web/docs/changes/20260923-queued-message-draining-execution-state.md`
