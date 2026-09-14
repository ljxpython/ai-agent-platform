# 20260914 - 对话工作台通透无界大视野与布局重构

## 背景
用户指出当前对话工作台存在多处臃肿的冗余结构与死留白：
1. 顶部全局 Header 与 Chat 内部 Header 双层重叠，垂直空间被严重吃掉 56px；
2. 底部输入框下方存在死板的固定 padding（外层 24px + 输入框 20px），产生巨大空白缝隙；
3. 左侧会话侧栏采用老旧的上一页/下一页分页器，且缺少一键灵活收起的常驻开关，横向挤占主聊天区；
4. 侧栏与主对话区之间存在 16px 缝隙，缺乏现代 IDE / DeepSeek 风格的无缝体验。

## 改动内容
1. **沉浸式单层 Header 融合**：
   - 在 `routes.ts` 为 `workspace-chat` 路由注入 `meta.immersive = true`；
   - 在 `WorkspaceLayout.vue` 识别沉浸模式，隐藏全局 `TopContextBar`，释放 56px 垂直高度；
   - 将原全局顶栏核心能力（`WorkspaceProjectSwitcher` 项目切换、`UserMenu` 个人菜单）无缝下沉整合至 Chat 顶栏右侧单行中，功能零丢失且 Header 仅占单层。
2. **消灭底部与四周死留白**：
   - 沉浸模式下移除外层 `.pw-workspace-main` 的固定四周内边距，移除外层容器的多余 `overflow-y-auto`；
   - 在 `index.css` 与 `ChatComposer.vue` 中优化 `.pw-chat-composer-wrap` 贴底间距（从 `pb-5` 紧凑为 `pb-2.5`），底边仅留 8~10px 精致呼吸感。
3. **会话列表自适应平滑滚动与侧栏一键收折**：
   - 彻底干掉 `ChatThreadSidebar.vue` 中的老式 `Pagination Footer` 及 10 条分页切片逻辑，改为直观、现代的自适应连续平滑垂直滚动列表；
   - 在 `ChatPage.vue` 顶栏左上角常驻会话抽屉切换按钮（`columns`），支持一键丝滑折叠与展开会话列表。折叠后主聊天区弹性伸展至 100% 满屏视野；
   - 优化移动端/平板端自适应：侧栏在移动端自动作为抽屉浮层（带遮罩蒙层）弹出，选定会话后自动收起，移除原本页面顶部冗余的移动端下拉与输入框。
4. **无缝边框对齐**：
   - 移除侧栏与主区之间的 `gap-4`，以 1px 现代细分割线贴合展示。

## 涉及文件
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- `apps/platform-web/src/router/routes.ts`
- `apps/platform-web/src/styles/index.css`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatThreadSidebar.vue`

## 验证结果
- `pnpm --filter platform-web run typecheck`: 0 error
- `pnpm --filter platform-web run lint`: 0 error, 0 warning
- `pnpm --filter platform-web test:run`: 47 passed, 143 passed, 100% 绿灯
- `pnpm --filter platform-web build`: 打包成功通过
