# fix: 修复停止按钮竞态导致"未找到可停止的当前运行"报错

## 背景

Agent 执行过程中点击停止按钮，偶发报错"未找到可停止的当前运行"并在顶部显示红色错误提示。

## 根因

`stop()` 在发 cancel 请求前会调 `verify(false)` 拉最新 run 状态。当 Agent 刚好执行完毕、服务端 run 已进入终态（success/error），但前端 stream 还在传输时，`verify()` 把终态 run 覆写进 `run.value`，导致 `active()` 返回 false，直接 throw 错误，cancel 请求根本未发出。

竞态时序：
```
T1: 后端 run.status → success（已终态）
T2: 用户点击停止（stream.isLoading=true，前端仍显示"正在执行"）
T3: verify() 拉回终态 run，active() = false → throw
```

## 修改内容

- **`apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`** — `stop()` 函数
- **`apps/platform-web/src/modules/chat/composables/useChatSession.ts`** — `stop()` 函数（同逻辑）

两处改动一致：
1. stream 仍在 loading 时，优先用已知 runId 直接 cancel，跳过前置 verify
2. verify 后 run 已终态时，静默刷新状态并 onReconnect，不再 throw 错误
