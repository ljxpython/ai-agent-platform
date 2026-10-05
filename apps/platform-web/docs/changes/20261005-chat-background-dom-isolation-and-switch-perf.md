# 会话流式中切换会话卡死根因修复与后台 DOM 隔离优化

## 背景

用户在执行长链路、高密度 SSE 事件流会话（如五子棋多步模型调用会话 `2923e4ae-a04f-4417-b76f-0c3af5f1f86a`）时，尝试点击左侧会话列表切换到其他会话，发现界面卡住，怀疑是自身系统问题。

## 根因定位

1. **非电脑系统问题**：后端在长执行链路产生高频 SSE 事件流。
2. **后台停靠实例无节制虚拟 DOM 比对**：
   - 多会话池机制下，非活跃会话被 Teleport 到 `parked` 隐藏容器中。
   - 虽然父级容器带 HTML `hidden` 属性，但 Vue 并不会跳过子树渲染。`ChatSession.vue` 内部挂载的大量复杂组件（`ChatMessageList`、`MessageContent`、`ChatComposer` 等）在后台依然随着每次流式 chunk 频繁触发虚拟 DOM 递归 Diff 和 Patch，严重挤占浏览器主线程事件循环，导致用户点击事件无法被及时响应。
3. **路由跳转缺乏即时反馈与重复触发保护**：
   - 切换会话时未先更新乐观选中高亮；
   - 未拦截对当前活跃会话的重复点击，造成无效导航开销。

## 改动内容

1. **`ChatSession.vue`：后台会话 DOM 虚拟化隔离**
   - 引入 `v-else-if="props.visible === false"` 条件分支，当实例位于后台停靠容器时，仅渲染轻量占位节点 `<div class="hidden" aria-hidden="true" />`；
   - 彻底消除后台高频消息导致的虚拟 DOM Diff 损耗与主线程 CPU 占用，切回前台时毫秒级按需水合。
2. **`ChatPage.vue` & `DearAgentPage.vue`：切换交互防抖与乐观选中**
   - 重构 `openThread(id)`，拦截当前已选中的重复点击 (`selectedThread.value === id`)；
   - 点击时立即乐观设置高亮与 SessionStore，提升用户感知响应速度。

## 涉及文件

- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
