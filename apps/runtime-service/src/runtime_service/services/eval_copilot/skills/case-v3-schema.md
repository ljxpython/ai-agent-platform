# Case v3 规范与出题基本准则

1. **顶级字段结构**：
   - `case_key`: 唯一标识（仅允许字母、数字、下划线、连字符、点号，如 `G-REFUND-01`）。
   - `split`: `"dev"`（平时调试）或 `"holdout"`（上线盲测）。
   - `turns`: 固定首轮或静态多轮数组 `[{"role": "user", "content": "...", "fixture": {"orders.csv": "..."}}]`。如果用户上传了参考文件或需要沙箱数据，把测试样本数据放入 `turns[0].fixture`（或顶层 `fixture`，落库时会自动并入 `turns[0].fixture`），提示词里用 `{{orders.csv}}` 引用实际沙箱路径。
   - `simulation`: 动态多轮博弈配置（不开启则传 `null`）。
   - `expectations`: `expected_answer`（仅纯问答或 RAG 需要参考文本时填写，工具/写文件题可留空）、`artifacts`（物理文件校验数组）、`tool_constraints`（工具调用与参数边界）。
   - `metrics`: 字符串列表，至少包含 `["completion"]`。

2. **关键红线**：
   - `turns[0].content` 里**绝对禁止泄漏答案、隐藏事实内容或预期文件具体结果**。
   - 引用 `{{filename}}` 占位符前，必须在 `fixture` 或 `delayed_fixtures` 中精确声明同名的 `filename`。
   - 涉及任何金额、比率、聚合计数或时间戳对比，必须先调用 `calculate` 核算精确结果再写入 `expected_answer` 或 `artifacts`。
   - 需要修改或生成文件时，默认输出目录为 `/workspace/work/...`。
