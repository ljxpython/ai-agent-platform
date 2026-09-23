# Provider 推理字段保留

2026-09-23，关联 Task 1-2。

- `apps/runtime-service/src/runtime_service/runtime/modeling.py`：`ChatOpenAIWithReasoning` 在非流式结果和流式 chunk 中，将第三方 `reasoning_content`、`reasoning` 或 `reasoning_details[].text` 保留到 `additional_kwargs.reasoning_content`。`build_model()` 的通用 OpenAI 兼容分支使用该适配器，DeepSeek 专用分支不变。
- `apps/platform-web/src/modules/chat/transcript.ts`：`extractReasoningFromMessage()` 读取三种原始格式；`apps/platform-web/src/modules/chat/trajectory/trajectory-adapter.ts` 复用同一规则。
- `apps/platform-web/src/modules/chat/components/MessageContent.vue`：Think 摘要只在收起时可见，展开后只保留全文，修复同一思考显示两次的问题。
- `apps/runtime-service/tests/runtime/test_modeling.py`、`apps/platform-web/src/modules/chat/transcript.test.ts`、`apps/platform-web/e2e/rendering-refactor.spec.ts`：覆盖字段映射和独立显示。

理由：LangChain `ChatOpenAI` 明确不保留第三方响应字段，前端不能渲染未传来的内容。保留在现有消息字段可沿用 LangGraph 与 Web 契约，无需新增协议。
