# 前端撒花与灵感胶囊实现细节

## 改动时间
2026-10-02

## 相关任务
- Task 1.1: 封装 ConfettiButton.vue 撒花微交互组件
- Task 1.2: 实现 ComposerSuggestions.vue 灵感胶囊栏
- Task 1.3: ChatComposer.vue 与 ChatSession.vue 集成对齐

## 改动文件
- `apps/platform-web/src/components/base/ConfettiButton.vue` (新增)
- `apps/platform-web/src/components/base/ConfettiButton.spec.ts` (新增)
- `apps/platform-web/src/modules/chat/components/ComposerSuggestions.vue` (新增)
- `apps/platform-web/src/modules/chat/components/ComposerSuggestions.spec.ts` (新增)
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue` (修改)
- `apps/platform-web/src/modules/chat/components/ChatComposer.spec.ts` (修改)

## 具体改动

### 1. ConfettiButton.vue
**位置：** `apps/platform-web/src/components/base/ConfettiButton.vue`
**改动内容：**
- 引入轻量级 `canvas-confetti` 库；
- 点击时根据 `event.currentTarget.getBoundingClientRect()` 精准计算相对于屏幕视口的百分比发射坐标；
- 设置 `colors: ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]` 与 `disableForReducedMotion: true` 保证无障碍体验；
- 点击时同步触发 `emit("click", event)`。

### 2. ComposerSuggestions.vue
**位置：** `apps/platform-web/src/modules/chat/components/ComposerSuggestions.vue`
**改动内容：**
- 构造水平自适应滚动胶囊栏：
  - `🎉 小惊喜`：采用 `ConfettiButton` 包装，带有暖色呼吸微光动效，点击喷洒五彩纸屑并触发 Prompt：`给我一个小惊喜吧`；
  - `📝 深度写作`：`撰写一篇关于[主题]的深度技术博客，包含架构设计与实操建议`；
  - `🔬 敏捷调研`：`深入调研一下[主题]，总结核心技术方案、优劣势对比与关键结论`；
  - `📊 数据洞察`：`分析以下数据并绘制直观图表：`；
  - `💻 交互单页`：`设计并生成一个零依赖单文件的高保真现代交互网页：`。

### 3. ChatComposer.vue 集成
**位置：** `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
**改动内容：**
- 增加 `showSuggestions` prop（通过 `withDefaults` 显式设置默认值为 `true`，防御 Vue 3 对未传 boolean prop 默认赋值 `false` 的陷阱）；
- 引入计算属性 `shouldShowSuggestions = computed(() => (props.showSuggestions ?? true) && !props.isRunning && !props.hasBlockingInterrupt && !composerModel.value.trim())`；
- 建议栏位于主输入框外层上方，输入框无内容时呈现，用户输入后优雅隐藏；
- 点击任意胶囊自动更新 `composerModel`，并在 `nextTick` 中自动聚焦光标到文本框。

## 验证
- [x] `pnpm test:run src/components/base/ConfettiButton.spec.ts` (3/3 通过)
- [x] `pnpm test:run src/modules/chat/components/ComposerSuggestions.spec.ts` (3/3 通过)
- [x] `pnpm test:run src/modules/chat/components/ChatComposer.spec.ts` (8/8 通过)
- [x] 全量聊天组件单测矩阵 (19/19 文件, 67/67 用例通过)
- [x] `pnpm build` (vue-tsc 类型检查与 vite 打包全部通过)
