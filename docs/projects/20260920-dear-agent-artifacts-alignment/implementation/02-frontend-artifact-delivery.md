# 02 前端成果页全链路重构与交付记录

## 改动时间
2026-09-21

## 相关任务
- Task F01: 修复项目参数注入与响应式 service 工厂装配
- Task F02: 废除历史扫描逻辑，全面对接 `getArtifacts` 并支持非首屏深链置顶
- Task F03: 实现独立 `useArtifacts` composable（分页、去重、代际控制、阻断 download 类型的 preview 请求）
- Task F04: 实现右侧滑出抽屉（Drawer / Slide-over）与 `WorkspacePreview` 内嵌渲染；补充 Markdown 内部图片并发与代际保护
- Task F05: `workspace.service` 补充 Axios Blob 错误解码函数 `unwrapWorkspaceError`
- Task F06: `useThreadWorkspace` 补充 download 拦截；保持终态刷新契约
- Task F07: 彻底重写单元测试，移除旧 W3 history mock 毒瘤，补充 `useArtifacts.spec.ts` 与 `WorkspacePreview.spec.ts`

## 改动文件
- `apps/platform-web/src/services/threads/workspace.service.ts`
- `apps/platform-web/src/services/threads/workspace.service.spec.ts`
- `apps/platform-web/src/composables/useArtifacts.ts` [NEW]
- `apps/platform-web/src/composables/useArtifacts.spec.ts` [NEW]
- `apps/platform-web/src/composables/useThreadWorkspace.ts`
- `apps/platform-web/src/components/workspace/WorkspacePreview.vue`
- `apps/platform-web/src/components/workspace/WorkspacePreview.spec.ts` [NEW]
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentArtifactsPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentArtifactsPage.spec.ts`
- `docs/projects/20260920-dear-agent-artifacts-alignment/04-frontend-handoff.md`

## 具体改动与技术决策

### 1. 架构解耦：抽出纯粹的 `useArtifacts` Composable
- **位置：** `apps/platform-web/src/composables/useArtifacts.ts`
- **设计决策：** 拒绝在承担目录树、文件下载与终端功能的 `useThreadWorkspace` 中硬塞 `includeTree` 开关。抽取单一职责的 `useArtifacts`，集中管理成果列表、游标分页（cursor）、代际取消（generation）、选中项和预览状态。
- **阻断 download 请求：** 当 `item.preview_kind === 'download'` 时，客户端直接设置 `{ kind: 'download', downloadOnly: true }`，**绝不向服务端发 `getWorkspacePreview` 请求**，彻底避免预期内 415 报错。

### 2. 交互重构：右侧滑出抽屉（Drawer / Slide-over）
- **位置：** `apps/platform-web/src/modules/dear-agent/pages/DearAgentArtifactsPage.vue`
- **设计决策：** 点击成果卡片或“在线预览”时，从屏幕右侧平滑滑出预览抽屉（内置 `WorkspacePreview.vue`），支持遮罩点击与键盘 `Esc` 键快捷退出，关闭时保留左侧会话与成果列表的滚动与筛选状态。
- **深链增强：** 针对路由 `?threadId=`，如果不在首屏 20 条会话中，独立调用 `service.get(threadId)` 校验项目归属并置顶插入列表；若无权访问或不存在，展示明确错误态，杜绝静默 fallback 到第一条会话。

### 3. Axios Blob 错误解包机制
- **位置：** `apps/platform-web/src/services/threads/workspace.service.ts`
- **设计决策：** 新增 `unwrapWorkspaceError`。当 Axios 针对非 2xx 响应抛出 AxiosError 时，异步读取 `error.response.data` (Blob) 内容并反序列化，提取后端原始的 `error.code`、`error.message` 与 `request_id`，杜绝只显示无意义的 "Request failed with status code 400"。

### 4. Markdown 内部图片并发与代际保护
- **位置：** `apps/platform-web/src/components/workspace/WorkspacePreview.vue`
- **设计决策：** 使用 `Promise.allSettled` 并发加载 Markdown 引用的 `/workspace/` 图片；绑定 `markdownTaskSeq` 代际编号，当文件切换或组件卸载时，立即销毁所有生成的临时 Object URL（`URL.revokeObjectURL`），杜绝内存泄漏和内容串台。

## 验证结论
- [x] **单元测试全量通过**：6 个测试套件，27 个测试用例全部绿灯通过（耗时 4.89s）
  - `DearAgentArtifactsPage.spec.ts` (3/3)
  - `useArtifacts.spec.ts` (6/6)
  - `WorkspacePreview.spec.ts` (3/3)
  - `workspace.service.spec.ts` (7/7)
  - `useThreadWorkspace.spec.ts` (3/3)
  - `session.service.spec.ts` (5/5)
- [x] **TypeScript 类型检查通过**：`pnpm typecheck` 0 errors
- [x] **代码质量检查通过**：`pnpm lint` 0 errors
- [x] **生产打包构建通过**：`vue-tsc --noEmit && vite build` 成功输出 dist
