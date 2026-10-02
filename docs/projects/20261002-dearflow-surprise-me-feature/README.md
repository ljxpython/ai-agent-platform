# DearFlow Agent 灵感建议与“小惊喜”创意工坊迁移

## 项目概述
- **时间：** 2026-10-02 至 2026-10-02
- **目标：** 完整复刻与超越原版 DeerFlow 的“给我一个小惊喜”（Surprise Me）体验：前端实现微动效撒花按钮与常驻灵感建议胶囊栏，后端增强 DearFlow Agent 的单文件交互式创意生成（Canvas + Web Audio + SVG）与沙箱高保真联动预览。
- **负责人：** @laowang
- **模板类型：** 标准模板
- **状态：** 已完成 (done)

## 快速导航
- [整体方案](plan.md)
- [任务拆分](tasks.md)
- [验证记录](verification.md)

## 改动范围
- **影响服务：** `platform-web`, `runtime-service`
- **改动级别：** 链路改动（跨服务体验与产物交互对齐）
- **预计工作量：** 0.5 人天

## 关键决策
1. **前端解耦与渐进增强：** 封装独立的 `ConfettiButton.vue`（基于微型 Canvas 粒子或 `canvas-confetti`）与 `ComposerSuggestions.vue` 灵感胶囊栏，以组件插槽模式挂载至 `ChatComposer.vue`，保持纯净无侵入。
2. **轻量灵感词库与动态填词：** 不仅支持“🎉 小惊喜（给我一个小惊喜吧）”，同时对齐 DeerFlow 提供“📝 深度写作”、“🔬 敏捷调研”、“📊 数据洞察”、“💻 互动页面”等可扩展胶囊，点击既有动效反馈，又能优雅填入 Composer 草稿。
3. **闭环利用刚交付的沙箱高保真预览：** 充分利用上一阶段落地的 `SandboxedHtmlFrame.vue` + `html_preview.py`（放行 `allow-scripts` 且锁死 `Origin: null`），使得智能体生成的 Canvas 粒子、Web Audio 实时音效、SVG 动画在工作区右侧产物面板中实现 100% 免刷新零延迟交互试玩。
4. **Agent 创意与安全边界收敛：** 在 `DearFlow Agent` 提示词中明确“趣味交互作品”规范——必须为零网络请求、零外部依赖音频/图片、纯前端原生合成的单文件 HTML，并强制使用 `present_artifacts` 声明不可变产物。
