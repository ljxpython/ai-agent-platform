# 实现记录 02: Agent 代码库调研收敛与预算收尾感知治理

## 改动文件
- [prompts.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/prompts.py)
- [execution_budget.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/middlewares/execution_budget.py)
- [agent.py](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/runtime-service/src/runtime_service/services/dearflow_agent/agent.py)

## 改动背景与根因
1. 原 `SYSTEM_PROMPT` 仅针对联网搜索设定了 3~5 次的收敛约束，对代码库与本地文件分析完全缺少边界限制。导致 Agent 在剖析 GitHub 仓库时陷入微观强迫症，频繁调用 `execute` 运行临时脚本对数十兆的全量文件树进行逐行正则遍历，耗尽 50 轮模型调用仍未输出产物。
2. 原预算告警指令 `WRAPUP_INSTRUCTION` 为纯英文，在中文长思考链（Reasoning）中易被忽略，且默认只在最后 3 次告警，模型缺乏充分的收敛余地。

## 改动内容
1. **代码资产与本地架构剖析收敛准则**：
   - 确立自顶向下（Top-Down）骨架原则，禁止深陷叶子节点微观穷举；
   - 设定单轮剖析探索工具调用 5~8 次的硬约束；
   - 严禁通过 `execute` 编写脚本对全量文件树进行全量正则/递归扫描；
   - 强制即刻落笔与阶段性交付，将结论迅速输出，次要未尽事项列为后续建议。
2. **中文化高优先级收尾指令**：
   - 将 `WRAPUP_INSTRUCTION` 升级为具备高优先级警示的中英双语指令，明确勒令模型“立即停止一切探索性调研与工具调用，必须立即利用当前已有信息整合并输出最终答复与产物”；
   - 将 `dearflow_agent` 的 `ExecutionBudgetMiddleware` 预警阈值显式提升为 `warning_calls=5`，提早刹车留出总结缓冲空间。
