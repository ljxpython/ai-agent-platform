# 收尾撤除Schema并保留显式禁用

- 时间：2026-10-29；任务：T0.J；取代implementation/09中仅保留Schema的收尾策略。
- 根因：v10第三子第8次模型调用在tool_choice=none下仍返回DSML文本。保留可见工具声明未能稳定阻止供应商输出调用标记；父报告又因4096中包含reasoning而截断。
- 文件：`apps/runtime-service/src/runtime_service/middlewares/execution_budget.py:disable_tool_calls`；测试`tests/middlewares/test_execution_budget.py`、`tests/runtime/test_model_resilience_protocols.py`。
- 最小修复：将tools置空，并通过model_settings传协议原生none（保留其他settings）；原有_observed_request在容灾切换后再次按实际模型规范化。空tools的LangChain factory只调用model.bind(model_settings)，否则会丢失tool_choice字段。
- 不解析或执行原始DSML，不追加隐式模型重试，不绕过共享预算。若供应商仍返回损坏报告，真实质量验收继续判失败。
- 回归先红8 failed/4 passed（14.06s）；修复后预算/协议/装配70 passed、5 warnings（59.08s），Ruff通过。原始request不可变与已有参数保留也在断言中。
- v11仅隔离测试共同输出上限8192，原题prompt哈希不变；不改产品默认、Run兜底或事实评分。真实模型效果由T3.2记录。
