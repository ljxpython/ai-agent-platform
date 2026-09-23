# 方案

原始 OpenAI 兼容接口分别返回 `reasoning_content`（Qwen）和 `reasoning` / `reasoning_details`（DeepSeek）。Runtime 使用 LangChain 模型适配，Web 从 LangGraph 消息构造 Transcript。官方 `ChatOpenAI` 文档说明第三方非标准字段不会保留。

1. 对照原始接口和 Runtime 当前 `ChatOpenAI` / `ChatDeepSeek` 的 invoke、stream 输出，定位字段损失点。
2. 在实际丢失的边界做最小修复，兼容现有文本及工具调用；Web 只消费确实传达的字段。
3. 验证模型适配、前端转换和完整消息链路。

契约：思考内容沿 LangChain 消息 `additional_kwargs` 或标准 `content_blocks` 到达 Web，且不会混入最终回答正文。

状态：partial。已确认 `ChatOpenAI` 丢弃第三方推理字段；正式平台聊天链路尚待运行中模型目录的实测。
