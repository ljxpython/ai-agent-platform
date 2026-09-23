# 2026-09-22 会话顶栏人机工程排布优化与专注模式沉浸感美化

## 背景
用户反馈：
1. 专注模式界面粗陋单薄，缺乏沉浸感与快捷退出体验。
2. 普通对话顶栏存在平铺“详情”与下拉菜单“会话详情与上下文”重复问题。
3. 顶栏右侧控件排布混乱，账号信息未置于最右侧，项目切换器与会话级工具界限不清晰。

## 改动内容
1. **专注模式（Focus Mode）极致利用率与右上角悬浮还原**：
   - 彻底移除横跨顶部的长条 Banner，并将外层容器设为 `p-0`，使聊天对话与输入区 100% 吃满全屏；
   - 在右上角放置极简毛玻璃悬浮还原按钮（`minimize` 图标），完全不占据垂直流高度；
   - 鼠标悬停时微展开“还原 ESC”按键提示，支持一键点击还原与全局键盘 `Escape` 随时退出还原。
2. **消灭重复按钮与二级操作收敛**：
   - 新建 `ThreadActionsMenu.vue`，集中收敛“会话详情与上下文”、“运行参数配置”、“专注模式”、“管理员临时接管”以及“删除会话”；
   - 移除 `ChatSession.vue` 中平铺的多余“详情”按钮，避免心智重复。
3. **顶栏信息架构调整（账号居最右，项目紧靠其左）**：
   - 将 `ChatSession.vue` 与 `DearAgentSession.vue` 中的工作区按钮及 Dear Agent 执行模式指示胶囊调整至 `#actions` 插槽之前；
   - 形成清晰的自左至右视觉动线：
     `[会话内部标识]` → `[对话/轨迹视图切换]` → `[执行模式胶囊]` → `[工作区]` → `[新对话]` → `[协作共享]` → `[··· 更多操作]` → `[竖向隔离线]` → `[项目切换器]` → `[用户账号 (最右侧)]`。

## 涉及文件
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- `apps/platform-web/src/modules/chat/components/ThreadAccessControl.vue`
- `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.vue`
- `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.spec.ts`
