# Chat 智能体切换与后台审批轮询穿透隔离修复

- **日期**：2026-10-05
- **服务**：platform-web
- **背景**：用户在 `dearflow_agent` 会话中点击通过审批后，该会话进入后台运行（resumed run）。当用户点击顶部 Agent 下拉框切换至 `showcase_demo` 时，左侧历史会话列表一直停留在 `dearflow_agent` 的会话队列，筛选未能生效。
- **根因**：
  1. **会话池后台事件穿透**：`useChatSessionPool` 在切换前后台活动 entry 时，仅修改了前一个实例的 `visible.value = false`，未解绑其 `view.value` 引用。导致后台运行的审批会话每 1.5 秒轮询 run 状态时，通过闭包直接触发当前页面的 `loadThreads()`；
  2. **并发轮询破坏列表请求 Epoch**：后台轮询触发的 `loadThreads()` 递增了 `listEpoch`，导致用户切换 Agent 产生的新请求被误判为过期响应（`requestEpoch !== listEpoch`）而直接被静默丢弃；
  3. **防御性重置缺失**：用户在顶部选择器切换 Agent 时，未预先清空 `threads.value` 与激活 loading 态，且依赖响应式计算属性取值存在异步时差。
- **改动**：
  1. `useChatSessionPool.ts`：在 `attachView` 切换实例时，彻底解绑 `previous.view.value = undefined`；
  2. `ChatSessionPool.vue`：在 `onRefresh` 中严密守卫 `entry.visible.value`，后台实例的刷新仅标记 `entry.needsRefresh = true`，绝不穿透调用前台视图；
  3. `ChatPage.vue`：抽取 `resolveSelectedAgent`，支持 `loadThreads(true, overrideAgentId)` 显式锁定目标 Agent；在 `choose` 选择时立即重置 `threads.value = []` 并开启 `listLoading`；
  4. **解耦智能体调用与会话列表远程拉取**：彻底移除会话内部在工具调用、流式结束、审批流转时触发全量 `loadThreads()` 的远程网络开销，将侧边栏列表远程查询严格收敛至“选择/切换智能体、初次加载/切换项目、手动翻页/加载更多”时；
  5. **本地响应式轻量增量更新 (Local Reactive Patch)**：在 `ChatPage.vue` 中引入 `touchLocalThread(threadId, status)`，会话状态变更直接在前端响应式置顶与修改时间，创建新对话时使用严格符合 `ChatThread` 规范的轻量对象完成乐观插入；
  6. 完善 `ChatPage.spec.ts` 验证 `onRefresh` 不再触发远程 `mockList`。
- **涉及文件**：
  - `apps/platform-web/src/modules/chat/composables/useChatSessionPool.ts`
  - `apps/platform-web/src/modules/chat/components/ChatSessionPool.vue`
  - `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
  - `apps/platform-web/src/modules/chat/composables/useChatSessionPool.spec.ts`
  - `apps/platform-web/src/modules/chat/pages/ChatPage.spec.ts`
