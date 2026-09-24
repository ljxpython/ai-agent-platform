# 03 前端记忆治理重构、分享隐私提示与孤儿代码清理

## 改动时间
2026-09-24

## 相关任务
- F01: 错误工具与无线程 Memory Service
- F02: 无线程页面上下文、状态矩阵、防竞态与静默轮询
- F03: 事实表单、本地时区日期与 409 CAS 冲突保留草稿
- F04: 候选卡片原文溯源、会话跳转与替换已有事实
- F05: 便携 JSON 导出与文件/文本双模追加导入预览
- F06: 标准确认弹窗与共享会话隐私提示
- F07: 前端验证门禁与全套回归

## 改动文件
- `apps/platform-web/src/utils/http-error.ts`
- `apps/platform-web/src/services/dear-agent/memory.service.ts`
- `apps/platform-web/src/services/dear-agent/memory.service.spec.ts`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentMemoryPage.spec.ts`
- `apps/platform-web/src/modules/chat/components/ThreadAccessControl.vue`
- `apps/platform-web/src/modules/chat/components/ThreadAccessControl.spec.ts`
- `apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.ts`（删除孤儿代码）
- `apps/platform-web/src/modules/dear-agent/composables/useDearGovernanceContext.spec.ts`（删除孤儿测试）

## 具体改动

### 1. 统一嵌套错误提取与无线程 Memory Service (`F01`)
**位置：** `src/utils/http-error.ts`, `src/services/dear-agent/memory.service.ts`
- 在 `http-error.ts` 中扩展 `extractEnvelopeFields` 支持提取 `error.details`，新增并导出同步辅助函数 `extractPlatformHttpError`，并在 `extractErrorStatus` 中兼容普通响应对象的 `response.status`。
- 重写 `memory.service.ts`：彻底移除 `threadId` 参数，统一通过 `GET / POST /api/langgraph/dear/memory`（携带 `x-project-id` header）交互，完整定义 `MemoryView`、`MemoryDocument`、`MemoryFact`、`ExtractionStatus`、`MemoryMutation` 及带 `replace_fact_id` 的 `MemoryCommandPayload`。

### 2. 无线程页面上下文、状态矩阵与静默轮询 (`F02`)
**位置：** `src/modules/dear-agent/pages/DearAgentMemoryPage.vue`
- 移除 `useDearGovernanceContext` 依赖与旧“关联会话选择器”，改用 `useWorkspaceProjectContext()` 获取当前项目，并删除孤儿文件 `useDearGovernanceContext.ts` 及 `.spec.ts`。
- 实现 `status === "disabled"` 独立说明面板、`ready` 只读横幅（修正权限提示为 `project.runtime.execute`）、`extraction` 状态指示栏及 `pause_reason` 维护提示。
- 引入 `scopeGeneration` 与 `AbortController` 防跨项目反序响应污染；当 `extraction.status === "running"` 时启动每 3 秒一次（上限 210 秒）的 `silentFetchMemory()`，确保后台同步不置主 `loading = true`、不冲掉打开的弹窗草稿与未解除的 409 冲突提示，并在 `onDeactivated` / `onScopeDispose` / 切项目时立即销毁定时器。

### 3. 事实表单、本地时区转换与 409 冲突保留草稿 (`F03`)
**位置：** `src/modules/dear-agent/pages/DearAgentMemoryPage.vue`
- 使用 `Array.from(formText.value.trim()).length` 计算 Unicode 码点长度。
- 新增 `toLocalDateInputString` 与 `localDateToEndOfDayIso`：编辑时将 ISO 时间回显为浏览器本地时区 `YYYY-MM-DD`；若用户未修改日期则原样保留原 `expires_at` ISO 字符串，修改或新增时转为本地时区当日 `23:59:59.999` 的 ISO 字符串，杜绝 UTC 零点导致的 `400 invalid_memory_fact`。
- 遇到 `409 memory_revision_conflict` 时保留当前弹窗草稿，自动调用 `fetchMemory({ preserveConflict: true })` 拉取最新 `revision` 并持久显示冲突横幅。

### 4. 候选溯源、会话跳转与替换已有事实 (`F04`)
**位置：** `src/modules/dear-agent/pages/DearAgentMemoryPage.vue`
- 候选卡片完整渲染 `quote`（缺失时显示“历史记录缺少原文”）、`category`、`source_kind`、`expires_at` 及跳转 `workspace-dear-agent` 的“查看来源会话”按钮。
- 提供「直接采纳」、「替换已有事实…」（选择现有 `fact` 后传入 `replace_fact_id`）和「拒绝丢弃」三项操作。

### 5. Fresh GET 导出与双模追加导入预览 (`F05`)
**位置：** `src/modules/dear-agent/pages/DearAgentMemoryPage.vue`
- 导出：调用 `readMemory` 获取最新全量有效 `facts`，投影为 `[{ text, category, expires_at }]` 下载为 `dear-memory-YYYYMMDD.json` 并调用 `URL.revokeObjectURL`。
- 导入：支持选择 `.json` 文件或粘贴 JSON 数组，前端严格校验体积、字符串类型、合法分类（拒绝未知分类如 `"knowledge"`）、有效时区时间及容量上限，实时预览有效/重复/错误条目，提交后按 `mutation.added / skipped` 展示服务端真实计数。

### 6. 标准确认弹窗与共享会话隐私提示 (`F06`)
**位置：** `src/modules/dear-agent/pages/DearAgentMemoryPage.vue`, `src/modules/chat/components/ThreadAccessControl.vue`
- 使用 `BaseDialog` 和 `ConfirmDialog` 替换全部手搓弹窗与原生 `window.confirm`。
- 在 `ThreadAccessControl.vue` 的 `mode === 'share'` 安全说明中补齐：“共享会话将自动停用个人记忆；但分享包含历史回答，回答中已经出现的个人信息也会被分享，不会自动移除历史个人信息。”

## 验证
- [x] 单元测试通过（3 套测试文件共 16 条用例全绿）
- [x] 类型检查通过（`pnpm --dir apps/platform-web typecheck` 零报错）
- [x] Lint 通过（`eslint` 0 errors, 0 warnings）
