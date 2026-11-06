# 前端 Markdown 产物链接拦截下载与空闲会话长连接断开误报治理 - 任务拆分

## Phase 1: 仓库基线同步与确认

### Task 1.1: 提交会话删除死锁治理成果并推送到远程仓库
- **改动内容：** 提交上一阶段针对 `thread_lifecycle.py` 外部任务终态报错放行、`service.py` 乐观剔除 `thread_access`，以及 `docs/CONTEXT.md` 的改动，推送到 GitHub 远端 `main` 分支。
- **代码位置：**
  - `apps/runtime-service/src/runtime_service/thread_lifecycle.py`
  - `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
  - `docs/CONTEXT.md`
- **预期结果：** 本地工作区干净，远端仓库包含最新的删除死锁治理代码。
- **验证项：** `git status` 无未提交文件，`git log -n 1` 提交信息规范。
- **状态：** `[ ]` 待开始（等待用户危险操作确认后执行）

## Phase 2: Markdown 产物协议放行与一键原生下载

### Task 2.1: Markdown 协议白名单扩充与属性标记
- **改动内容：**
  - 在 `markdown.ts` 的 `SAFE_PROTOCOLS` 中加入 `"artifact:"`。
  - 在 `link_open` 规则中，检测到以 `artifact://` 开头的链接时，不添加 `target="_blank"`，而是打上 `data-artifact-id` 属性。
- **代码位置：** `apps/platform-web/src/utils/markdown.ts`
- **预期结果：** Markdown 渲染后生成带有正确 `artifact_id` 属性的原生链接，且不会被洗为 `#`。
- **验证项：** `markdown.spec.ts` 补充针对 `artifact://` 协议渲染的单测。
- **状态：** `[ ]` 待开始

### Task 2.2: 产物链接全局/局部点击拦截与流式下载
- **改动内容：**
  - 在消息内容渲染组件（或 Chat 容器）建立针对 `a[href^="artifact://"]` 的点击事件监听。
  - 阻断默认跳转行为，提取 `artifact_id`。
  - 调用 `workspaceService` 获取产物对应的工作区文件流，自动触发浏览器原生文件下载。
  - 若产物拉取失败，弹出轻量级错误通知 Toast。
- **代码位置：**
  - `apps/platform-web/src/modules/chat/components/ChatMessageItem.vue` / `ChatMessageContent.vue`
  - `apps/platform-web/src/services/threads/workspace.service.ts`
- **预期结果：** 点击 `[下载 PPTX]` 链接时，不再新开标签页，而是立刻在浏览器底部唤起该 PPTX 文件的原生下载。
- **验证项：** 组件单测模拟点击 `artifact://` 链接，断言 `preventDefault` 被调用且下载服务被触发。
- **状态：** `[ ]` 待开始

## Phase 3: 会话重连断流异常收敛与防误报

### Task 3.1: 补充非致命流断开错误类型
- **改动内容：**
  - 在 `useChatSession.ts` 的 `isNonFatalStreamError` 函数中加入 `"Event stream closed"` 和 `"Protocol event stream closed"` 关键字。
  - 确保此类由网络层或空闲连接断开抛出的错误不会穿透到致命错误流。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **预期结果：** `isNonFatalStreamError` 正确识别 `Event stream closed.` 异常并返回 `true`。
- **验证项：** `useChatSession.spec.ts` 补充单测用例。
- **状态：** `[ ]` 待开始

### Task 3.2: 唤醒空闲会话重连失败静默防护
- **改动内容：**
  - 在 `watch([() => options.visible?.value, ...])` 唤醒逻辑中，切回会话恢复连接时：若当前会话未处于运行中（`!active(run.value)`），`reconnectStream().catch(...)` 吞没断连错误，仅重置 `eventsParked` 标记，不调用 `fail(cause)`。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **预期结果：** 切换会话切回已完成会话时，状态栏保持“最后活跃于...”或“就绪”，不再弹出红色“✕ 执行出错: Event stream closed.”和橙色“恢复连接”横条。
- **验证项：** `useChatSession.spec.ts` 模拟切换并唤醒空闲会话，断言 `error.value` 为空。
- **状态：** `[ ]` 待开始

## Phase 4: 全面工程验证

### Task 4.1: 全量测试与类型构建检查
- **改动内容：** 运行前端单元测试、vue-tsc 类型检查与 Vite 生产构建。
- **预期结果：** Vitest 测试全绿，TypeScript 0 错误，生产构建成功打包。
- **验证项：** `pnpm test:run`、`pnpm typecheck`、`pnpm build`。
- **状态：** `[ ]` 待开始
