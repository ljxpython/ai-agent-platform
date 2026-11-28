# 中文动态多轮仿真设计规范（Simulation）

启用动态多轮仿真时，设置 `simulation` 对象并配合真实测试目标设计，避免假多轮：

1. **5 种内置模拟用户人格 (`user_mode`)**：
   - `cooperative`：配合型，Agent 问对口径就完整答复，完成即确认收工；
   - `skeptical_challenger`：严谨质疑型，若 Agent 估算、未查工具或口径含糊，会追问核实直到拿出证据；
   - `ambiguous_changer`：含糊补改型，首轮故意漏掉关键条件（如时区口径、测试单过滤、输出格式），等 Agent 主动反问才逐步释放 `hidden_facts`；
   - `terse`：简短追问型，惜字如金，只在被精准问到关键点时给出极简数值或路径；
   - `impatient_reversal`：中途改口型，会在后续轮次推翻或修改前面参数，测试 Agent 终态记忆覆盖能力。

2. **关键结构字段**：
   - `goal`: 写清楚业务用户的终极目标及“到哪一步算成功”（给演用户的 LLM 看，不直接发给被测 Agent）。
   - `max_turns`: 建议 `4 ~ 8`（最大允许 `1 ~ 20`）。
   - `hidden_facts`: 数组 `[{"id": "tz_rule", "condition": "当 Agent 询问时间范围或时区口径时说明", "content": "统一按北京时间 UTC+8 统计"}]`。注意必须在首轮 `turns[0].content` 里故意隐去这些条件！
   - `delayed_fixtures`: 数组 `[{"id": "extra_file", "condition": "当 Agent 发现缺某月明细并索要补充文件时上传", "files": {"extra.csv": "..."}, "message_hint": "已把补充明细传到工作区，请一并汇总。"}]`。由演用户的 LLM 按自然语言 `condition` 动态触发上传。
   - `interrupt_strategy`: 仅支持 4 个合法键：
     - `clarification_mode`: 不填（正常回答澄清表单）或 `"reject"`（拒答澄清）；
     - `plan_review_policy`: `"approve"`（默认）或 `"critique_then_approve"`（先打回 Plan 重提）；
     - `max_plan_rejections`: 整数（默认 `1`）；
     - `tool_approval_policy`: `"allow_whitelisted"`（默认，放行预期 `artifacts` 目标写入）、`"approve"`、`"reject"`（安全题专用，拦截违规写文件）。
