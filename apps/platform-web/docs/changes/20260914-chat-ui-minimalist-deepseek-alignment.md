# 前端主对话流与顶栏极简化设计（对齐 DeepSeek Harness）

## 背景与诉求
对比 `deepseek-harness` 原版主对话流，现有聊天页面存在严重的“套娃卡片病”与视觉冗余：
1. 主视窗被深色/渐变外框包裹，外层又嵌套大圆角白卡片，空间压抑；
2. 思考过程（Think）呈现为黄色警告卡片，视觉侵略性过强；
3. 用户消息带有多余的圆形“你”字头像；
4. 顶栏操作堆叠了实心绿色大按钮，视图切换器为厚重的大胶囊套壳；
5. 底部输入框缺乏工业级性能小字（Metrics Strip）。

## 变更内容
1. **无界通透主视窗 (`index.css` & `.pw-chat-workspace`)**：
   - 移除聊天主视窗外层的大圆角、边框与阴影，背景改为纯净底色（`bg-white dark:bg-dark-950`），通透铺开，呼吸感拉满。
   - 顶栏改为纯平底边分割线（`border-b border-gray-100`）。
2. **极简灰色原子思考条 (`MessageContent.vue`)**：
   - 彻底干掉土黄色大框框，采用原版极简灰色单行 Think 条：`⚛ Think · 思考摘要...`。
   - 点击可平滑展开完整思考内容，展开区采用低饱和淡灰底色（`bg-gray-50/50`），绝不喧宾夺主。
3. **用户气泡无头像化与 AI 去卡片自然排版 (`ChatMessageList.vue`)**：
   - 移除用户消息顶部的“你”头像，改为右浮动的轻蓝微底色大圆角气泡（`rounded-2xl rounded-tr-xs bg-blue-50/85`）。
   - AI 回复彻底移除外层大白卡片，自然流淌在纯净背景上；底部悬浮操作按钮极简化。
4. **顶栏 Header 极简化与下划线 Tab (`ChatSession.vue` & `ChatPage.vue`)**：
   - 将 `[ 对话 | 轨迹 ]` 视图切换重构为原版的极简下划线文本 Tab（激活项带 2px 蓝下划线）。
   - 移除顶栏扎眼的实心绿色新对话按钮，统一收敛为精致浅色线框按钮。
5. **底部工业级指标条 (`ChatSession.vue`)**：
   - 在输入框正下方新增紧凑性能指标小字：`X 轮 · X 步 | LLM 就绪 | 输入 X tok · 输出 Y tok`。
6. **质量与测试保障**：
   - `vue-tsc` 0 类型报错。
   - `eslint` 0 error 0 warning。
   - 全量 47 个测试套件（143 项单元测试）100% 跑绿。
   - 生产打包 `vite build` 12.55s 成功通过。

## 涉及文件
- [MODIFY] `apps/platform-web/src/styles/index.css`
- [MODIFY] `apps/platform-web/src/modules/chat/components/MessageContent.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- [MODIFY] `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
