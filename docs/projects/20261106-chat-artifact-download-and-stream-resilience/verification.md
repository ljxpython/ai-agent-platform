# 前端 Markdown 产物链接拦截下载与空闲会话长连接断开误报治理 - 验证计划

## 验证策略概述
本项目的核心验证目标：
1. **Markdown 产物协议放行与下载拦截**：确保 `artifact://` 协议安全合法，点击时被精确捕获并不再外跳空白页面，直接调起原生文件下载。
2. **空闲流断开防误报**：确保用户在多会话间反复切换时，已完成的会话不会因为空闲 SSE 连接挂起恢复而误弹红条。
3. **零回归与构建健康**：保证全量单测通过、TypeScript 类型校验通过、生产编译构建无警告。

## Phase 验证项

### Phase 1: 仓库基线同步验证
- [ ] 提交信息规范清晰，包含详细说明。
- [ ] 远端 GitHub 仓库成功接收推送，主干基线保持整洁。

### Phase 2: Markdown 产物链接验证
- [ ] `markdown.ts` 单测覆盖 `artifact://` 协议，验证不会被降级为 `#`。
- [ ] 验证 `link_open` 没有对 `artifact://` 链接强制设置 `target="_blank"`。
- [ ] 验证点击 `artifact://` 链接时 `preventDefault()` 阻断跳转，并正确调用文件下载函数。

### Phase 3: 会话重连断流异常收敛验证
- [ ] `useChatSession.spec.ts` 验证 `isNonFatalStreamError("Event stream closed.")` 返回 `true`。
- [ ] 验证空闲会话切回唤醒时，若 `reconnectStream()` 被 reject，`error.value` 不受污染，页面不显示橙色与红色错误横幅。

### Phase 4: 全量工程门禁
- [ ] `pnpm test:run` 单测全部通过。
- [ ] `pnpm typecheck` 0 错误。
- [ ] `pnpm build` 生产构建成功。

## Final 验证要求
1. **真实浏览器交互验证**：
   - 在会话 `cb4f8571-83ca-442e-aed8-d3d3d26d9e30` 中，点击正文的 `[下载 PPTX]`，浏览器应立即弹出或开始下载 `.pptx` 文件，当前页面不发生跳转，不新开空白标签页。
   - 在左侧侧边栏中连续在多个已完成的会话（包括 `ccefa211` 和 `cb4f8571`）之间反复点击切换，页面顶端不再出现橙色条 `Event stream closed.`，底部状态栏不再出现红色框 `✕ 执行出错: Event stream closed.`。
2. **四态判定记录**：
   - 最终验证完成后记录完成度四态（`done` / `partial` / `blocked` / `deferred`）。
