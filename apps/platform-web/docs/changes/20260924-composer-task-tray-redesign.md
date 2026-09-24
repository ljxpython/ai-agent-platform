# 聊天待办任务进度重构为底部输入框悬浮托盘（Composer Top Tray）

## 背景与痛点
原 `ChatStickyTaskPill.vue` 直接挂载在聊天滚动流 `.pw-chat-stream-content` 内部并使用 `sticky top-0`：
1. 页面滚动经过深色代码块或表格时，浅色进度横幅/胶囊会直接覆盖在代码块中部，造成严重的图文穿模与视觉割裂；
2. 全部任务完成（`100%`）时底部横跨全宽的高饱和度翠绿进度条过于喧宾夺主；
3. 右侧同时堆叠计数徽标、`查看待办看板 →`、`▾` 内联展开与 `✕` 收起恢复胶囊四个交互项，视觉噪点高。

## 改动内容
1. **空间解耦（下沉至 Composer 顶沿托盘）**：
   - 在 `ChatComposer.vue` 的 `.pw-chat-composer-wrap` 内部、`.pw-chat-composer` 主框体正上方新增 `#top-tray` 插槽，自动继承居中最大宽度并左右内缩 `12px`（`px-3`），形成阶梯式帽檐托盘结构。
   - 在 `ChatSession.vue` 中将 `ChatStickyTaskPill` 从 `.pw-chat-stream-content` 移出，挂入 `<ChatComposer>` 的 `#top-tray` 插槽，彻底消除滚动时对正文与代码块的遮挡。
2. **三态视觉升级与降噪（`ChatStickyTaskPill.vue`）**：
   - 移除底部全宽进度条与冗余的 `✕` 二级胶囊切换；
   - **执行态**：采用 `16×16` 动态 SVG 环形进度圈（Progress Ring）展示完成比例，配合当前执行步骤文案；
   - **完成态**：自动降噪为翠绿小圆勾 SVG 图标 + 温和灰字 `已完成全部 N 项待办任务`；
   - **向上展开态**：整条托盘可点击向上丝滑展开任务执行清单，清单右上角保留安静的 `待办看板 ↗` 入口用于唤起右侧上下文抽屉。

## 涉及文件
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatStickyTaskPill.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/components/ChatStickyTaskPill.spec.ts`
