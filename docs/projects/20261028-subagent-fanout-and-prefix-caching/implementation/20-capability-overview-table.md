# 能力概述显式字段交接

## 背景

v21已按冻结实现完成两臂各三次：委派五项核心合格2/3，串行首轮漏默认启用，后两次缺用量。完整汇总见[原始指标与评分](19-v21-controlled-comparison.json)。现有指令已要求默认装配和主循环关系，但自由叙述仍省略这些结论；不能把低上下文占用当作质量通过。

## 最小修改

- `apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py`：能力概述使用一能力一行的短表，把默认装配、主循环关系和证据分成显式列；填写有证据的结论或未知。替换原来的同义概述要求，不改变原始问题、评分、权限、预算或工具。
- `apps/runtime-service/src/runtime_service/services/dearflow_agent/subagents/code_explorer.py`：子报告使用同样的通用列；纯流程子题可直接交付流程，不强加无关表格。保留原短证据交接、调用额度和只读边界；未加入目标路径或事实答案。
- `apps/runtime-service/tests/services/dearflow_agent/test_agent.py`：Pro/Ultra装配断言覆盖父子字段要求；该测试只证明接线，不保证模型遵循，真实质量须另采新组。

## Phase证据

- 先红：2 failed、10 passed、12 deselected、5 warnings（31.61s）；失败均为新格式断言。
- 修改后：Agent/Subagent/共享预算组合35 passed、1 skipped、37 warnings（68.51s）；跳过和第三方警告不计通过。
- 本轮三文件Ruff通过。日志保留于所属Worktree `.local-stack/phase-v22-overview-{red,green}.log`。
- v21六次原始文件和人工评分不改、不替换；新版本冻结后仍须按原五项事实重新验收，不以模板断言替代模型证据。项目尚未进入Final。
