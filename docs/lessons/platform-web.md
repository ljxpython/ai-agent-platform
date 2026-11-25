# Platform Web 经验库

## [坑] 权限查询失败不等于权限撤销
- **场景：** 切屏、后台刷新、项目切换与资源拒绝交织。
- **错误：** 把未加载/网络失败当撤权，任意 403 触发全局刷新，或以“有角色”放行所有页面。
- **正确：** 区分不可确认与明确拒绝，保留同身份同项目的具体权限快照；拒绝事件带作用域；回归同时覆盖瞬态故障、角色降级、真实撤权与账号切换。
- **日期：** 2026-10-05；本会话用户批准记录。

## [坑] 暂停当前 SSE 不会阻止 SDK 后续新订阅
- **场景：** 后台提交新 Run 或投影更新，SDK 又建立事件订阅，占满浏览器连接槽。
- **正确：** 后台新订阅握手后暂停，防止挂起 ready Promise；后台不自动重连，切回恢复。验收同时核对后台终态、消息只消费一次和 SSE 数量。
- **日期：** 2026-10-05；用户批准记录。

## [坑] 多轮对话下历史 Run 列表加载守卫缺陷与防误报
- **场景：** 同一 Thread 产生多轮对话（多次 Run）后切换至轨迹或诊断视图。
- **错误：** 仅依赖 `!session.run.value?.run_id` 作为拉取历史 Run 的守卫，导致内存刚执行完 Run 的会话在切到轨迹视图时跳过历史 runs 查询，使多 Run 下拉选择器无法渲染；或者将模型备选重试（Fallback）直接判定为整屏报错。
- **正确：** 进入轨迹视图时无条件拉取当前 Thread 历史 runs，并与内存实时活跃 run 进行安全去重合并；模型 Fallback 成功保持 Completed 绿标，仅以 Amber 警示框展示重试记录。
- **日期：** 2026-10-07；Agent 可观测性与追踪补齐项目。

## [坑] Vue 3 多数据源 watch 在 immediate 模式下的参数解构防崩
- **场景：** 使用 `watch([() => a, () => b], ... , { immediate: true })` 监听多个响应式依赖并立即触发初始化。
- **错误：** 在回调参数中直接进行数组解构 `([newA, newB], [oldA, oldB])`。首次执行时 Vue 传入的 `oldValue` 为 `undefined`，解构引发 `TypeError: undefined is not iterable`，导致 watcher runner 静默报废且后续依赖变化不再响应。
- **正确：** 回调参数保持 `([newA, newB], oldValues)`，在函数体内通过安全可选链读取 `const oldA = oldValues?.[0]; const oldB = oldValues?.[1];`。
- **日期：** 2026-10-10（用户批准）；非 Docker 后台任务兼容 A/B 前端增量项目。

## [坑] 非 HTTPS 下裸调 navigator.clipboard.writeText 会静默失效
- **场景：** 页面部署在公网 HTTP IP（非 HTTPS / 非 localhost），组件实现复制 Thread ID、Trace ID、Run ID 或日志操作。
- **错误：** 直接调用 `navigator.clipboard.writeText(...)` 并在 `catch` 中静默忽略或提前将 `copied` 置为 `true`。非 Secure Context 下浏览器不暴露 `navigator.clipboard`，点击毫无反应或误报“已复制”。
- **正确：** 统一复用带 `document.execCommand('copy')` 降级路径的 `copyText`（`@/utils/clipboard`），并仅在返回 `true` 时更新复制成功状态提示。
- **日期：** 2026-11-25；用户批准记录，见 `apps/platform-web/src/utils/clipboard.ts`。
