# 前端沙箱工作区与产物展示实现

## 改动时间
2026-09-17

## 相关任务
- 前端工作区面板（Files/Artifacts/Terminal 三合一）开发
- 参考借鉴 open-swe 优秀实践（弹性拖拽容器、全屏切换、xterm 多终端保活、Add to Chat 联动）
- 全链路打通（Agent 运行时与工作区状态联动、静默刷新、未读徽标）

## 改动文件
- `apps/platform-web/package.json`（新增 `@xterm/xterm`, `@xterm/addon-fit`）
- `apps/platform-web/src/types/workspace.ts`（新建）
- `apps/platform-web/src/services/threads/workspace.service.ts`（新建）
- `apps/platform-web/src/services/threads/terminal.service.ts`（新建）
- `apps/platform-web/src/composables/useThreadWorkspace.ts`（新建）
- `apps/platform-web/src/composables/useThreadTerminal.ts`（新建）
- `apps/platform-web/src/components/workspace/SandboxedHtmlFrame.vue`（新建）
- `apps/platform-web/src/components/workspace/WorkspaceTree.vue`（新建）
- `apps/platform-web/src/components/workspace/WorkspacePreview.vue`（新建）
- `apps/platform-web/src/components/workspace/TerminalPanel.vue`（新建）
- `apps/platform-web/src/components/workspace/WorkspacePanel.vue`（新建）
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`（升级替换固定 320px 网格）
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`（同步升级接入）
- `apps/platform-web/src/services/threads/workspace.service.spec.ts`（新建单测）
- `apps/platform-web/src/composables/useThreadWorkspace.spec.ts`（新建单测）

## 具体改动

### 1. 弹性面板与交互体系升级
- 摒弃了原本写死 `lg:grid-cols-[minmax(0,1fr)_320px]` 且仅在 `hasArtifacts` 时显示的僵化设计；
- 升级为左侧带拖拽手柄（`360px ~ 960px` 可调、双击重置为 `480px`、持久化至 localStorage）、全屏最大化/还原切换的弹性侧边抽屉容器 `WorkspacePanel.vue`；
- 在 `ChatSession.vue` 与 `DearAgentSession.vue` 顶部 Header 新增常驻工作区入口按钮。

### 2. 多终端交互与保活挂载（借鉴 open-swe）
- 引入工业级 `@xterm/xterm` 与 `@xterm/addon-fit`；
- 支持多会话二级 Tab 栏（`[终端 1] [终端 2] [+]`），支持清屏、关闭会话与尺寸去抖；
- 采用 `v-show` 保持终端 DOM 挂载，切换工作区 Tab（如切到 Files 查代码）绝不销毁实例；切后台自动降频轮询至 2500ms，切回前台立即 `fit()` 还原尺寸；
- 深度 Chat 联动：支持终端划词文本一键“引用到提问框”，支持终端输出路径点击直达 Files 预览。

### 3. 代码、Markdown、HTML 安全沙箱与图片预览
- 纯净安全的 `SandboxedHtmlFrame.vue`：`iframe` 严格配置 `sandbox=""` 与 `referrerpolicy="no-referrer"`；
- 文本/代码支持行号、语法容器、一键复制代码；
- Markdown 支持平滑切换“渲染视图”与“源码视图”；
- 未知二进制文件自动呈现下载卡片。

### 4. 跨组件状态与全链路打通
- `ChatSession.vue` 监听 Agent 运行终态（`busy` 从 true 变 false）与 `present_artifacts` 事件，自动触发工作区静默刷新（Invalidate & Refetch）；
- 切换 `threadId` 时 AbortController 立即取消在途网络请求，彻底杜绝切线程数据串台。

## 验证
- [x] 单元测试通过（全量 64 个测试套件，208 个测试用例全部通过）
- [x] `vue-tsc --noEmit` 静态类型检查 0 错误通过
- [x] `pnpm lint` 检查 0 错误通过
- [x] `pnpm build` 全量生产打包顺利完成
