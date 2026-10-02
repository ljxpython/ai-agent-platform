# 智能体创意编程提示词规范对齐细节

## 改动时间
2026-10-02

## 相关任务
- Task 2.1: DearFlow Agent Prompt 补充单文件创意编程规范

## 改动文件
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`

## 具体改动

### 1. prompts.py
**位置：** `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`
**改动内容：**
在 `SYSTEM_PROMPT` 中明确增加了针对“小惊喜”、“创意互动小品”、“视觉艺术”或“交互单页”的交付范式：
```text
面对用户提出的“小惊喜”、创意互动小品、视觉艺术或交互单页需求：
- 遵循单文件、零外部依赖原则（自包含 HTML + CSS + 原生 JavaScript / Canvas / SVG）；
- 若需背景配乐或互动音效，必须使用 Web Audio API 纯原生波形实时合成，严禁引用不可控的外部音频文件或网络请求；
- 支持响应式自适应视口与暗色/浅色模式，交互流畅；
- 在 /workspace/work/ 编写完成后，必须调用 present_artifacts 发布到产物区供用户在沙箱中即时把玩。
```

## 理由
1. **零外部资源依赖**：避免由于引用外部不可用或被墙的 CDN/图片/音频链接导致在安全沙箱中出现 404 或死链；
2. **Web Audio 纯实时波形合成**：借鉴原版 DeerFlow 的高水准实现，通过原生 OscillatorNode 与 GainNode 实时合成声效（如古琴拨弦、烟花绽放、风声水声），既不需要外部音频文件，又完全符合工作区严格沙箱环境；
3. **闭环交付**：通过 `present_artifacts` 自动发布至工作区产物树，无缝触发前端 `SandboxedHtmlFrame.vue` 现代化高保真预览。

## 验证
- [x] `uv run pytest tests/services/dearflow_agent/test_agent.py` (18/18 通过)
- [x] `uv run pytest tests/services/dearflow_agent/test_research.py` (15/15 通过)
