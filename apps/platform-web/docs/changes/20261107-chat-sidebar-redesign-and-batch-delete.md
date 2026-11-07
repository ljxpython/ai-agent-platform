# 历史会话侧边栏工业级重构与批量删除、顶栏 Tooltip 优化

## 背景

用户在实际体验平台聊天界面时提出若干痛点与视觉缺陷：

1. **顶栏小图标缺乏标题提示**：工作区、新对话、分享、更多操作、执行模式等纯图标按钮无悬停解释，用户无法直观理解功能；
2. **顶栏元素撞车重叠**：左侧容器采用 `min-w-0 shrink` 弹性压缩策略，在侧边栏展开导致主内容区变窄时，内部不换行子元素向右溢出，与右侧容器的“对话”按钮发生严重视觉重叠；
3. **历史会话侧边栏排版拥挤凌乱**：原搜索框被两侧方块挤压变形，下方 5 个状态过滤胶囊在侧边栏常规宽度下强制折行（“异常”掉到第二行，右侧“批量”按钮悬空），严重破坏视觉秩序；
4. **缺少会话批量删除能力**：历史会话增多时用户只能逐个卡片悬浮、点击删除并确认，操作繁琐低效。

## 改动内容

1. **顶栏高质感 Tooltip 交互接入与物理防重叠治理**：
   - 提取全局复用 `.pw-tooltip-top` 毛玻璃暗色悬浮气泡，接入 `ChatSession.vue`（新对话、工作区、执行模式）、`ThreadAccessControl.vue`（分享权限）、`ThreadActionsMenu.vue`（更多操作）及左侧主导航栏图标；
   - 彻底修复 `ChatSession.vue` 顶栏左侧容器压缩后子元素向右溢出与右侧“对话”按钮撞车的缺陷，将左侧容器调整为 `shrink-0`，外层通过平滑横向滚动容器自适应，根除任何物理重叠。
2. **侧边栏“方案 A：三段式纯净排版”重构**（`DearAgentThreadSidebar.vue` & `ChatThreadSidebar.vue`）：
   - **第一行（标头）**：紧凑展示 `历史会话 (18)` 标题徽章，右侧聚合三联操作组（`[📁 批量]`、`[💬 新建]`、`[‹ 收起]`）；
   - **第二行（全宽搜索）**：32px 沉浸式 `w-full` 搜索栏，内嵌放大镜与即时清空按钮（快捷 ESC 或一键清空）；
   - **第三行（单行过滤胶囊）**：`全部 / 待处理 / 运行中 / 空闲 / 异常` 5 个轻量药丸选择器，主色微高亮，`overflow-x-auto no-scrollbar` 永不断行，彻底终结折行掉队乱象。
3. **会话批量删除前端并发 Worker 队列**（`ChatPage.vue` & `DearAgentPage.vue`）：
   - 支持多选模式切换，整卡点击勾选与一键全选（智能过滤只读/受限项）；
   - 底部滑入悬浮操作条，展示已选计数、实时删除进度 `(done/total)` 与二次确认安全防护；
   - 纯前端实现并发队列（并发度 3）批量安全调用底层 `DELETE /threads/{id}` 接口，无需破坏后端现役契约。
4. **单测套件扩充与回归**：
   - 为 `DearAgentThreadSidebar.spec.ts` 与 `ChatThreadSidebar.spec.ts` 补齐紧凑搜索一键清空与批量管理模式响应单测，全量单测保持 100% 跑绿。

## 涉及文件

- `apps/platform-web/src/components/layout/AppSidebar.vue`
- `apps/platform-web/src/styles/index.css`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/ThreadAccessControl.vue`
- `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.vue`
- `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentThreadSidebar.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.spec.ts`

## 验证

- 单元测试：`pnpm vitest run` 159 个测试套件，945 项测试全绿。
- 类型检查：`vue-tsc --noEmit` 0 错误。
- 生产构建：`pnpm build` 构建成功。
- 线上部署与真实探针验收：已发布至生产环境并通过真实大模型端到端与无头浏览器三视口截屏验证。
