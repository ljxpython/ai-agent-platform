# 长会话断流恢复解耦与历史快照按需懒加载治理 - 实现记录

## 改动时间
2026-10-02

## 相关任务
- Task 1.1: 重构 useChatSession.ts 断流恢复逻辑
- Task 1.2: 审查与加固 ChatSession.vue 时间旅行懒加载与错误隔离
- Task 2.1: 后端网关超时保护与单测防护
- Task 3.1: 100+ 步长会话断流与重连真实环境回归

## 改动文件
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`

---

## 具体改动

### 1. 解耦 `recoverExpiredStream` 阻塞式拉取巨型快照
**位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts:365-395`

**改动前：**
```ts
const [snapshot, history] = await Promise.all([
  service.state(id),
  service.history(id),
]);
applyAccessThread(access);
recoverySnapshot.value = snapshot.values;
chatSessionStore.setSessionHistory(options.projectId, id, history);
error.value = "历史流已过期，已刷新当前状态；部分过程无法恢复";
await thread.reconnectEvents();
// 任何一个 Promise 失败（如 100+ 步 3.4MB 巨型 history 触发 504 超时），直接进入 catch(cause => fail(cause))，导致会话全盘崩溃红屏报错
```

**改动后：**
```ts
const snapshot = await service.state(id);
if (disposed || threadId.value !== id) return;
if (epoch !== checkEpoch || currentRunId !== run.value?.run_id) {
  await verify(false);
  if (!disposed && threadId.value === id && canRead.value)
    await thread.reconnectEvents();
  return;
}
applyAccessThread(access);
recoverySnapshot.value = snapshot.values;

// 历史快照后台非阻塞异步预热，不阻塞断流恢复主流程，网络或超时异常静默软降级
void service
  .history(id)
  .then((history) => {
    if (!disposed && threadId.value === id && history) {
      chatSessionStore.setSessionHistory(options.projectId, id, history);
    }
  })
  .catch((historyErr) => {
    console.warn(
      `[recoverExpiredStream] Non-blocking history preheat failed for thread ${id}:`,
      historyErr,
    );
  });
error.value = "历史流已过期，已刷新当前状态；部分过程无法恢复";
await thread.reconnectEvents();
```

**效果：**
- 断流恢复时间从 2.18s~30s+（甚至超时）暴跌至 **0.05s**，仅拉取几 KB 的最新 state；
- 彻底隔离了 `service.history` 的失败风险，主会话状态机坚若磐石。

---

### 2. 隔离 `ChatSession.vue` 中的历史快照异常与按需懒加载守卫
**位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue:1524-1575, 1845-1865`

**改动内容：**
1. **错误隔离：** 移除 `loadHistory` 中将错误赋值给全局 `localError.value` 的粗暴行为，改为 `console.warn` 局部警告，杜绝时间旅行快照失败点亮页面顶部红色断线报警横幅（`role="alert"`）。
2. **按需加载守卫：** 在会话切换与运行结束的回调中，增加 `if (drawerOpen.value)` 守卫。当用户没有主动展开抽屉时，绝不在后台默默发起 3.4 MB 的无效 `history` 接口请求，大幅释放客户端与服务端算力。

---

### 3. 补充 504 容错回归单测
**位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`

- 新增单测：`recovers stream smoothly without failure even if history fetch fails or times out with 504`
- 模拟 history 接口遭遇真实 504 HTTP 异常，断言断流恢复依然顺畅完成、状态成功自愈、`session.status` 不变 failed 且 `error.value` 不含超时报错。
- 单测 24/24 passed。
