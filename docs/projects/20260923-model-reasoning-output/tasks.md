# 任务

## Task 1：定位模型适配差异
- **改动内容：** 对比原始响应与 LangChain invoke/stream 消息。
- **代码位置：** `apps/runtime-service/src/runtime_service/runtime/modeling.py` → `build_model()`
- **预期结果：** 明确 Qwen、DeepSeek 各自在哪一层丢失思考内容。
- **验证项：** 双模型实测与字段摘要。
- **状态：** [/] 进行中

## Task 2：修复消息链路与展示
- **改动内容：** 保留可展示的推理文本并统一 Web 读取。
- **代码位置：** Runtime 模型构建和 `apps/platform-web/src/modules/chat/transcript.ts`
- **预期结果：** 思考内容单独展示，正文与工具调用保持原状。
- **验证项：** 定向单测。
- **状态：** [ ] 待开始

## Task 3：链路验证
- **改动内容：** 执行单元、集成与端到端验证并记录结果。
- **代码位置：** `verification.md`
- **预期结果：** 如实确认完成度与未覆盖风险。
- **验证项：** 测试与本地链路检查。
- **状态：** [ ] 待开始
