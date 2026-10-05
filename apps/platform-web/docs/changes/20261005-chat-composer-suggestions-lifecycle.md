# Chat 灵感胶囊栏生命周期与单次会话收起优化

- **日期**：2026-10-05
- **服务**：platform-web
- **背景**：对话框上方的灵感建议胶囊栏（小惊喜、深度写作、敏捷调研、数据洞察、交互单页）原先仅判断输入框是否为空及是否处于生成中。导致即使会话已经进行了多轮对话，只要输入框被清空，胶囊栏就会反复在输入框上方弹出，遮挡和打扰已有上下文输入体验。
- **改动**：
  1. `ChatSession.vue`：引入 `hasUsedSuggestion` 状态与 `shouldShowComposerSuggestions` 计算属性。定义会话级隐藏规则：胶囊栏仅在空白新会话且尚未产生任何消息、未点击过建议时展示；
  2. 一旦用户在当前会话中点击了灵感胶囊（使用完成），或用户发送了消息、产生了对话（对话开始/完成），该胶囊栏在当前会话后续生命周期中彻底收起隐藏，不再反复弹出；
  3. 当切换/新建空白会话时，自动重置展示状态，依然可作为初始灵感引导；
  4. `ChatComposer.vue`：向组件传递 `:show-suggestions="shouldShowComposerSuggestions"` 与 `@select-suggestion="handleSelectSuggestion"`；
  5. `ChatComposer.spec.ts`：补充单元测试，验证当 `showSuggestions` 为 `false` 时胶囊栏容器正确隐藏。
- **涉及文件**：
  - `apps/platform-web/src/modules/chat/components/ChatSession.vue`
  - `apps/platform-web/src/modules/chat/components/ChatComposer.spec.ts`
