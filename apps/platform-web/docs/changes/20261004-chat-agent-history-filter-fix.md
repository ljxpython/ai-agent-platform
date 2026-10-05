# Chat 对话历史智能体过滤失效与全局列表回显根治

## 背景与问题

1. **智能体维度历史会话列表隔离失效（全局列表回显）**：
   在通用对话工作台（Chat）及 Pad / 桌面界面中，顶部选择 Agent（如 `cec2267a-d96d-47e0-8363-71b083fd7d1f`）后，左侧历史会话列表无论选择何种智能体，始终展示为全项目所有智能体混杂的全局列表（全部 39 条会话）。
2. **根因剖析**：
   - **优先级倒挂**：`ChatPage.vue` 中 `currentSelectedAgent` 计算属性原本写为 `target.value?.agentId || textParam(route.query.agentId)`。一旦之前加载过任何一个会话或目标，旧的 `target.value` 锁死在最前面，导致路由 query 变更为新 Agent 时，`currentSelectedAgent` 计算出的依然是旧 Agent，响应式 watch 无法感知变更；
   - **过滤参数被 `graphId` 错误劫持**：`loadThreads` 和 `handlePageChange` 中构造的 `metadata` 采用了 `selected?.graphId ? { graph_id: selected.graphId } : { agent_id: selected.agentId }`。由于当前所有 Agent 均配置了底层图运行时（例如 `showcase_demo` 或 `agent`），三元表达式永远取了 `graph_id`，向后端发送的查询永远按 graph 查，导致把该图下所有 Agent 的历史全量查出；
   - **Pad 交互误折叠**：`choose` 函数在 `< 1024` 时野蛮将 `sidebarCollapsed.value = true`，导致 Pad（宽度在 768px~1024px）用户在顶栏切换 Agent 时侧边栏被强行收起，重新展开后因上述两处 Bug 看到的依然是全局列表。

## 改动内容

1. **单一事实来源响应式收敛 (`ChatPage.vue`)**：
   - 优化 `selectedTarget` 与 `currentSelectedAgent` 计算属性，以用户在 URL query / 选择器中显式指定的 `agentId` 为最高优先级，未指定时降级取当前会话所属的 `target.value?.agentId`；
   - 确保顶部选择器高亮与左侧历史列表过滤响应式 0ms 联动。
2. **向后端精准传递 `agent_id` 过滤 (`ChatPage.vue`)**：
   - 将 `loadThreads` 与 `handlePageChange` 中的 `metadata` 优先级调整为：当用户选中了具体 Agent 时，坚决以 `{ agent_id: selected.agentId }` 发起服务端精准匹配与总数计数；仅当无 `agentId` 时降级按 `graph_id` 兜底；选择“全部”时传 `undefined` 查询全局。
   - 保留 `isThreadBelongToAgent` 对老版本无 `agent_id` 历史数据的向后兼容兜底。
3. **Pad 界面人机体验优化 (`ChatPage.vue`)**：
   - 调整 `choose` 侧边栏自动折叠阈值至窄屏手机端（`< 768px`）；Pad（`>= 768px`）及桌面端保持侧边栏当前展开状态，方便用户切换 Agent 后立刻直观查阅匹配的历史会话。
4. **单测契约加固 (`ChatPage.spec.ts`)**：
   - `mockList` 与 `count` 支持 `agent_id` 字段的精确匹配，显式断言选择不同 Agent 时向服务端发送带有 `{ metadata: { agent_id } }` 的请求；
   - 全量 45 个测试套件（210 项单测）全部通过，`typecheck` 0 错误，生产打包顺利完成。

## 涉及文件

- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.spec.ts`
- `apps/platform-web/docs/changes/20261004-chat-agent-history-filter-fix.md`
- `docs/CONTEXT.md`
- `docs/FEATURES.md`
