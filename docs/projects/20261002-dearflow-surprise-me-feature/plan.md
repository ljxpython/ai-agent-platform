# DearFlow Agent 灵感建议与“小惊喜”创意工坊 - 整体方案

## 背景
用户在体验原版 `deer-flow`（会话 `ecf4a7f1-b626-4821-93aa-a92b78976903`）时，体验到了其输入框上方的“小惊喜”功能：
1. 点击输入框胶囊按钮，伴随着轻快的五彩纸屑撒花（Confetti）物理粒子动效；
2. 输入框自动填入“给我一个小惊喜吧”并触发智能体执行；
3. 智能体根据用户画像与语境，自主在沙箱内写出一份纯前端、单文件、零外部依赖、自包含 Web Audio 与 Canvas 物理渲染的水墨交互作品（如《秋江灯影》：点击江面放河灯、涟漪扩散、实时古琴合成）；
4. 通过文件发布工具在工作区内即时可交互预览。

当前我们平台已在底层具备高保真安全预览能力（`SandboxedHtmlFrame.vue` + `html_preview.py`），但前端交互层缺乏灵感胶囊与粒子微交互，智能体侧对“创意交互小品”的交付范式未做系统性指引。

## 目标
1. **前端交互体验**：在 `platform-web` 的聊天输入框（`ChatComposer`）上方引入可折叠/按需呈现的灵感建议胶囊栏，核心包含带五彩纸屑撒花动画的“🎉 小惊喜”按钮及常用高频指令胶囊；
2. **输入联动控制**：支持一键将预设 prompt 填入输入框草稿并聚焦，支持在空会话及日常对话中随时呼出；
3. **Agent 创意生成能力增强**：在 `DearFlow Agent` 中注入创意编程（Creative Coding）范式约束，确保生成“单文件 · 零依赖 · 纯实时合成”的高质量交互式网页，并通过 `present_artifacts` 闭环交付至工作区；
4. **全链路沙箱安全与体验闭环**：验证生成的作品在既有沙箱中正常播放 Web Audio 音效、Canvas 动画流畅运行、且零网络探测或跨域越权。

## 方案设计

### 整体架构

```text
[用户界面 platform-web]
  │
  ├── ComposerSuggestions.vue (常驻/建议灵感胶囊)
  │     ├── ConfettiButton.vue (五彩撒花物理粒子微交互)
  │     │     └── 触发 Prompt: "给我一个小惊喜吧"
  │     └── Quick Suggestion Pills ("写作", "调研", "网页", "图表")
  │           └── 填入 ChatComposer 草稿框并自动聚焦
  │
  ▼
[平台网关 platform-api & SSE]
  │
  ▼
[运行时 runtime-service: DearFlow Agent]
  │
  ├── 识别创意作品/惊喜诉求 (Creative Coding Pattern)
  ├── 在 /workspace/work/ 生成单文件互动作品 (Canvas + Web Audio + SVG)
  └── 调用 present_artifacts 原子发布到 /workspace/outputs/
  │
  ▼
[工作区沙箱 SandboxedHtmlFrame.vue]
  │
  └── sandbox="allow-scripts" + Origin: null 安全隔离，真机交互试玩！
```

### 关键改动点

#### 1. 前端撒花按钮与灵感胶囊组件
- **文件：**
  - `apps/platform-web/src/components/base/ConfettiButton.vue`（新组件）
  - `apps/platform-web/src/modules/chat/components/ComposerSuggestions.vue`（新组件）
  - `apps/platform-web/src/modules/chat/components/ChatComposer.vue`（挂载与布局对齐）
- **实现方案：**
  - 采用轻量级 `canvas-confetti` 或自研基于 requestAnimationFrame 的 Canvas 粒子系统（控制在 50 行内，零体积膨胀）；
  - `ComposerSuggestions.vue` 布局为响应式水平滚动/弹性换行的精致小胶囊，包括：
    - `🎉 小惊喜`：点击撒花，草稿填入“给我一个小惊喜吧”
    - `📝 深度写作`：草稿填入“撰写一篇关于[主题]的深度技术博客”
    - `🔬 敏捷调研`：草稿填入“深入研究一下[主题]，并总结核心架构与发现”
    - `📊 数据分析`：草稿填入“分析以下数据并绘制直观图表：”
    - `💻 交互网页`：草稿填入“生成一个现代高保真交互式单文件网页：”
  - 点击胶囊时带反馈动画，优雅更新 `draft`。

#### 2. DearFlow Agent 创意编程与小品生成指引
- **文件：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`
- **改动：**
  - 在 `SYSTEM_PROMPT` 中补充对“小惊喜 / 趣味小作品 / 创意网页 / 视觉艺术”的交互规范：
    - 坚持**单文件 · 零依赖**原则（HTML + CSS + 原生 JS / Canvas / SVG）；
    - 若需音效，使用 **Web Audio API 纯实时波形合成**，禁止引用不可控的外链 MP3/WAV；
    - 界面适配暗色/浅色自适应与响应式视口；
    - 完成后必须调用 `present_artifacts` 发布到产物区。

## 链路影响
- **调用链路：** `platform-web (ChatComposer)` → `platform-api` → `runtime-service (DearFlow Agent)` → `/workspace/outputs/{file}.html` → `platform-web (SandboxedHtmlFrame)`
- **契约变更：** 无破坏性契约变更，完全复用既有的 Run 触发与 Artifacts 产物发布契约。

## 风险和依赖
- **依赖：** `canvas-confetti` 依赖或自研微型 Canvas 粒子（优先自研或安全安装，确保打包体积极小）；
- **风险：** 撒花粒子在低端设备或极端缩放下的坐标偏移；
  - **应对：** 使用 `getBoundingClientRect()` 计算相对于视口的绝对百分比坐标，严格限制粒子数量（最大 50-75 颗），单次触发 1.5 秒后自动销毁 DOM 节点。

## 实施计划
1. **Phase 1: 前端动效与胶囊组件研发**
   - 编写 `ConfettiButton.vue` 与粒子发射逻辑；
   - 编写 `ComposerSuggestions.vue` 并接入 `ChatComposer.vue`；
   - 编写前端 Vitest 单元测试。
2. **Phase 2: DearFlow Agent 创意编程指令补充**
   - 更新 `prompts.py` 补充创意小品单文件交付指引；
   - 单元测试回归验证。
3. **Phase 3: 端到端效果实测与工作区验证**
   - 真实点击“小惊喜”全链路执行，验证生成单文件 Canvas + Web Audio 互动小品，在沙箱中高保真试玩。
