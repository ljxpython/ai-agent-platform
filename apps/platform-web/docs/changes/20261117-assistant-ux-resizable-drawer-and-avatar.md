# 平台助手体验升级：可拖拽拉伸抽屉、一键宽屏模式与个性化头像联动

## 背景

用户反馈平台助手默认抽屉宽度过窄，在展示多列结构化数据（如诊断动作对比表、长调用栈）时内容受挤压截断；同时输入框在聚焦和 hover 态存在原生深黑色边框回退与双层硬框问题，且系统缺少个性化用户头像配置。

## 改动内容

1. **抽屉自由拉伸（Resizable）与宽屏展开**：
   - `BaseDrawer.vue`：增加 `resizable` 属性与左边缘无级拖拽手柄（`ew-resize`），支持在 420px 至屏幕最大宽度之间任意拉伸，并提供 `customWidth` 响应式双向绑定。
   - `PlatformAssistantDrawer.vue`：增加宽度本地持久化（`localStorage` 键 `pw_assistant_drawer_width`，默认 580px），并在顶栏右上角增加【宽屏】/【标准】一键切换按钮（580px ⇄ 960px）。
2. **输入框（Composer）深色边框根治与呼吸微光聚焦**：
   - `AssistantComposer.vue`：彻底清除 Tailwind v4 残留的无效 `focus:outline-hidden`，使用 `border-none outline-none ring-0 focus:outline-none focus:ring-0` 彻底拔除浏览器 user-agent 黑色直角外框；外层容器重塑为现代平滑过渡微蓝高亮 `focus-within:border-sky-500 focus-within:ring-2 focus-within:ring-sky-500/15`。
3. **用户个性化头像与全局联动**：
   - `authStore`：增加 `customAvatar` 响应式与 localStorage 持久化支持；
   - `ProfilePage.vue`：提供高颜值预设头像库（极客少年、码农萌妹、平台小精灵）与本地图片上传能力，卡片尺寸规范为 `w-14 h-14 shrink-0`；
   - `AssistantChatView.vue` 与 `UserMenu.vue`：联动展示用户自定义头像。
4. **悬浮入口优化**：
   - `WorkspaceLayout.vue`：右下角悬浮按钮去除外层白色胶囊框与冗余介绍文本，保留纯透明底小人吉祥物看板娘动图与在线微弱呼吸绿点。

## 涉及文件

- `apps/platform-web/src/components/base/BaseDrawer.vue`
- `apps/platform-web/src/modules/platform-assistant/components/PlatformAssistantDrawer.vue`
- `apps/platform-web/src/modules/platform-assistant/components/AssistantComposer.vue`
- `apps/platform-web/src/modules/platform-assistant/components/AssistantChatView.vue`
- `apps/platform-web/src/modules/account/pages/ProfilePage.vue`
- `apps/platform-web/src/components/layout/UserMenu.vue`
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- `apps/platform-web/src/stores/auth.ts`
