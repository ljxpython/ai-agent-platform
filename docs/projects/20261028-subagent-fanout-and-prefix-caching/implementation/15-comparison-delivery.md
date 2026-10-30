# 调研比较按一致维度交付

2026-10-29；任务T0.X。

v17实际核查了原文，前三个行为维度仍被flags/activation细节替代，漏掉子报告已有的父级发现；主报告7597字符，核心4/5。

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/code_explorer.py` → `code_explorer()`：把既有比较维度落实为表格列，提供方为行，未知明确标出，禁止flags清单替代比较。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py` → `SYSTEM_PROMPT`：同样保留比较维度与限定，移除最多六行的冲突软限制，仍要求紧凑交付。
- `apps/runtime-service/tests/services/dearflow_agent/test_agent.py`：核对Pro/Ultra父子装配要求。

最小装配2 passed/22 deselected/5 warnings（11.03s），Ruff通过。未改模型/任务/预算/来源/评分，没有新增状态机或评审模型；真实稳定性必须v18验证。
