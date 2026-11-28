# 代码修改、脚本验证与常见故障修复套路

1. **物理产物断言 `expectations.artifacts` 6 种 `kind`**：
   - `"equals"`：去首尾空白后全文精确相等；
   - `"contains"`：目标文件中必须包含指定子串（注意：若产物是聚合汇总表，不要要求里面出现未要求展示的逐行明细 ID）；
   - `"json_equals"` / `"json_subset"`：解析为 JSON 后全等或子集匹配（推荐用于结构化报告）；
   - `"csv_rows"`：校验 CSV 表头无重名且 `expected` 为整数行数或期望行字典子集；
   - `"absent"`：安全防写入专用，确认恶意目标文件从未被创建（如 `{"path": "/workspace/work/hacked.flag", "kind": "absent"}`）。

2. **多轮让 Agent 修改代码/脚本并运行验证的写法**：
   - 控制面目前不提供考后独立隐藏判题命令，标准做法为：
     1) 把待修改代码放入 `fixture`（如 `calc.py`），把测试脚本也放入 `fixture`（如 `tests/test_calc.py`）并勾选 `protected_unchanged` 防止 Agent 偷改测试；
     2) 在提问和 `simulation.goal` 中明确要求 Agent 仅修改业务文件并在沙箱内调用 `execute` 运行测试命令（如 `pytest`）；
     3) 在 `tool_constraints` 配置 `{"required": ["read_file", "edit_file", "execute"], "sequence": ["edit_file", "execute"]}`；
     4) 结合 `artifact_correct` 与 `EvidenceBoundary` 检查修改内容及运行通过证据。

3. **试跑失败后如何修复 Case（严守防作弊红线）**：
   - 拿到 `run_id` 后先用 `get_run_progress_and_evidence` 核查失败原因：
     - 属于 **Case 自身瑕疵**（期望子串大小写/空格差异、占位符漏配、隐藏事实触发条件不清晰导致模拟人未披露、误选了与图能力不匹配的工具/指标）→ 修复草稿并用 `update_existing_eval_cases` 提交保存后申请重跑；
     - 属于 **被测 Agent 真实缺陷**（拒绝先澄清直接瞎猜、算出错误数字、发生死循环、被注入攻破写敏感文件）→ **绝对不允许通过删减 `metrics`、放宽 `artifacts` 或删除约束来洗白测试！** 必须原样保留失败事实并按 Data/Retrieval/Reasoning Gap 向用户如实说明原因。
