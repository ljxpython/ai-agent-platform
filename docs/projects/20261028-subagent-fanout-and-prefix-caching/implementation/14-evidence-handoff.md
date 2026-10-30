# 调研证据交接保留语义限定

2026-10-29；任务T0.V。

v16父仅2次模型调用、0次原文核对，主峰值5.6%但质量2/5。子概述在无引用前言中，父重排时保留类型细节却丢失行为限定；不是窗口或总额度故障。

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/code_explorer.py` → `code_explorer()`：概述并入有引用的最多五条结论，保持条件、作用对象与动作顺序，先删可选配置细节。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py` → `SYSTEM_PROMPT`：最终答复前批量核对各原问题至少一处关键原文，限定与行号随结论保留，只补证据缺口。
- `apps/runtime-service/tests/services/dearflow_agent/test_agent.py` → `test_delegation_mode_exposes_restricted_code_explorer()`：Pro/Ultra装配检查父子指令接线，无目标仓库路径或答案。

先红2 failed/22 deselected（12.35s），修改后组合34 passed/1 skipped/33 warnings（54.68s），Ruff通过。没有新增工具/中间件/模型评审层，预算与任务不变；是否改善真实交付须v17实测，不能从字符串断言推断。
