# 任务

## Task 1：定位模型适配差异
- **改动内容：** 对比原始响应与 LangChain invoke/stream 消息。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/modeling.py` → `build_model()`
- **预期结果：** 明确 Qwen、DeepSeek 各自在哪一层丢失思考内容。
- **验证项：** 双模型实测与字段摘要。
- **状态：** [x] 2026-09-23，Qwen 经旧 `ChatOpenAI` invoke/stream 推理长度均为 0，DeepSeek 经 `ChatDeepSeek` 保留。
- **合规检查：** [x] 实测 [x] 结果记录 [x] 状态更新 [x] CONTEXT 更新

## Task 2：修复消息链路与展示
- **改动内容：** 保留可展示的推理文本并统一 Web 读取。
- **代码位置：** Runtime 模型构建和 `apps/platform-web/src/modules/chat/transcript.ts`
- **预期结果：** 思考内容单独展示，正文与工具调用保持原状。
- **验证项：** 定向单测。
- **状态：** [x] 2026-09-23，见 [实现记录](implementation/01-provider-reasoning.md)。
- **合规检查：** [x] 代码实现 [x] 定向验证 [x] 状态更新 [x] CONTEXT 更新

## Task 3：链路验证
- **改动内容：** 执行单元、集成与端到端验证并记录结果。
- **代码位置：** `verification.md`
- **预期结果：** 如实确认完成度与未覆盖风险。
- **验证项：** 测试与本地链路检查。
- **状态：** [x] 2026-09-23，局部验证完成，正式平台聊天链路待验。
- **合规检查：** [x] 验证执行 [x] 结果记录 [x] 状态更新 [x] CONTEXT 更新

## Task 4：去除展开态重复思考预览
- **改动内容：** Think 收起时保留摘要，展开时只显示全文。
- **代码位置：** `apps/platform-web/src/modules/chat/components/MessageContent.vue` → reasoning `<details>`
- **预期结果：** 展开后思考文本只出现一次。
- **验证项：** Playwright 收起/展开断言、ESLint、类型检查，均通过。
- **状态：** [x] 2026-09-23，见 [实现记录](implementation/01-provider-reasoning.md)。
- **合规检查：** [x] 代码实现 [x] 验证执行 [x] 状态更新 [x] CONTEXT 更新

## Task 5：修复流式阶段 `content_blocks` 丢失与模型选择器同名去重
- **改动内容：** `ChatOpenAIWithReasoning` 显式设置 `model_provider="openai_compatible"`，解除 `langchain_core` OpenAI translator 对流式 `additional_kwargs["reasoning_content"]` 的屏蔽；修复 `MessageContent.vue` 原生 `<details>` `@toggle` 覆盖流式自动展开状态的问题；`ChatModelSelector.vue` 支持 `defaultModelId` 精准匹配、作用域标签展示及同渠道同名模型去重。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/modeling.py`、`apps/platform-web/src/modules/chat/components/MessageContent.vue`、`ChatModelSelector.vue`
- **预期结果：** 对话流式过程中实时输出并展开 `Think` 思考内容，不再等对话结束后才弹出；对话模型选择器不再重复展示同渠道同名模型。
- **验证项：** `test_modeling.py` (12 passed) 与 `ChatModelSelector.spec.ts` (3 passed)。
- **状态：** [x] 2026-09-23
- **合规检查：** [x] 代码实现 [x] 验证执行 [x] 状态更新 [x] CONTEXT 更新

## Task 6：放宽推理模型单次调用超时至 600s 并清理前端未落库超时重试废稿
- **改动内容：** 将 `showcase_demo`、`workflow_demo`、`reference_agent`、`dearflow_agent` 的 `ModelCallTimeoutMiddleware(timeout_seconds=...)` 统一调宽至 `600` 秒，避免深度思考 + 长文流式输出在 30 秒处被强行中断重试；在 `useTranscriptMessages.ts` 中过滤流式重试期间被新 `AIMessage` 覆盖的未落库废稿以及流结束时不在 `values.messages` 快照中的未提交消息，避免超时重试废稿被塞入顶部“执行步骤与工具调用”。
- **代码位置：** `apps/runtime-service/src/runtime_service/services/**/agent.py`、`apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **预期结果：** 推理模型长文生成不再因 30 秒超时而反复重试，且即使发生重试也不会在前端对话中残留废稿。
- **验证项：** `useTranscriptMessages.spec.ts` (6 passed) 与 `test_runtime_middleware.py` / `test_middleware_order.py` (22 passed)。
- **状态：** [x] 2026-09-23
- **合规检查：** [x] 代码实现 [x] 验证执行 [x] 状态更新 [x] CONTEXT 更新


