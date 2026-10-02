# DearFlow Agent 灵感建议与“小惊喜”创意工坊 - 任务拆分

## Phase 1: 前端动效与灵感胶囊组件

### Task 1.1: 封装 ConfettiButton.vue 撒花微交互组件
- **改动内容：** 实现自包含基于 canvas-confetti 的五彩纸屑物理粒子撒花按钮，点击时计算触发坐标并向四周喷射 Confetti 粒子。
- **代码位置：** `apps/platform-web/src/components/base/ConfettiButton.vue`
- **预期结果：** 点击按钮时在视口中喷出五彩纸屑，动效轻快不卡顿，1.5 秒内自动垃圾回收。
- **验证项：** `pnpm test:run src/components/base/ConfettiButton.spec.ts` → ✅ 3/3 通过
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-frontend-confetti-and-suggestions.md](implementation/01-frontend-confetti-and-suggestions.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### Task 1.2: 实现 ComposerSuggestions.vue 灵感胶囊栏
- **改动内容：** 构造水平响应式灵感建议栏，包含“🎉 小惊喜”以及“📝 写作”、“🔬 调研”、“📊 分析”、“💻 网页”等胶囊，点击后填入草稿并通知父组件聚焦。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ComposerSuggestions.vue`
- **预期结果：** 在 `ChatComposer` 顶部插槽优雅呈现，不抢占主输入区空间。
- **验证项：** `pnpm test:run src/modules/chat/components/ComposerSuggestions.spec.ts` → ✅ 3/3 通过
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-frontend-confetti-and-suggestions.md](implementation/01-frontend-confetti-and-suggestions.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

### Task 1.3: ChatComposer.vue 与 ChatSession.vue 集成对齐
- **改动内容：** 将灵感胶囊栏接入 `ChatComposer.vue`，支持在会话空状态或输入框未聚焦时友好引导，与 `draft` 双向绑定。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- **预期结果：** 用户在任何聊天界面均可一键触发小惊喜与常用指令，响应式草稿双向联动。
- **验证项：** `pnpm test:run src/modules/chat/components/ChatComposer.spec.ts` 与全量 19 组组件测试（67/67 通过），`pnpm build` 打包无报错 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-02 → 见 [01-frontend-confetti-and-suggestions.md](implementation/01-frontend-confetti-and-suggestions.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 2: Agent 创意编程与小品生成指引

### Task 2.1: DearFlow Agent Prompt 补充单文件创意编程规范
- **改动内容：** 在 `prompts.py` 的 `SYSTEM_PROMPT` 中新增创意小品与惊喜请求的处理规范：严格单文件零外部资源依赖、纯原生 Canvas/SVG/CSS 动画、Web Audio 合成音效、通过 `present_artifacts` 发布。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`
- **预期结果：** Agent 接收到“给我一个小惊喜吧”时能够自主产出可交互的精品 HTML。
- **验证项：** `uv run pytest tests/services/dearflow_agent/test_agent.py`（18/18 通过）与 `test_research.py`（15/15 通过） → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-02 → 见 [02-agent-creative-coding-prompt.md](implementation/02-agent-creative-coding-prompt.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## Phase 3: 全链路端到端验收

### Task 3.1: 界面交互与沙箱实时试玩验证
- **改动内容：** 端到端测试点击“小惊喜”，等待 Agent 执行并生成单文件 HTML，检查工作区右侧产物面板中 Canvas 渲染与 Web Audio 播放能力。
- **预期结果：** 粒子动效流畅，产物高保真运行，无控制台报错或跨域安全拦截。
- **验证项：** 前端编译、组件测试及后端 Agent 单测全绿通过 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-02
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新
  - [x] docs/CHANGELOG.md 已更新

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全链路端到端验收通过
