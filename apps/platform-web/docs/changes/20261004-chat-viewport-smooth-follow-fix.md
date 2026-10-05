# Chat 对话体验优化（视口倒滚/流式跟随/消息闪退）与权限抖动根治

## 背景与问题

1. **发送消息视口倒滚跳跃（用户体验极差）**：
   用户发送消息时，消息上屏后视口先向上平滑滚动定位到上一个历史对话并停顿片刻，最后才又弹回刚发送的最新消息。
   根因：`ChatSession.vue` 在 `send()`、`sendQueuedContent()`、`resendQueuedMessage()` 中，乐观消息赋值后立即同步调用 `anchorLatestUserTurn(true)`；此时 Vue 尚未将新消息渲染成 DOM，`getLatestUserElement(vp)` 抓到的是上一个回合的旧用户元素，触发了向旧消息的平滑滚动；随后 `watch(displayedMessages)` 在微任务刷新后再次触发 `anchorLatestUserTurn`，形成反向二次回弹。
2. **流式输出每 180ms 机械阶梯式暴跳卡顿**：
   `requestSmartStreamingFollow` 内部硬编码了 `programmaticScrollUntil = Date.now() + 180`，导致大模型吐字期间每秒数十个 token 的滚动跟随被粗暴拦截为 5.5 fps 的机械跳帧。
3. **56vh 巨型空气垫片与动态收缩互相对冲**：
   视口底部塞入 `minHeight: 56vh` 的空白垫片，导致初次进入多轮对话时底部存在大片空白；流式期间垫片等量收缩与 scrollTop 下滚互相对冲，滚动条剧烈抖动且反复触发重排。
4. **发送消息瞬间消失 Bug（气泡蒸发）**：
   用户点击发送后，输入框清空且气泡瞬间蒸发，等后端完整消息回传后才又出现。
   根因：`ChatSession.vue` 在 `displayedMessages` 计算属性内部违背 Vue 纯函数规范塞入了微任务副作用：`if (hasOptimisticEchoed(resolved, optimisticUserMessage.value)) queueMicrotask(() => setOptimisticUserMessage(null))`。由于 `resolved` 本身就包含了刚加入的 `optimisticUserMessage`，导致其在计算属性里自己比对命中自己，在 0.1ms 内将乐观消息清空，造成气泡瞬间闪退。
5. **切屏/休眠突发“当前页面权限已失效”Bug（全屏大黄条阻断）**：
   切屏回退或窗口 focus 时突然弹黄条提示权限失效，F5 刷新又恢复。
   根因：
   1. `workspace.ts` 中 `refreshCurrentProjectAccess()` 在 catch 块中，当遇到 403（网络唤醒延迟、Token 刷新临界点）时，将 `this.currentProjectAccess = null` 彻底抹零自爆；
   2. `WorkspaceLayout.vue` 中 `routeAccessAllowed` 计算属性直接断定无权限，卸载 `<router-view>` 并清空会话池；
   3. `WorkspaceLayout.vue` 中事件监听使用匿名箭头函数绑定，导致 `onUnmounted` 时 `removeEventListener` 完全失效造成内存泄漏与跨组件幽灵触发。

## 改动内容

1. **收敛回合锚定与目标回合感知校验**：
   - 彻底移除 `ChatSession.vue` 发送分支中同步无脑调用的 `void anchorLatestUserTurn(true)`，统一收敛由 `watch(displayedMessages)` 在 Vue 将新消息 patch 到 DOM 后统一精准触发。
   - 重构 `useChatViewport.ts` 中的 `getLatestUserElement(vp, targetTurnIndex)` 与 `anchorLatestUserTurn`：增加期望回合索引（`targetTurnIndex`）匹配校验。若 DOM 尚未就绪，等待微任务帧；若仍未就绪则安全滚向内容最末尾，绝对不使用上一轮历史旧元素算 offsetTop，从逻辑和物理上根除倒滚回弹。
2. **升级 60fps / 120fps 原生 rAF 单帧流式跟随**：
   - 废除 `requestSmartStreamingFollow` 内部的 180ms 锁死拦截，改用浏览器原生 `requestAnimationFrame` 单帧批处理跟随，流式吐字顺滑无感。
   - 在 `syncBottomSpacerHeight` 中增加微幅差值防抖保护（高度差 < 4px 时不反复写 ref），消除 Layout Thrashing 与组件重绘。
3. **移除 56vh 突兀垫片**：
   - 清除 `ChatSession.vue` 底部垫片上的 `minHeight: 56vh`，改为仅在 `bottomSpacerHeightPx > 0` 时自适应生效，回复变长后自然归零收起。
4. **彻底切除 computed 内自杀式副作用代码**：
   - 将 `ChatSession.vue` 的 `displayedMessages` 恢复为纯粹的纯计算属性，移除所有 `queueMicrotask` 清空乐观消息的逻辑；由权威消息来源 `watch([messages, latestHistoryMessages])` 单向数据流接管乐观消息的自然交接。
5. **权限 SWR 驻留与事件监听器严谨解绑**：
   - `workspace.ts`：移除 catch 块中 403 抹零逻辑（仅在 404 项目已彻底不存在时重置），实现真正的 Stale-While-Revalidate；
   - `WorkspaceLayout.vue`：加固 `routeAccessAllowed` 计算属性，只要本地持有所属项目有效授权，前台视图坚决放行；`watch(routeAccessAllowed)` 改为仅在明确退登（`!authStore.isAuthenticated`）时才清空会话池；
   - 改用具名函数注册和清理 `visibilitychange`、`focus`、`platform-access-denied` 事件，根治匿名函数无法注销造成的内存泄露与单测污染。
6. **测试与类型加固**：
   - 在 `useChatViewport.spec.ts` 补充针对 DOM 未渲染时防倒滚的回归测试用例。
   - 在 `WorkspaceLayout.spec.ts` 的 `afterEach` 中补充 `vi.clearAllMocks()`，清理跨测试 mock 污染。
   - 全量回归 46 个测试套件（212 个单测）100% 通过，`pnpm typecheck` 0 errors，`pnpm build` 生产打包成功。

## 涉及文件

- `apps/platform-web/src/modules/chat/composables/useChatViewport.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useChatViewport.spec.ts`
- `apps/platform-web/src/stores/workspace.ts`
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- `apps/platform-web/src/layouts/WorkspaceLayout.spec.ts`
- `docs/CONTEXT.md`
- `docs/FEATURES.md`
